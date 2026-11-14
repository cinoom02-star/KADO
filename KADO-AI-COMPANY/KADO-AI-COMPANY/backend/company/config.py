"""Local configuration. This module never edits the existing KADO installation."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path, PureWindowsPath
import secrets


ROOT = Path(__file__).resolve().parents[2]


def _protected_windows_path(path: str | Path) -> bool:
    candidate = PureWindowsPath(str(path))
    protected = (PureWindowsPath(r"C:\KADO\kado"), PureWindowsPath(r"C:\KADO\KADO-AJANLAR"))
    return any(candidate == root or root in candidate.parents for root in protected)


@dataclass
class Settings:
    project_root: Path = ROOT
    data_dir: Path | None = None
    workspace_root: Path | None = None
    database_url: str = ""
    api_token: str = ""
    host: str = "127.0.0.1"
    port: int = 8765
    worker_concurrency: int = 1
    max_retries: int = 2
    task_timeout: float = 120.0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    model_provider: str = "unconfigured"
    cors_origins: list[str] = field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765", "http://localhost:8765"])
    max_files: int = 500
    max_file_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()
        self.data_dir = Path(self.data_dir or self.project_root / "data").resolve()
        self.workspace_root = Path(self.workspace_root or self.data_dir / "workspace").resolve()
        if _protected_windows_path(self.data_dir) or _protected_windows_path(self.workspace_root):
            raise ValueError("Mevcut KADO klasörleri veri veya görev çalışma alanı olarak kullanılamaz.")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        if not self.database_url:
            self.database_url = "sqlite:///" + (self.data_dir / "company.sqlite3").as_posix()
        if not self.api_token:
            token_path = self.data_dir / "api-token.txt"
            if token_path.exists():
                self.api_token = token_path.read_text(encoding="utf-8").strip()
                if len(self.api_token) < 24:
                    raise ValueError("Yerel API anahtarı en az 24 karakter olmalıdır.")
            else:
                self.api_token = secrets.token_urlsafe(32)
                # Exclusive creation avoids accidentally replacing a token on restart.
                try:
                    with token_path.open("x", encoding="utf-8") as token_file:
                        token_file.write(self.api_token + "\n")
                    token_path.chmod(0o600)
                except FileExistsError:
                    self.api_token = token_path.read_text(encoding="utf-8").strip()
        if len(self.api_token) < 24:
            raise ValueError("API anahtarı en az 24 karakter olmalıdır.")
        self.worker_concurrency = max(1, min(int(self.worker_concurrency), 8))
        self.max_retries = max(0, min(int(self.max_retries), 10))
        self.task_timeout = max(1.0, min(float(self.task_timeout), 3600.0))

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env", override=False)
        except ImportError:
            pass
        env = os.environ
        return cls(
            project_root=Path(env.get("KADO_COMPANY_ROOT", str(ROOT))),
            data_dir=Path(env["KADO_DATA_DIR"]) if env.get("KADO_DATA_DIR") else None,
            workspace_root=Path(env["KADO_WORKSPACE_ROOT"]) if env.get("KADO_WORKSPACE_ROOT") else None,
            database_url=env.get("DATABASE_URL", ""),
            api_token=env.get("KADO_API_TOKEN", ""),
            host=env.get("KADO_HOST", "127.0.0.1"),
            port=int(env.get("KADO_PORT", "8765")),
            worker_concurrency=int(env.get("KADO_WORKER_CONCURRENCY", "1")),
            max_retries=int(env.get("KADO_MAX_RETRIES", "2")),
            task_timeout=float(env.get("KADO_TASK_TIMEOUT", "120")),
            ollama_base_url=env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            ollama_model=env.get("OLLAMA_MODEL", ""),
            gemini_api_key=env.get("GEMINI_API_KEY", ""),
            gemini_model=env.get("GEMINI_MODEL", "gemini-2.5-flash"),
            model_provider=env.get("MODEL_PROVIDER", "unconfigured"),
            cors_origins=[s.strip() for s in env.get("KADO_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8765,http://localhost:8765").split(",") if s.strip()],
        )
