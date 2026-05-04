"""
pii-guard proxy server.

Sits between your application and the LLM API. Tokenizes PII in prompts
before they leave your machine, detokenizes responses before they reach
your app. Drop-in: just change the base URL.

Usage:
    pii-guard proxy --port 8111 --preset dpdp

Then in your app:
    ANTHROPIC_BASE_URL=http://localhost:8111          # Anthropic SDK
    OPENAI_BASE_URL=http://localhost:8111/openai/v1   # OpenAI-compat SDK
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx

from pii_guard.scanner.engine import Scanner
from pii_guard.scanner.patterns import BASE_PATTERNS
from pii_guard.presets import load_presets
from pii_guard.tokenizer.engine import tokenize as _tokenize
from pii_guard.tokenizer.session import Session

_ANTHROPIC_BASE = "https://api.anthropic.com"
_OPENAI_BASE    = "https://api.openai.com"


# ── Text extraction / injection helpers ──────────────────────────────────────

def _extract_texts(data: Any) -> list[str]:
    """Recursively pull all user-visible text strings out of a request body."""
    texts: list[str] = []
    if isinstance(data, str):
        texts.append(data)
    elif isinstance(data, list):
        for item in data:
            texts.extend(_extract_texts(item))
    elif isinstance(data, dict):
        for key, val in data.items():
            if key in ("text", "content", "input", "system"):
                texts.extend(_extract_texts(val))
    return texts


_CONTENT_KEYS = {"text", "content", "input", "system", "query", "prompt"}

def _tokenize_in_place(data: Any, scanner: Scanner, session: Session, _parent_key: str = "") -> tuple[Any, int]:
    """Walk the request body and tokenize PII in every text field. Returns modified data + match count."""
    total = 0
    if isinstance(data, str):
        # Only tokenize if parent key is a known content-carrying field
        if _parent_key in _CONTENT_KEYS or not _parent_key:
            tokenized, matches = _tokenize(data, scanner, session)
            return tokenized, len(matches)
        return data, 0
    elif isinstance(data, list):
        result = []
        for item in data:
            new_item, n = _tokenize_in_place(item, scanner, session, _parent_key)
            result.append(new_item)
            total += n
        return result, total
    elif isinstance(data, dict):
        result = {}
        for key, val in data.items():
            new_val, n = _tokenize_in_place(val, scanner, session, key)
            result[key] = new_val
            total += n
        return result, total
    return data, 0


def _detokenize_in_place(data: Any, session: Session) -> Any:
    """Walk response body and detokenize all text fields."""
    if isinstance(data, str):
        return session.detokenize(data)
    elif isinstance(data, list):
        return [_detokenize_in_place(item, session) for item in data]
    elif isinstance(data, dict):
        return {k: _detokenize_in_place(v, session) if k in ("text", "content", "output") else v
                for k, v in data.items()}
    return data


def _detokenize_sse_line(line: str, session: Session) -> str:
    """Detokenize a single SSE data line."""
    if not line.startswith("data: "):
        return line
    payload = line[6:]
    if payload.strip() in ("[DONE]", ""):
        return line
    try:
        obj = json.loads(payload)
        obj = _detokenize_in_place(obj, session)
        return "data: " + json.dumps(obj)
    except Exception:
        return line


# ── Request handler ───────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    # Set by ProxyServer before starting
    scanner: Scanner
    session: Session
    session_lock: threading.Lock
    verbose: bool

    def log_message(self, fmt, *args):
        if self.server.verbose:
            print(f"[pii-guard proxy] {fmt % args}", flush=True)

    def _target_url(self) -> str:
        path = self.path
        if path.startswith("/openai"):
            return _OPENAI_BASE + path[len("/openai"):]
        return _ANTHROPIC_BASE + path

    def _forward_headers(self) -> dict[str, str]:
        skip = {"host", "content-length", "transfer-encoding"}
        return {k: v for k, v in self.headers.items() if k.lower() not in skip}

    def do_GET(self):
        self._proxy(method="GET", body=None)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        self._proxy(method="POST", body=raw)

    def _proxy(self, method: str, body: bytes | None):
        target = self._target_url()
        headers = self._forward_headers()
        is_streaming = False
        match_count = 0

        # Tokenize request body
        if body:
            try:
                data = json.loads(body)
                is_streaming = bool(data.get("stream", False))
                with self.server.session_lock:
                    data, match_count = _tokenize_in_place(data, self.server.scanner, self.server.session)
                    if match_count:
                        self.server.session.save()
                body = json.dumps(data).encode()
                headers["Content-Length"] = str(len(body))
                if match_count and self.server.verbose:
                    print(f"[pii-guard proxy] tokenised {match_count} PII instance(s) in request", flush=True)
            except Exception:
                pass

        try:
            if is_streaming:
                self._proxy_streaming(method, target, headers, body)
            else:
                self._proxy_buffered(method, target, headers, body)
        except Exception as e:
            self.send_error(502, f"Proxy error: {e}")

    def _proxy_buffered(self, method, target, headers, body):
        with httpx.Client(timeout=120) as client:
            resp = client.request(method, target, headers=headers, content=body)

        # Detokenize response
        resp_body = resp.content
        try:
            data = json.loads(resp_body)
            with self.server.session_lock:
                data = _detokenize_in_place(data, self.server.session)
            resp_body = json.dumps(data).encode()
        except Exception:
            pass

        self.send_response(resp.status_code)
        for k, v in resp.headers.items():
            if k.lower() not in ("content-length", "transfer-encoding"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)

    def _proxy_streaming(self, method, target, headers, body):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        with httpx.Client(timeout=120) as client:
            with client.stream(method, target, headers=headers, content=body) as resp:
                buffer = b""
                for chunk in resp.iter_bytes():
                    buffer += chunk
                    while b"\n" in buffer:
                        line_bytes, buffer = buffer.split(b"\n", 1)
                        line = line_bytes.decode("utf-8", errors="replace")
                        with self.server.session_lock:
                            line = _detokenize_sse_line(line, self.server.session)
                        out = (line + "\n").encode()
                        self.wfile.write(f"{len(out):x}\r\n".encode())
                        self.wfile.write(out + b"\r\n")
                        self.wfile.flush()

        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


# ── Public API ─────────────────────────────────────────────────────────────────

class ProxyServer:
    def __init__(
        self,
        port: int = 8111,
        presets: list[str] | None = None,
        extra_patterns: dict[str, str] | None = None,
        session_path: Path | None = None,
        verbose: bool = True,
    ):
        self.port = port

        patterns = {**BASE_PATTERNS, **load_presets(presets or ["dpdp"])}
        if extra_patterns:
            patterns.update(extra_patterns)
        # Load custom patterns from config file
        try:
            import yaml
            cfg = Path.home() / ".pii-guard" / "config.yaml"
            if cfg.exists():
                patterns.update((yaml.safe_load(cfg.read_text()) or {}).get("custom_patterns") or {})
        except Exception:
            pass

        self.scanner = Scanner(patterns)
        self.session = Session.load(session_path) if session_path else Session.new()
        self.verbose = verbose

        # Attach to handler class via server instance attributes
        self._server = HTTPServer(("127.0.0.1", port), _Handler)
        self._server.scanner = self.scanner
        self._server.session = self.session
        self._server.session_lock = threading.Lock()
        self._server.verbose = verbose

    def start(self):
        if self.verbose:
            print(f"[pii-guard proxy] Listening on http://localhost:{self.port}", flush=True)
            print(f"[pii-guard proxy] Session key: {self.session.path}", flush=True)
            print(f"[pii-guard proxy] Active patterns: {len(self._server.scanner.active_types)}", flush=True)
            print(f"[pii-guard proxy] Set ANTHROPIC_BASE_URL=http://localhost:{self.port}", flush=True)
            print(f"[pii-guard proxy] Ctrl+C to stop\n", flush=True)
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            self._server.session.save()
            print(f"\n[pii-guard proxy] Stopped. Session saved to {self.session.path}", flush=True)
