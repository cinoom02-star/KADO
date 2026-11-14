"""Bounded real filesystem tools. No shell and no access outside the configured workspace."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Awaitable, Callable

Checkpoint = Callable[[], Awaitable[None]]
DENIED_DIRS = {".git", ".ssh", ".aws", ".venv", "venv", "node_modules", "__pycache__", "auth_info", "sessions", "session", ".wwebjs_auth", ".wwebjs_cache"}


class ToolLimit(RuntimeError):
    pass


def is_sensitive(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith(".env") or any(word in name for word in ("secret", "credential", "token", "password", "auth_info", "session")) or name.endswith((".pem", ".key", ".p12", ".pfx"))


def within(root: Path, candidate: Path) -> Path:
    root, candidate = root.resolve(), candidate.resolve()
    if not candidate.is_relative_to(root):
        raise PermissionError("Dosya yolu izinli çalışma alanının dışında")
    return candidate


class WorkspaceTools:
    def __init__(self, workspace_root: str | Path, data_dir: str | Path, max_files: int = 500,
                 max_file_bytes: int = 2 * 1024 * 1024):
        self.root = Path(workspace_root).resolve()
        self.artifacts = Path(data_dir).resolve() / "artifacts"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.max_files = max(1, int(max_files))
        self.max_file_bytes = max(1, int(max_file_bytes))

    def target(self, relative: str = ".") -> Path:
        if not isinstance(relative, str) or "\x00" in relative:
            raise PermissionError("Geçersiz yol")
        candidate = within(self.root, self.root / relative)
        rel = candidate.relative_to(self.root)
        if any(part.lower() in DENIED_DIRS or is_sensitive(Path(part)) for part in rel.parts):
            raise PermissionError("Gizli anahtar/oturum alanına erişim reddedildi")
        if not candidate.is_dir():
            raise FileNotFoundError("Taranacak klasör bulunamadı")
        return candidate

    def artifact(self, task_id: str, name: str = "report.json") -> Path:
        if not task_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in task_id):
            raise PermissionError("Geçersiz görev kimliği")
        requested_directory = self.artifacts / task_id
        if requested_directory.is_symlink():
            raise PermissionError("Görev kanıt klasörü sembolik bağlantı olamaz")
        directory = within(self.artifacts, requested_directory)
        directory.mkdir(parents=True, exist_ok=True)
        if name not in {"report.json", "qa.json", "audit.json", "response.json"}:
            raise PermissionError("Desteklenmeyen çıktı dosyası")
        if (directory / name).is_symlink():
            raise PermissionError("Kanıt dosyası sembolik bağlantı olamaz")
        return within(directory, directory / name)

    async def inventory(self, relative: str, checkpoint: Checkpoint, max_files: int | None = None,
                        max_file_bytes: int | None = None, max_total_bytes: int = 20 * 1024 * 1024) -> dict:
        max_files = self.max_files if max_files is None else max(1, int(max_files))
        max_file_bytes = self.max_file_bytes if max_file_bytes is None else max(1, int(max_file_bytes))
        target = self.target(relative)
        records, excluded = [], []
        total = 0
        scanned = 0
        for directory, dirs, files in os.walk(target, followlinks=False):
            await checkpoint()
            current = within(self.root, Path(directory))
            kept = []
            for name in sorted(dirs):
                item = current / name
                if name.lower() in DENIED_DIRS or is_sensitive(item) or item.is_symlink():
                    excluded.append({"path": str(item.relative_to(target)), "reason": "sensitive_or_symlink_directory"})
                else:
                    within(self.root, item)
                    kept.append(name)
            dirs[:] = kept
            for name in sorted(files):
                await checkpoint()
                scanned += 1
                if scanned > max_files:
                    raise ToolLimit(f"Dosya sınırı aşıldı ({max_files}); daha dar bir klasör seçin")
                item = current / name
                relative_path = item.relative_to(target).as_posix()
                if is_sensitive(item) or item.is_symlink():
                    excluded.append({"path": relative_path, "reason": "sensitive_or_symlink_file"})
                    continue
                actual = within(self.root, item)
                if not actual.is_file():
                    excluded.append({"path": relative_path, "reason": "not_regular_file"})
                    continue
                size = actual.stat().st_size
                if size > max_file_bytes:
                    excluded.append({"path": relative_path, "reason": "file_size_limit", "size": size})
                    continue
                total += size
                if total > max_total_bytes:
                    raise ToolLimit(f"Toplam okuma sınırı aşıldı ({max_total_bytes} bayt)")
                # Open exactly one bounded regular file; reject replacements that became symlinks.
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
                fd = os.open(actual, flags)
                with os.fdopen(fd, "rb") as handle:
                    data = handle.read(max_file_bytes + 1)
                if len(data) > max_file_bytes:
                    raise ToolLimit("Tarama sırasında büyüyen dosya sınırı aştı")
                records.append({"path": relative_path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return {"schema_version": 1, "workspace_path": target.relative_to(self.root).as_posix(),
                "files": records, "file_count": len(records), "total_bytes": sum(x["size"] for x in records),
                "excluded": excluded, "scope_note": "Yalnızca izinli, boyut sınırındaki dosyalar; güvenlik ve kod kalitesi analizi değildir."}

    def write_json(self, task_id: str, data: dict, name: str = "report.json") -> dict:
        path = self.artifact(task_id, name)
        encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".write-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"path": str(path), "name": name, "sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}

    async def verify(self, task_id: str, relative: str, checkpoint: Checkpoint) -> dict:
        path = self.artifact(task_id)
        if path.stat().st_size > 2 * 1024 * 1024:
            return {"passed": False, "checks": [{"name": "report_size", "passed": False}], "reason": "Kanıt dosyası aşırı büyük"}
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            return {"passed": False, "checks": [{"name": "valid_json", "passed": False}], "reason": "Rapor JSON değil"}
        if not isinstance(report, dict):
            return {"passed": False, "checks": [{"name": "report_object", "passed": False}], "reason": "Rapor JSON nesnesi olmalıdır"}
        fresh = await self.inventory(relative, checkpoint)
        checks = [
            {"name": "schema", "passed": report.get("schema_version") == 1},
            {"name": "scope", "passed": report.get("workspace_path") == fresh["workspace_path"]},
            {"name": "hashes_sizes_and_paths", "passed": report.get("files") == fresh["files"]},
            {"name": "file_count", "passed": report.get("file_count") == fresh["file_count"]},
            {"name": "total_bytes", "passed": report.get("total_bytes") == fresh["total_bytes"]},
            {"name": "exclusions_disclosed", "passed": report.get("excluded") == fresh["excluded"]},
        ]
        return {"passed": all(check["passed"] for check in checks), "checks": checks,
                "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "verified_file_count": fresh["file_count"], "reason": "Dosya kanıtları bağımsız yeniden hesaplandı"}
