#!/usr/bin/env python3
"""
Claude Code PostToolUse hook — fires after the Bash tool.

Same logic as post_read.py: tokenise PII in command output before
it enters Claude's context window.

All tool calls within the same Claude Code session share one session file
(keyed on session_id), so a single detokenize pass restores everything.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PRESETS = os.environ.get("PII_GUARD_PRESETS", "dpdp").split(",")
_ENABLED = os.environ.get("PII_GUARD_ENABLED", "1") not in ("0", "false", "no")
_MAX_SCAN_CHARS = int(os.environ.get("PII_GUARD_MAX_CHARS", 200_000))


def _extract_content(tool_result) -> str | None:
    if isinstance(tool_result, str):
        return tool_result
    if isinstance(tool_result, dict):
        c = tool_result.get("content")
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
        if isinstance(tr.get("content"), list):
            data["tool_response"]["content"] = [{"type": "text", "text": new_content}]
        else:
            data["tool_response"]["content"] = new_content


def main():
    raw = sys.stdin.read()

    if not _ENABLED:
        sys.stdout.write(raw)
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.stdout.write(raw)
        return

    tool_output = _extract_content(data.get("tool_response"))
    if not tool_output:
        sys.stdout.write(json.dumps(data))
        return

    scan_target = tool_output[:_MAX_SCAN_CHARS]

    try:
        from pii_guard.presets import load_presets
        from pii_guard.scanner.engine import Scanner
        from pii_guard.scanner.patterns import BASE_PATTERNS
        from pii_guard.tokenizer.engine import tokenize
        from pii_guard.tokenizer.session import Session

        patterns = {**BASE_PATTERNS, **load_presets(_PRESETS)}
        try:
            import yaml
            cfg_path = Path.home() / ".pii-guard" / "config.yaml"
            if cfg_path.exists():
                cfg = yaml.safe_load(cfg_path.read_text()) or {}
                patterns.update(cfg.get("custom_patterns") or {})
        except Exception:
            pass
        scanner = Scanner(patterns)

        if not scanner.has_pii(scan_target):
            sys.stdout.write(json.dumps(data))
            return

        session_id = data.get("session_id", "")
        session_dir = Path.home() / ".pii-guard" / "sessions"
        if session_id:
            session_path = session_dir / f"claude-{session_id}.json"
            session = Session.load(session_path)
        else:
            session = Session.new(session_dir)

        tokenized, matches = tokenize(scan_target, scanner, session)
        session.save()

        notice = (
            f"[pii-guard] {len(matches)} PII instance(s) tokenised in bash output "
            f"(session: {session.path}).\n\n"
        )
        remainder = tool_output[_MAX_SCAN_CHARS:]
        _set_content(data, notice + tokenized + remainder)
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
