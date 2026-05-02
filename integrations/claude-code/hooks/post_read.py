#!/usr/bin/env python3
"""
Claude Code PostToolUse hook — fires after the Read tool.

Receives tool result JSON on stdin, tokenizes any PII in the file content,
writes the token→value session key to ~/.pii-guard/sessions/, then outputs
the modified tool result JSON so Claude only ever sees tokenized content.

All tool calls within the same Claude Code session share one session file
(keyed on session_id), so a single detokenize pass restores everything.

Install: pii-guard install-hooks
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PRESETS = os.environ.get("PII_GUARD_PRESETS", "dpdp").split(",")
_ENABLED = os.environ.get("PII_GUARD_ENABLED", "1") not in ("0", "false", "no")


def _debug(msg: str) -> None:
    with open("/tmp/pii_guard_debug.log", "a") as f:
        f.write(msg + "\n")


def _extract_content(tool_response) -> str | None:
    """Extract file content from Claude Code's tool_response payload."""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, dict):
        # Claude Code Read format: {"type":"text","file":{"content":"...",...}}
        file_block = tool_response.get("file")
        if isinstance(file_block, dict):
            c = file_block.get("content")
            if isinstance(c, str):
                return c
        # Fallback: flat content key
        c = tool_response.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return "\n".join(
                block.get("text", "") for block in c if isinstance(block, dict)
            )
    return None


def _set_content(data: dict, new_content: str) -> None:
    tr = data["tool_response"]
    if isinstance(tr, str):
        data["tool_response"] = new_content
    elif isinstance(tr, dict):
        file_block = tr.get("file")
        if isinstance(file_block, dict):
            data["tool_response"]["file"]["content"] = new_content
        elif isinstance(tr.get("content"), list):
            data["tool_response"]["content"] = [{"type": "text", "text": new_content}]
        else:
            data["tool_response"]["content"] = new_content


def main():
    raw = sys.stdin.read()
    _debug(f"[pii-guard hook fired] len={len(raw)} enabled={_ENABLED}")

    if not _ENABLED:
        sys.stdout.write(raw)
        return

    try:
        data = json.loads(raw)
        _debug(f"[pii-guard] keys={list(data.keys())} tool_result_type={type(data.get('tool_result')).__name__}")
    except json.JSONDecodeError as e:
        _debug(f"[pii-guard] JSON decode error: {e} raw[:200]={raw[:200]}")
        sys.stdout.write(raw)
        return

    tr = data.get("tool_response")
    _debug(f"[pii-guard] tool_response={json.dumps(tr)[:500] if tr is not None else 'MISSING'}")
    tool_output = _extract_content(tr)
    _debug(f"[pii-guard] extracted content len={len(tool_output) if tool_output else None}")
    if not tool_output:
        sys.stdout.write(json.dumps(data))
        return

    try:
        from pii_guard.presets import load_presets
        from pii_guard.scanner.engine import Scanner
        from pii_guard.scanner.patterns import BASE_PATTERNS
        from pii_guard.tokenizer.engine import tokenize
        from pii_guard.tokenizer.session import Session

        patterns = {**BASE_PATTERNS, **load_presets(_PRESETS)}
        # Load custom patterns from ~/.pii-guard/config.yaml if present
        try:
            import yaml
            cfg_path = Path.home() / ".pii-guard" / "config.yaml"
            if cfg_path.exists():
                cfg = yaml.safe_load(cfg_path.read_text()) or {}
                patterns.update(cfg.get("custom_patterns") or {})
        except Exception:
            pass
        scanner = Scanner(patterns)

        if not scanner.has_pii(tool_output):
            _debug(f"[pii-guard] no PII found, passing through")
            sys.stdout.write(json.dumps(data))
            return

        # Use a per-Claude-session file so all reads share one key
        session_id = data.get("session_id", "")
        session_dir = Path.home() / ".pii-guard" / "sessions"
        if session_id:
            session_path = session_dir / f"claude-{session_id}.json"
            session = Session.load(session_path)
        else:
            session = Session.new(session_dir)

        tokenized, matches = tokenize(tool_output, scanner, session)
        session.save()
        _debug(f"[pii-guard] TOKENIZED {len(matches)} matches: {[m.pii_type for m in matches[:5]]}")

        notice = (
            f"[pii-guard] {len(matches)} PII instance(s) tokenised "
            f"(session: {session.path}). "
            "Tokens like [EMAIL_1] represent real values stored locally.\n\n"
        )
        _set_content(data, notice + tokenized)
        sys.stdout.write(json.dumps(data))

    except ImportError:
        warning = "[pii-guard] WARNING: package not installed — PII passed through unfiltered.\n\n"
        _set_content(data, warning + tool_output)
        sys.stdout.write(json.dumps(data))
    except Exception as e:
        sys.stdout.write(json.dumps(data))
        print(f"[pii-guard] hook error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
