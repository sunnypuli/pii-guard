"""
pii-guard CLI

Commands:
  scan        Detect PII and report what was found (read-only)
  tokenize    Replace PII with consistent tokens, write session key
  detokenize  Reverse tokenize using a session key file
  config      Manage configuration
"""

from __future__ import annotations

import importlib.resources
import shutil
import sys
from pathlib import Path

import click

from pii_guard.presets import AVAILABLE_PRESETS, load_presets
from pii_guard.scanner.engine import Scanner
from pii_guard.scanner.patterns import BASE_PATTERNS
from pii_guard.tokenizer.engine import detokenize as _detokenize
from pii_guard.tokenizer.engine import tokenize as _tokenize
from pii_guard.tokenizer.session import Session


# ── Shared helpers ────────────────────────────────────────────────────────────

def _build_scanner(presets: tuple[str, ...], no_base: bool) -> Scanner:
    patterns: dict[str, str] = {}
    if not no_base:
        patterns.update(BASE_PATTERNS)
    if presets:
        patterns.update(load_presets(list(presets)))
    if not patterns:
        raise click.UsageError("No patterns loaded. Specify at least one preset or remove --no-base.")
    return Scanner(patterns)


def _read_input(file: str) -> str:
    if file == "-":
        return sys.stdin.read()
    return Path(file).read_text(encoding="utf-8", errors="replace")


def _default_output_path(input_path: str, suffix: str = ".safe") -> str:
    p = Path(input_path)
    return str(p.with_stem(p.stem + suffix))


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
def scan(file: str, preset: tuple, no_base: bool, show_values: bool):
    """Scan FILE (or stdin) for PII and report findings.

    Exits with code 1 if PII is found, 0 if clean.
    """
    scanner = _build_scanner(preset, no_base)
    text = _read_input(file)
    matches = scanner.scan(text)

    if not matches:
        click.secho("✓ No PII detected.", fg="green")
        sys.exit(0)

    # Group by type
    by_type: dict[str, list] = {}
    for m in matches:
        by_type.setdefault(m.pii_type, []).append(m)

    source = file if file != "-" else "stdin"
    click.secho(f"\nFound {len(matches)} PII instance(s) in {source}:\n", fg="yellow", bold=True)

    for pii_type, type_matches in sorted(by_type.items()):
        count = len(type_matches)
        click.secho(f"  {pii_type:<20} {count:>4} instance(s)", fg="yellow")
        if show_values:
            for m in type_matches[:5]:           # cap at 5 to avoid flooding output
                click.echo(f"    line {_line_num(text, m.start):>4}: {m.value!r}")
            if count > 5:
                click.echo(f"    … and {count - 5} more")

    click.echo()
    click.echo("Run `pii-guard tokenize` to replace with tokens before analysis.")
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
def tokenize(
    file: str,
    preset: tuple,
    no_base: bool,
    output: str | None,
    session: str | None,
    quiet: bool,
):
    """Tokenize PII in FILE (or stdin). Writes safe output + session key.

    The session key file maps tokens back to original values.
    It never leaves your machine.
    """
    scanner = _build_scanner(preset, no_base)
    text = _read_input(file)

    sess = Session.load(session) if session else Session.new()
    tokenized, matches = _tokenize(text, scanner, sess)

    if not matches:
        if not quiet:
            click.secho("✓ No PII detected — file is already clean.", fg="green")
        if output and output != "-":
            Path(output).write_text(tokenized, encoding="utf-8")
        else:
            click.echo(tokenized, nl=False)
        return

    sess.save()

    # Write tokenized output
    if file == "-" or output == "-":
        click.echo(tokenized, nl=False)
    else:
        out_path = output or _default_output_path(file)
        Path(out_path).write_text(tokenized, encoding="utf-8")

    if not quiet:
        # Summary
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
            replaced = sum(
                text.count(tok) for tok in sess.tokens
            )
            click.secho(f"✓ Replaced {replaced} token(s). Output: {out_path}", fg="green")


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

    Then copy integrations/CLAUDE.md into your project to add the behavioral layer.
    """
    # Locate the integrations directory bundled with the package
    try:
        pkg_root = Path(__file__).parent.parent
        hooks_src = pkg_root / "integrations" / "claude-code" / "hooks"
        settings_src = pkg_root / "integrations" / "claude-code" / "settings.json"
        if not hooks_src.exists():
            raise FileNotFoundError
    except (FileNotFoundError, Exception):
        raise click.ClickException(
            "Could not find bundled hook files. "
            "Try cloning the repo and running from there: "
            "https://github.com/your-org/pii-guard"
        )

    # Install hooks to ~/.pii-guard/hooks/
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

    # Install settings.json into project .claude/
    project_path = Path(project).resolve()
    claude_dir = project_path / ".claude"
    settings_dst = claude_dir / "settings.json"

    if settings_dst.exists():
        # Merge hooks block into existing settings.json
        import json as _json
        existing = _json.loads(settings_dst.read_text(encoding="utf-8"))
        new_hooks = _json.loads(settings_src.read_text(encoding="utf-8"))

        existing_hooks = existing.setdefault("hooks", {})
        for event, matchers in new_hooks.get("hooks", {}).items():
            existing_hooks.setdefault(event, [])
            existing_matchers = {m.get("matcher") for m in existing_hooks[event]}
            for matcher_block in matchers:
                if matcher_block.get("matcher") not in existing_matchers:
                    existing_hooks[event].append(matcher_block)

        settings_dst.write_text(
            _json.dumps(existing, indent=2, ensure_ascii=False),
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
