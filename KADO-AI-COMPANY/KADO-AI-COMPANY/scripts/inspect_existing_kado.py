"""Read-only inventory; never reads .env/session/auth stores or emits source text.

Run from a copy of this new sidecar, not from an existing KADO folder. Report
output is stdout, so the caller explicitly chooses its destination.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone


SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", "sessions", "session", "auth", "auth_info",
        "auth_info_baileys", ".wwebjs_auth", ".wwebjs_cache", "credentials", "secrets", "media", "recordings", "cache"}
CODE_EXTENSIONS = {".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".bat", ".ps1"}
SIGNATURES = {
    "http_api": re.compile(r"FastAPI\(|Flask\(|express\(|createServer\("),
    "whatsapp_puppeteer": re.compile(r"whatsapp-web\.js|puppeteer", re.I),
    "whatsapp_baileys": re.compile(r"baileys|makeWASocket|baileys-caller", re.I),
    "voice_elevenlabs": re.compile(r"elevenlabs|ElevenLabs", re.I),
    "voice_local": re.compile(r"piper|whisper|vosk", re.I),
    "pcm_audio": re.compile(r"16000|Int16Array|Float32Array|pcm_s16le"),
    "whatsapp_call_candidate": re.compile(r"startCall|answerCall|offerCall|call\.offer|incoming.call|barge.in", re.I),
    "llm_ollama": re.compile(r"ollama|11434", re.I),
    "llm_gemini": re.compile(r"generativeai|generativelanguage|gemini", re.I),
}


def safe_name(name: str):
    lower = name.casefold()
    return (lower not in SKIP and not lower.startswith(".env") and
            not any(part in lower for part in ("secret", "credential", "session", "token", "auth_info")) and
            not lower.endswith((".pem", ".key", ".sqlite", ".sqlite3", ".db", ".log")))


def inspect_root(root: str | Path, *, max_files: int = 4000, max_file_bytes: int = 262144):
    root = Path(root)
    result = {"root": str(root), "exists": root.is_dir(), "files": [], "skipped": 0, "errors": [],
              "truncated": False, "interpretation": "Signatures identify candidates only; no runtime capability has been verified."}
    if not root.is_dir():
        result["errors"].append("ROOT_NOT_FOUND")
        return result
    resolved = root.resolve()
    for directory, dirs, files in os.walk(root, followlinks=False):
        before = len(dirs)
        dirs[:] = [name for name in sorted(dirs) if safe_name(name) and not (Path(directory) / name).is_symlink()]
        result["skipped"] += before - len(dirs)
        for name in sorted(files):
            path = Path(directory) / name
            if not safe_name(name) or path.suffix.casefold() not in CODE_EXTENSIONS or path.is_symlink():
                result["skipped"] += 1
                continue
            if len(result["files"]) >= max_files:
                result["truncated"] = True
                return result
            try:
                path.resolve().relative_to(resolved)
                size = path.stat().st_size
                if size > max_file_bytes:
                    result["skipped"] += 1
                    continue
                raw = path.read_bytes()
                if len(raw) > max_file_bytes:
                    result["skipped"] += 1
                    continue
                text = raw.decode("utf-8-sig", errors="replace")
                syntax = {"status": "not_checked"}
                if path.suffix.casefold() == ".py":
                    try:
                        ast.parse(text, filename=str(path.relative_to(root)))
                        syntax = {"status": "valid", "scope": "syntax_only_not_runtime"}
                    except SyntaxError as exc:
                        syntax = {"status": "invalid", "error_type": type(exc).__name__, "line": exc.lineno}
                signatures = {key: len(pattern.findall(text)) for key, pattern in SIGNATURES.items() if pattern.search(text)}
                result["files"].append({"path": str(path.relative_to(root)), "bytes": len(raw),
                                        "sha256": hashlib.sha256(raw).hexdigest(), "candidate_signatures": signatures, "syntax": syntax,
                                        "runtime_status": "unverified"})
            except (OSError, ValueError) as exc:
                result["errors"].append({"path": str(path.relative_to(root)), "error": type(exc).__name__})
    return result


def main():
    parser = argparse.ArgumentParser(description="Read-only KADO source candidate inventory. Never verifies WhatsApp calls.")
    parser.add_argument("paths", nargs="*", default=[r"C:\KADO\kado", r"C:\KADO\KADO-AJANLAR"])
    args = parser.parse_args()
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "mode": "READ_ONLY",
              "existing_files_modified": False, "source_contents_exported": False,
              "runtime_tests_performed": False, "roots": [inspect_root(path) for path in args.paths]}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
