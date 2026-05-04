"""
pii-guard CLI

Commands:
  scan            Detect PII and report what was found (read-only)
  tokenize        Replace PII with consistent tokens, write session key
  detokenize      Reverse tokenize using a session key file
  stats           Show token counts from a session key file
  export-session  Export session as CSV for Excel / VLOOKUP
  proxy           Start local PII-filtering API proxy
  install-hooks   Install Claude Code PostToolUse hooks
  config          Manage configuration
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml

from pii_guard.presets import AVAILABLE_PRESETS, load_presets
from pii_guard.scanner.engine import Scanner
from pii_guard.scanner.patterns import BASE_PATTERNS
from pii_guard.tokenizer.engine import detokenize as _detokenize
from pii_guard.tokenizer.engine import tokenize as _tokenize
from pii_guard.tokenizer.session import Session

_CONFIG_PATH   = Path.home() / ".pii-guard" / "config.yaml"
_AUDIT_LOG     = Path.home() / ".pii-guard" / "audit.log"


# ── Config loading ────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    try:
        return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _custom_patterns_from_config() -> dict[str, str]:
    return _load_config().get("custom_patterns") or {}


def _parse_inline_patterns(pattern_args: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for arg in pattern_args:
        if ":" not in arg:
            raise click.UsageError(
                f"--pattern must be KEY:REGEX (e.g. --pattern CUSTOMER_ID:CUST-\\d{{6}}), got: {arg!r}"
            )
        key, _, regex = arg.partition(":")
        key = key.strip().upper()
        try:
            re.compile(regex)
        except re.error as e:
            raise click.UsageError(f"Invalid regex for {key!r}: {e}")
        result[key] = regex
    return result


# ── Shared helpers ────────────────────────────────────────────────────────────

def _build_scanner(
    presets: tuple[str, ...],
    no_base: bool,
    extra_patterns: tuple[str, ...] = (),
) -> Scanner:
    patterns: dict[str, str] = {}
    if not no_base:
        patterns.update(BASE_PATTERNS)
    if presets:
        patterns.update(load_presets(list(presets)))
    patterns.update(_custom_patterns_from_config())
    if extra_patterns:
        patterns.update(_parse_inline_patterns(extra_patterns))
    if not patterns:
        raise click.UsageError("No patterns loaded. Specify at least one preset or remove --no-base.")
    return Scanner(patterns)


def _read_input(file: str) -> str:
    if file == "-":
        return sys.stdin.read()
    path = Path(file)
    from pii_guard.formats import is_rich_format, read_text
    if is_rich_format(path):
        try:
            return read_text(path)
        except ImportError as e:
            raise click.ClickException(str(e))
    return path.read_text(encoding="utf-8", errors="replace")


def _default_output_path(input_path: str, suffix: str = ".safe") -> str:
    p = Path(input_path)
    if p.suffix.lower() == ".pdf":
        return str(p.with_stem(p.stem + suffix).with_suffix(".txt"))
    return str(p.with_stem(p.stem + suffix))


def _write_tokenized_output(
    file: str,
    output: str,
    tokenized_text: str,
    sess: Session,
) -> None:
    """Write tokenized output, preserving format for DOCX/XLSX."""
    from pii_guard.formats import is_rich_format, write_tokenized

    path = Path(file)
    out_path = Path(output)

    if is_rich_format(path) and path.suffix.lower() != ".pdf":
        original_to_token = {v: k for k, v in sess.tokens.items()}
        try:
            write_tokenized(path, out_path, original_to_token)
        except ImportError as e:
            raise click.ClickException(str(e))
    else:
        out_path.write_text(tokenized_text, encoding="utf-8")


def _append_audit(action: str, file: str, count: int, by_type: dict[str, int]) -> None:
    """Append one line to the audit log."""
    try:
        _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().isoformat(timespec="seconds")
        parts = [f"{k}:{v}" for k, v in sorted(by_type.items())]
        line = f"{ts}  {action:<12} {Path(file).name:<40} total={count}  {' '.join(parts)}\n"
        with _AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
@click.version_option(package_name="pii-guard")
def cli():
    """pii-guard: local PII firewall for AI CLI tools.

    Tokenize before it leaves your machine.
    """


# ── scan ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("file", default="-", metavar="FILE|-")
@click.option(
    "--preset", "-p",
    multiple=True,
    default=("dpdp",),
    show_default=True,
    help=f"Presets to activate. Available: {', '.join(AVAILABLE_PRESETS)}",
)
@click.option("--no-base", is_flag=True, help="Exclude base patterns (email, IP, JWT…)")
@click.option("--show-values", is_flag=True, help="Print the actual matched values")
@click.option(
    "--pattern", "-P",
    multiple=True,
    metavar="KEY:REGEX",
    help="Add a custom pattern inline, e.g. -P CUSTOMER_ID:CUST-\\d{6}. Repeatable.",
)
def scan(file: str, preset: tuple, no_base: bool, show_values: bool, pattern: tuple):
    """Scan FILE (or stdin) for PII and report findings.

    Supports plain text, CSV, PDF, DOCX, and XLSX files.
    Exits with code 1 if PII is found, 0 if clean.
    """
    scanner = _build_scanner(preset, no_base, pattern)
    text = _read_input(file)
    matches = scanner.scan(text)

    if not matches:
        click.secho("✓ No PII detected.", fg="green")
        sys.exit(0)

    by_type: dict[str, list] = {}
    for m in matches:
        by_type.setdefault(m.pii_type, []).append(m)

    source = file if file != "-" else "stdin"
    click.secho(f"\nFound {len(matches)} PII instance(s) in {source}:\n", fg="yellow", bold=True)

    for pii_type, type_matches in sorted(by_type.items()):
        count = len(type_matches)
        click.secho(f"  {pii_type:<20} {count:>4} instance(s)", fg="yellow")
        if show_values:
            for m in type_matches[:5]:
                click.echo(f"    line {_line_num(text, m.start):>4}: {m.value!r}")
            if count > 5:
                click.echo(f"    … and {count - 5} more")

    click.echo()
    click.echo("Run `pii-guard tokenize` to replace with tokens before analysis.")
    _append_audit("scan", file, len(matches), {t: len(ms) for t, ms in by_type.items()})
    sys.exit(1)


# ── tokenize ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("file", default="-", metavar="FILE|-")
@click.option(
    "--preset", "-p",
    multiple=True,
    default=("dpdp",),
    show_default=True,
    help="Presets to activate.",
)
@click.option("--no-base", is_flag=True, help="Exclude base patterns")
@click.option(
    "--output", "-o",
    default=None,
    help="Output file path. Default: <file>.safe.<ext>. Use - for stdout.",
)
@click.option(
    "--session", "-s",
    default=None,
    help="Session key file. Default: ~/.pii-guard/sessions/pii-guard-<timestamp>.json",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress summary output")
@click.option(
    "--pattern", "-P",
    multiple=True,
    metavar="KEY:REGEX",
    help="Add a custom pattern inline. Repeatable.",
)
def tokenize(
    file: str,
    preset: tuple,
    no_base: bool,
    output: str | None,
    session: str | None,
    quiet: bool,
    pattern: tuple,
):
    """Tokenize PII in FILE (or stdin). Writes safe output + session key.

    Supports plain text, CSV, PDF, DOCX, and XLSX.
    DOCX and XLSX files are tokenized in-place, preserving formatting.
    PDF files are written as tokenized plain text.
    """
    scanner = _build_scanner(preset, no_base, pattern)
    text = _read_input(file)

    sess = Session.load(session) if session else Session.new()
    tokenized, matches = _tokenize(text, scanner, sess)

    if not matches:
        if not quiet:
            click.secho("✓ No PII detected — file is already clean.", fg="green")
        if output and output != "-":
            Path(output).write_text(tokenized, encoding="utf-8")
        elif file == "-" or output == "-":
            click.echo(tokenized, nl=False)
        return

    sess.save()

    if file == "-" or output == "-":
        click.echo(tokenized, nl=False)
    else:
        out_path = output or _default_output_path(file)
        _write_tokenized_output(file, out_path, tokenized, sess)

    if not quiet:
        by_type: dict[str, int] = {}
        for m in matches:
            by_type[m.pii_type] = by_type.get(m.pii_type, 0) + 1

        click.secho(f"\nTokenized {len(matches)} PII instance(s):\n", fg="cyan", bold=True)
        for pii_type, count in sorted(by_type.items()):
            click.echo(f"  {pii_type:<20} {count:>4} → [{pii_type}_1] … [{pii_type}_{count}]")

        if file != "-" and output != "-":
            click.echo()
            click.secho(f"Safe output:  {output or _default_output_path(file)}", fg="cyan")
            click.secho(f"Session key:  {sess.path}", fg="cyan")
            click.echo()
            click.echo("To detokenize AI results:")
            click.secho(
                f"  pii-guard detokenize result.txt --session {sess.path}",
                fg="bright_white",
            )
            click.echo()
            click.echo("To export a mapping CSV for Excel VLOOKUP:")
            click.secho(
                f"  pii-guard export-session {sess.path}",
                fg="bright_white",
            )

    _append_audit("tokenize", file if file != "-" else "stdin", len(matches), by_type if not quiet else {})


# ── detokenize ────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("file", default="-", metavar="FILE|-")
@click.option(
    "--session", "-s",
    required=True,
    help="Session key file (written by pii-guard tokenize).",
)
@click.option("--output", "-o", default=None, help="Output file. Default: <file>.detokenized.<ext>")
@click.option("--quiet", "-q", is_flag=True)
def detokenize(file: str, session: str, output: str | None, quiet: bool):
    """Reverse tokenize FILE using a session key.

    Replaces [TOKEN_N] placeholders with their original values.
    """
    sess = Session.load(session)
    text = _read_input(file)
    result = _detokenize(text, sess)

    if file == "-" or output == "-":
        click.echo(result, nl=False)
    else:
        out_path = output or _default_output_path(file, suffix=".detokenized")
        Path(out_path).write_text(result, encoding="utf-8")
        if not quiet:
            replaced = sum(text.count(tok) for tok in sess.tokens)
            click.secho(f"✓ Replaced {replaced} token(s). Output: {out_path}", fg="green")


# ── stats ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("session", metavar="SESSION")
def stats(session: str):
    """Show token counts from a session key file.

    \b
    Example:
      pii-guard stats ~/.pii-guard/sessions/pii-guard-20240115-103000.json
    """
    sess = Session.load(session)
    tokens = sess.tokens

    if not tokens:
        click.secho("Session is empty — no tokens recorded.", fg="yellow")
        return

    by_type = sess.summary_by_type()
    total = sum(by_type.values())

    click.echo()
    click.secho(f"Session:  {Path(session).name}", bold=True)
    click.secho(f"Total tokens: {total}\n", fg="cyan")
    click.echo(f"  {'Type':<22} {'Count':>6}")
    click.echo(f"  {'-'*22} {'------':>6}")
    for pii_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        click.echo(f"  {pii_type:<22} {count:>6}")
    click.echo()


# ── export-session ───────────────────────────────────────────────────────────

@cli.command("export-session")
@click.argument("session", metavar="SESSION")
@click.option(
    "--output", "-o",
    default=None,
    help="Output CSV path. Default: <session-name>.mapping.csv",
)
@click.option(
    "--filter-type", "-t",
    default=None,
    help="Only export a specific PII type, e.g. EMAIL or AADHAAR.",
)
def export_session(session: str, output: str | None, filter_type: str | None):
    """Export a session key as a CSV mapping file for use in Excel / VLOOKUP.

    \b
    Output format:
      token,pii_type,original_value
      [EMAIL_1],EMAIL,john@acme.com
      [AADHAAR_1],AADHAAR,2345 6789 0123
    """
    import csv as _csv

    sess = Session.load(session)
    tokens = sess.tokens

    if not tokens:
        click.secho("Session has no tokens.", fg="yellow")
        return

    rows = []
    for token, value in sorted(tokens.items()):
        pii_type = token.strip("[]").rsplit("_", 1)[0]
        if filter_type and pii_type.upper() != filter_type.upper():
            continue
        rows.append({"token": token, "pii_type": pii_type, "original_value": value})

    if not rows:
        click.secho(f"No tokens found for type '{filter_type}'.", fg="yellow")
        return

    out_path = output or str(Path(session).with_suffix(".mapping.csv"))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=["token", "pii_type", "original_value"])
        writer.writeheader()
        writer.writerows(rows)

    click.secho(f"✓ {len(rows)} token(s) exported to {out_path}", fg="green")
    click.echo()
    click.echo("In Excel: VLOOKUP(A2, mapping.csv!A:C, 3, FALSE)")


# ── config ────────────────────────────────────────────────────────────────────

@cli.group()
def config():
    """Manage pii-guard configuration."""


@config.command("list-presets")
def list_presets():
    """List available presets."""
    click.echo("Available presets:\n")
    descriptions = {
        "dpdp":  "India DPDP Act — Aadhaar, PAN, UPI, IFSC, GSTIN, mobile",
        "gdpr":  "EU GDPR — IBAN, BIC, VAT, coordinates, MAC address",
        "hipaa": "US HIPAA — SSN, NPI, DEA, MRN, health plan IDs",
        "pci":   "PCI-DSS — credit/debit cards, CVV, card expiry",
    }
    for name in AVAILABLE_PRESETS:
        click.echo(f"  {name:<8} {descriptions.get(name, '')}")


@config.command("show-patterns")
@click.argument("preset")
def show_patterns(preset: str):
    """Show regex patterns for a given preset."""
    try:
        patterns = load_presets([preset])
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"\nPatterns in preset '{preset}':\n")
    for pii_type, pattern in sorted(patterns.items()):
        click.echo(f"  {pii_type}")
        click.echo(f"    {pattern}\n")


# ── proxy ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--port", "-p", default=8111, show_default=True, help="Local port to listen on.")
@click.option(
    "--preset", "-P",
    multiple=True,
    default=("dpdp",),
    show_default=True,
    help="Presets to activate.",
)
@click.option(
    "--pattern",
    multiple=True,
    metavar="KEY:REGEX",
    help="Extra inline pattern, e.g. --pattern CUSTOMER_ID:CUST-\\d{6}",
)
@click.option("--session", "-s", default=None, help="Resume an existing session key file.")
@click.option("--no-base", is_flag=True, help="Exclude base patterns (email, IP, JWT…)")
@click.option("--quiet", "-q", is_flag=True, help="Suppress per-request logs.")
def proxy(port: int, preset: tuple, pattern: tuple, session: str | None, no_base: bool, quiet: bool):
    """Start a local PII-filtering proxy for the Claude / OpenAI API.

    \b
    Works with Cursor, Aider, Codex CLI, Continue.dev, LangChain, and any
    OpenAI-compatible or Anthropic-compatible SDK.

    \b
    Quickstart:
      pii-guard proxy --port 8111 --preset dpdp

    \b
    Configure your SDK:
      export ANTHROPIC_BASE_URL=http://localhost:8111
      export OPENAI_BASE_URL=http://localhost:8111/openai/v1

    \b
    Docker:
      docker run -p 8111:8111 pii-guard proxy --preset dpdp

    \b
    Restore real values:
      pii-guard export-session ~/.pii-guard/sessions/<id>.json
    """
    try:
        import httpx  # noqa: F401
    except ImportError:
        raise click.ClickException(
            "httpx is required for the proxy. Install it: pip install httpx"
        )

    from pii_guard.proxy.server import ProxyServer

    session_path = Path(session) if session else None
    ProxyServer(
        port=port,
        presets=list(preset),
        extra_patterns=_parse_inline_patterns(pattern) if pattern else None,
        session_path=session_path,
        verbose=not quiet,
    ).start()


# ── install-hooks ─────────────────────────────────────────────────────────────

@cli.command("install-hooks")
@click.option(
    "--project", "-d",
    default=".",
    help="Project directory to install .claude/settings.json into. Default: current directory.",
)
@click.option("--global", "global_only", is_flag=True, help="Install hooks globally only (skip project settings.json).")
def install_hooks(project: str, global_only: bool):
    """Install Claude Code hooks so every session is PII-guarded automatically.

    \b
    Installs:
      ~/.pii-guard/hooks/post_read.py    — intercepts Read tool output
      ~/.pii-guard/hooks/post_bash.py    — intercepts Bash tool output
      <project>/.claude/settings.json   — wires hooks into Claude Code

    \b
    For Cursor, Aider, and other tools use the proxy instead:
      pii-guard proxy --port 8111 --preset dpdp
    """
    try:
        pkg_root = Path(__file__).parent.parent
        hooks_src = pkg_root / "integrations" / "claude-code" / "hooks"
        settings_src = pkg_root / "integrations" / "claude-code" / "settings.json"
        if not hooks_src.exists():
            raise FileNotFoundError
    except (FileNotFoundError, Exception):
        raise click.ClickException(
            "Could not find bundled hook files. "
            "Clone the repo and run from there: "
            "https://github.com/sunnypuli/pii-guard"
        )

    hook_dest = Path.home() / ".pii-guard" / "hooks"
    hook_dest.mkdir(parents=True, exist_ok=True)

    for hook_file in ["post_read.py", "post_bash.py"]:
        src = hooks_src / hook_file
        dst = hook_dest / hook_file
        shutil.copy2(src, dst)
        dst.chmod(0o755)
        click.secho(f"  ✓ {dst}", fg="green")

    if global_only:
        click.echo()
        click.secho("Hooks installed globally.", fg="cyan")
        _print_next_steps()
        return

    project_path = Path(project).resolve()
    claude_dir = project_path / ".claude"
    settings_dst = claude_dir / "settings.json"

    if settings_dst.exists():
        existing = json.loads(settings_dst.read_text(encoding="utf-8"))
        new_hooks = json.loads(settings_src.read_text(encoding="utf-8"))
        existing_hooks = existing.setdefault("hooks", {})
        for event, matchers in new_hooks.get("hooks", {}).items():
            existing_hooks.setdefault(event, [])
            existing_matchers = {m.get("matcher") for m in existing_hooks[event]}
            for matcher_block in matchers:
                if matcher_block.get("matcher") not in existing_matchers:
                    existing_hooks[event].append(matcher_block)
        settings_dst.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        click.secho(f"  ✓ Merged into existing {settings_dst}", fg="green")
    else:
        claude_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(settings_src, settings_dst)
        click.secho(f"  ✓ {settings_dst}", fg="green")

    click.echo()
    click.secho("pii-guard hooks installed.", fg="cyan", bold=True)
    _print_next_steps()


def _print_next_steps():
    click.echo()
    click.echo("Optional — add the behavioral layer:")
    click.secho(
        "  cp integrations/CLAUDE.md <your-project>/CLAUDE.md",
        fg="bright_white",
    )
    click.echo()
    click.echo("Set presets via env (default: dpdp):")
    click.secho(
        "  export PII_GUARD_PRESETS=dpdp,pci",
        fg="bright_white",
    )


# ── Utilities ─────────────────────────────────────────────────────────────────

def _line_num(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


if __name__ == "__main__":
    cli()
