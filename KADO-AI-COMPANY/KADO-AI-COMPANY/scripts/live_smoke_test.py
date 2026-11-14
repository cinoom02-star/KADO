"""Launch an isolated real HTTP server, submit through SDK, verify restart history.

Never accesses existing KADO or WhatsApp. Optional --postgres tests a disposable
Docker PostgreSQL instance; no password is printed or written to the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kado_bridge import KadoClient
from kado_bridge.kado_task_dispatcher import KadoTaskDispatcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    container = None
    proc = None
    report = {"mode": "live_http_sdk", "database": "postgresql16" if args.postgres else "sqlite",
              "existing_kado_connected": False, "whatsapp_tested": False}
    with tempfile.TemporaryDirectory(prefix="kado-live-") as temp:
        scratch = Path(temp)
        workspace = scratch / "workspace"
        workspace.mkdir()
        source = "KADO gerçek HTTP uçtan uca doğrulama\n"
        (workspace / "proof.txt").write_text(source, encoding="utf-8")
        token = secrets.token_urlsafe(32)
        env = {**os.environ, "KADO_COMPANY_ROOT": str(ROOT), "KADO_DATA_DIR": str(scratch / "data"),
               "KADO_WORKSPACE_ROOT": str(workspace), "KADO_API_TOKEN": token,
               "OLLAMA_MODEL": "", "GEMINI_API_KEY": "", "MODEL_PROVIDER": "unconfigured"}
        database_url = "sqlite:///" + (scratch / "history.sqlite3").as_posix()
        try:
            if args.postgres:
                password = secrets.token_urlsafe(24)
                container = "kado-verification-" + secrets.token_hex(4)
                docker_env = {**os.environ, "POSTGRES_PASSWORD": password}
                docker = ["docker", "--host=unix:///var/run/docker.sock"]
                subprocess.run(docker + ["run", "--rm", "-d", "--name", container,
                               "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_USER=kado_verify",
                               "-e", "POSTGRES_DB=kado_verify", "-p", "127.0.0.1::5432",
                               "postgres:16-alpine"], env=docker_env, check=True, capture_output=True)
                port_info = subprocess.check_output(docker + ["port", container, "5432/tcp"], text=True).strip()
                db_port = port_info.rsplit(":", 1)[1]
                for _ in range(60):
                    check = subprocess.run(docker + ["exec", container, "pg_isready", "-U", "kado_verify", "-d", "kado_verify"], capture_output=True)
                    if check.returncode == 0:
                        break
                    time.sleep(0.25)
                else:
                    raise RuntimeError("Disposable PostgreSQL not ready")
                database_url = f"postgresql+psycopg://kado_verify:{password}@127.0.0.1:{db_port}/kado_verify"
            env["DATABASE_URL"] = database_url
            with socket.socket() as free:
                free.bind(("127.0.0.1", 0))
                port = free.getsockname()[1]
            url = f"http://127.0.0.1:{port}"
            command = [sys.executable, "-m", "uvicorn", "company.api:app", "--app-dir", str(ROOT / "backend"),
                       "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]

            def start_server():
                process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("HTTP process exited during startup")
                    try:
                        with KadoClient(url, token, timeout=1, retries=0) as probe:
                            if probe.health()["status"] == "ok":
                                return process
                    except Exception:
                        time.sleep(0.1)
                process.terminate()
                process.wait(timeout=10)
                raise TimeoutError("HTTP server startup timeout")

            proc = start_server()
            with KadoClient(url, token) as client:
                assert len(client.agents()) == 35
                task = client.create_task("HTTP ile gerçek dosya kanıtı", input={"path": "."}, idempotency_key="live-proof")
                assert client.create_task("HTTP ile gerçek dosya kanıtı", input={"path": "."}, idempotency_key="live-proof")["id"] == task["id"]
                final = KadoTaskDispatcher(client).wait(task["id"], timeout=20, poll_interval=0.1)
                assert final["status"] == "APPROVED", final["status"]
                evidence = Path(final["result"]["report"]["path"]).read_bytes()
                inventory = json.loads(evidence)
                assert inventory["files"][0]["sha256"] == hashlib.sha256(source.encode()).hexdigest()
                assert hashlib.sha256(evidence).hexdigest() == final["result"]["report"]["sha256"]
                events = client.events()
                (args.output / "proof.txt").write_text(source, encoding="utf-8")
                tools = client._client.get("/api/tool-calls", params={"task_id": task["id"]}).json()
                (args.output / "tool-calls.json").write_text(json.dumps(tools, ensure_ascii=False, indent=2), encoding="utf-8")
                for name in ("report.json", "qa.json", "audit.json"):
                    (args.output / name).write_bytes((Path(final["result"]["report"]["path"]).parent / name).read_bytes())
                # Static HTTP verifies built frontend is served; browser rendering is separate.
                index = client._client.get("/")
                assert index.status_code == 200 and "<div id=\"root\">" in index.text
                report.update(task_id=task["id"], status=final["status"], agents=35,
                              event_count=len(events), report_sha256=final["result"]["report"]["sha256"],
                              source_sha256=inventory["files"][0]["sha256"], static_frontend_http=True,
                              duplicate_submission_suppressed=True)
                (args.output / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
            proc.terminate()
            proc.wait(timeout=10)
            proc = start_server()
            with KadoClient(url, token) as client:
                restored = client.task(task["id"])
                assert restored["status"] == "APPROVED" and restored["result"] == final["result"]
                assert len(client.events()) >= len(events)
                report["restart_history_preserved"] = True
            report["passed"] = True
            (args.output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False))
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
            if container:
                subprocess.run(["docker", "--host=unix:///var/run/docker.sock", "rm", "-f", container], capture_output=True)


if __name__ == "__main__":
    main()
