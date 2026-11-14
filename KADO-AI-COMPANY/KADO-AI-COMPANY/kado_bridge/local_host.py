"""Run the inspected existing KADO with in-memory company tools.

Only standard library imports: the existing KADO venv is never installed into.
No original KADO, memory, voice or WhatsApp source/session file is changed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import threading
import time
from urllib import error, parse, request
import uuid
import weakref

VERSION = "0.1.1"
REVIEWED_MAIN_SHA256 = "9c952052a8b02e87a7176064ba00c7e0ddd40ef8cc1eef8145e3f6dea60118a6"
PREFIX = "company_"


def declaration(name, description, properties=None, required=None):
    return {"name": name, "description": description,
            "parameters": {"type": "OBJECT", "properties": properties or {}, "required": required or []}}


TEXT = {"type": "STRING"}
TOOLS = [
    declaration("company_connection_status", "Yeni 35 ajanlı şirket motoruna gerçek bağlantıyı ve desteklenen yetenekleri denetle."),
    declaration("company_list_agents", "Yeni şirketteki mevcut CEO KADO, dört yönetici ve 30 uzman rolünü listele. Roller sürekli çalışan modeller değildir."),
    declaration("company_workspace_audit", "Yeni şirkete gerçek dosya envanteri ve bağımsız QA/denetim görevi ver. Yol sadece şirketin izinli workspace alanındadır; kod kalitesi analizi değildir.",
                {"title": TEXT, "path": TEXT}, ["title"]),
    declaration("company_generate_text", "Seçilen uzmana yapılandırılmış Ollama/Gemini üzerinden gerçek metin üretim görevi ver. Model yoksa BLOCKED; çıktı insan incelemesi gerektirir. Video, internet araştırması veya yayın işlemi yapmaz.",
                {"title": TEXT, "prompt": TEXT, "agent_id": TEXT, "provider": {"type": "STRING", "enum": ["ollama", "gemini"]}}, ["title", "prompt"]),
    declaration("company_get_task", "Yeni şirketin UUID görev numarasıyla gerçek durum, sonuç ve denetim kanıtlarını oku.", {"task_id": TEXT}, ["task_id"]),
    declaration("company_recent_tasks", "Yeni şirket motorunun son görevlerini oku."),
    declaration("company_control_task", "Yeni şirket görevini duraklat, devam ettir, iptal et veya sınırlı yeniden dene. İnsan onayı bu araçla verilemez; onay panelde yapılır.",
                {"task_id": TEXT, "action": {"type": "STRING", "enum": ["pause", "resume", "cancel", "retry"]}}, ["task_id", "action"]),
]

INSTRUCTION = """
[MEVCUT KADO — YENİ 35 AJANLI ŞİRKET BAĞLANTISI]
Sen mevcut KADO'sun; kimliğin, hafızan, sesin ve önceki araçların korunur.
Yeni AI Company için company_ araçlarını kullan. Eski create_agent_task,
start_agent_task ve kado_* araçları önceki KADO-AJANLAR sistemine aittir;
yeni şirket göreviyle eski sayısal görev numaralarını karıştırma.
Önce company_connection_status ile bağlantıyı kontrol et. Görev bazlı çalış;
35 ağır modelin aynı anda çalıştığını iddia etme. company_workspace_audit
izinli şirket çalışma alanında gerçek dosya kanıtı üretir. Metin görevleri
gerçek sağlayıcı gerektirir, içerik doğruluğu için insan onayı gerekir.
PENDING/IN_PROGRESS tamamlandı demek değildir. BLOCKED/FAILED durumlarını
açıkça söyle. Sonuçları company_get_task ile oku; UUID'yi koru.
Dosya silme, ödeme, yayınlama ve canlı dağıtım bu araçlarda yoktur.
WhatsApp araması, internet araştırması, video veya sosyal yayınlama
yapılmış gibi konuşma. Bu bağlantı WhatsApp taşımasını doğrulamaz.
"""


class CompanyError(RuntimeError):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CompanyError("Yerel API yönlendirmesi reddedildi; anahtar başka adrese gönderilmedi.")


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".kado-host-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class CompanyClient:
    def __init__(self, company_root: Path, url="http://127.0.0.1:8765", token=None, state_path=None):
        self.root = Path(company_root).resolve()
        endpoint = parse.urlsplit(url)
        if endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"} or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or endpoint.path not in {"", "/"}:
            raise CompanyError("Bu yerel adaptör yalnızca loopback şirket URL'sini kabul eder.")
        self.url = url.rstrip("/")
        local = {}
        if token is None and (self.root / ".env").is_file():
            for line in (self.root / ".env").read_text(encoding="utf-8-sig").splitlines():
                key, separator, value = line.strip().removeprefix("export ").partition("=")
                if separator and key.strip() in {"KADO_API_TOKEN", "KADO_DATA_DIR"}:
                    value = value.strip()
                    if len(value) > 1 and value[0] == value[-1] and value[0] in {"'", '"'}:
                        value = value[1:-1]
                    local[key.strip()] = value
        token_data = Path(os.environ.get("KADO_DATA_DIR") or local.get("KADO_DATA_DIR") or self.root / "data")
        if not token_data.is_absolute():
            token_data = self.root / token_data
        self.token = token or os.environ.get("KADO_API_TOKEN") or local.get("KADO_API_TOKEN") or (token_data / "api-token.txt").read_text(encoding="utf-8-sig").strip()
        if len(self.token) < 24:
            raise CompanyError("Şirket panelinin yerel API anahtarı bulunamadı.")
        # Explicitly bypass proxies ONLY for validated loopback, never for external providers.
        self.opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
        self.instance_id = str(uuid.uuid4())
        self.phase = "adapter_loaded"
        self.state_path = Path(state_path or self.root / "data" / "kado-host-state.json")
        self.lock = threading.RLock()
        self.pending = self._read_pending()
        self.host_ref = None
        self._stop = threading.Event()
        self._thread = None
        self._registered = False

    def __repr__(self):
        return f"CompanyClient(url={self.url!r}, token=<redacted>)"

    def _read_pending(self):
        if not self.state_path.exists():
            return {}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            raise CompanyError("KADO görev takip kaydı okunamıyor; data/kado-host-state.json dosyasını inceleyin.") from None

    def http(self, method, path, body=None, retryable=False):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        for attempt in range(3 if retryable else 1):
            req = request.Request(self.url + path, data=data, method=method,
                headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
            try:
                with self.opener.open(req, timeout=8) as response:
                    raw = response.read(2_000_001)
                    if len(raw) > 2_000_000:
                        raise CompanyError("Şirket yanıtı boyut sınırını aştı.")
                    return json.loads(raw)
            except error.HTTPError as exc:
                if retryable and exc.code in {429, 502, 503, 504} and attempt < 2:
                    try:
                        delay = min(5, max(0, float(exc.headers.get("Retry-After", "0.25"))))
                    except ValueError:
                        delay = 0.25
                    time.sleep(delay)
                    continue
                raise CompanyError(f"Şirket API HTTP {exc.code}; işlem doğrulanmadı. Panel ve yerel API anahtarını kontrol edin.") from None
            except (error.URLError, TimeoutError, ConnectionError, OSError):
                if retryable and attempt < 2:
                    time.sleep(0.15 * (2 ** attempt))
                    continue
                raise CompanyError("Şirket motoruna erişilemedi. Önce yeni AI Company BASLAT.bat dosyasını çalıştırın.") from None
            except (ValueError, UnicodeError):
                raise CompanyError("Şirket API yanıtı geçerli JSON değil.") from None

    def heartbeat(self, phase=None):
        result = self.http("POST", "/api/integrations/kado/heartbeat", {
            "instance_id": self.instance_id, "source_sha256": REVIEWED_MAIN_SHA256,
            "pid": os.getpid(), "phase": phase or self.phase, "adapter_version": VERSION})
        self._registered = True
        return result

    def attach_host(self, host):
        self.host_ref = weakref.ref(host)
        self.phase = "host_ready"

    def _remember_task(self, task):
        with self.lock:
            if task["id"] not in self.pending:
                self.pending[task["id"]] = {"notified_status": None}
                atomic_json(self.state_path, self.pending)
        return task

    @staticmethod
    def compact_task(task):
        result = task.get("result") or {}
        return {"id": task["id"], "title": task.get("title"), "status": task["status"],
                "error": task.get("error"), "retry_count": task.get("retry_count"),
                "summary": result.get("summary"), "report": result.get("report"),
                "qa_passed": (result.get("qa") or {}).get("passed"),
                "audit_passed": (result.get("audit") or {}).get("passed"),
                "text": str((result.get("response") or {}).get("text", ""))[:5000],
                "human_review_required": result.get("human_review_required", False),
                "owner_decision": task.get("owner_decision")}

    def execute(self, name, args, call_id=None):
        if name == "company_connection_status":
            agents = self.http("GET", "/api/agents", retryable=True)
            integrations = self.http("GET", "/api/integrations", retryable=True)
            return {"api_reachable": True, "agent_roles": len(agents), **integrations}
        if name == "company_list_agents":
            return self.http("GET", "/api/agents", retryable=True)
        if name in {"company_workspace_audit", "company_generate_text"}:
            title = str(args.get("title", "")).strip()
            if not 1 <= len(title) <= 300:
                raise CompanyError("Görev başlığı 1–300 karakter olmalı.")
            if name == "company_workspace_audit":
                kind, inputs = "workspace_audit", {"path": str(args.get("path") or ".")}
            else:
                prompt = str(args.get("prompt", "")).strip()
                if not 1 <= len(prompt) <= 20000:
                    raise CompanyError("Metin istemi 1–20000 karakter olmalı.")
                kind, inputs = "llm_task", {"prompt": prompt, "agent_id": str(args.get("agent_id") or "deep_researcher")}
                if args.get("provider"):
                    if args["provider"] not in {"ollama", "gemini"}:
                        raise CompanyError("Desteklenmeyen model sağlayıcısı.")
                    inputs["provider"] = args["provider"]
            call_key = "kado-host:" + hashlib.sha256(str(call_id or uuid.uuid4()).encode()).hexdigest()
            task = self.http("POST", "/api/tasks", {"title": title, "kind": kind, "input": inputs,
                                                    "idempotency_key": call_key}, retryable=True)
            return self.compact_task(self._remember_task(task))
        if name in {"company_get_task", "company_control_task"}:
            try:
                task_id = str(uuid.UUID(str(args.get("task_id", ""))))
            except ValueError:
                raise CompanyError("Yeni şirketin geçerli UUID görev numarası gerekir.") from None
            path = "/api/tasks/" + task_id
            if name == "company_control_task":
                action = args.get("action")
                if action not in {"pause", "resume", "cancel", "retry"}:
                    raise CompanyError("Bu araç onay veremez; yalnızca pause/resume/cancel/retry desteklenir.")
                task = self.http("POST", path + "/action", {"action": action})
            else:
                task = self.http("GET", path, retryable=True)
            return self.compact_task(task)
        if name == "company_recent_tasks":
            return [self.compact_task(task) for task in self.http("GET", "/api/tasks?limit=20", retryable=True)]
        raise CompanyError("Bilinmeyen şirket aracı.")

    def poll_completed(self):
        host = self.host_ref() if self.host_ref else None
        if host is None:
            return
        with self.lock:
            pending = list(self.pending.items())
        # Bound one pass; old results remain available through the central API.
        for task_id, info in pending[-100:]:
            if self._stop.is_set():
                return
            task = self.http("GET", "/api/tasks/" + str(uuid.UUID(task_id)), retryable=False)
            status = task["status"]
            if status not in {"APPROVED", "FAILED", "BLOCKED", "CANCELLED", "REVIEW"} or info.get("notified_status") == status:
                continue
            if status == "REVIEW" and not (task.get("result") or {}).get("human_review_required"):
                continue
            if status == "APPROVED":
                message = "Yeni şirket görevi kabul edildi: " + task["title"] + ". " + str((task.get("result") or {}).get("summary") or "Sonuç panelde okunabilir.")
            elif status == "REVIEW":
                message = "Yeni şirketin metin çıktısı insan incelemesi bekliyor: " + task["title"] + ". Panelden inceleyebilirsiniz."
            else:
                message = "Yeni şirket görevi " + status + ": " + task["title"] + ". " + str(task.get("error") or "Durumu panelden inceleyebilirsiniz.")
            host.ui.write_log("KADO: " + message[:1200])
            # Reuse the inspected KADO ElevenLabs queue. Never call _pc_notify:
            # that method may forward to WhatsApp, which is not verified here.
            loop, queue = getattr(host, "_loop", None), getattr(host, "_el_queue", None)
            if not getattr(host, "_paused", False) and not getattr(host.ui, "muted", False) and getattr(host, "_el_on", False) and loop and loop.is_running() and queue is not None:
                loop.call_soon_threadsafe(queue.put_nowait, message[:1200])
            with self.lock:
                self.pending[task_id]["notified_status"] = status
                atomic_json(self.state_path, self.pending)

    def start_monitor(self):
        def monitor():
            while not self._stop.wait(8):
                try:
                    self.heartbeat()
                    self.poll_completed()
                except Exception as exc:
                    print("[KADO COMPANY] Bağlantı izleme:", type(exc).__name__)
        self._thread = threading.Thread(target=monitor, name="kado-company-monitor", daemon=True)
        self._thread.start()

    def close(self):
        self.phase = "stopped"
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if self._registered:
            try:
                self.heartbeat("stopped")
            except CompanyError:
                pass


def install_hooks(namespace, client):
    cls, types = namespace["KadoLive"], namespace["types"]
    original_init, original_config, original_execute = cls.__init__, cls._build_config, cls._execute_tool
    original_text = cls._on_text_command

    def connected_text(self, text):
        cleaned = str(text).strip()
        parts = cleaned.split(maxsplit=2)
        if not parts or parts[0].casefold() not in {"/sirket", "/şirket"}:
            return original_text(self, text)
        if getattr(self, "_paused", False):
            self.ui.write_log("ERR: KADO duraklatılmış; görev gönderilmedi.")
            return
        action = parts[1].casefold() if len(parts) > 1 else ""
        if action == "denetle":
            name, args = "company_workspace_audit", {"title": "KADO: gerçek çalışma alanı denetimi", "path": parts[2].strip('"') if len(parts) > 2 else "."}
        elif action == "durum" and len(parts) > 2:
            name, args = "company_get_task", {"task_id": parts[2].strip()}
        elif action in {"baglanti", "bağlantı"}:
            name, args = "company_connection_status", {}
        else:
            self.ui.write_log("SYS: Komutlar: /sirket denetle . | /sirket durum GOREV_UUID | /sirket baglanti")
            return

        async def dispatch():
            try:
                print("[KADO COMPANY] Doğrudan komut:", name, flush=True)
                result = await asyncio.to_thread(client.execute, name, args, "desktop:" + str(uuid.uuid4()))
                client.phase = "tool_call_verified"
                if name == "company_workspace_audit":
                    message = "Görev gerçekten kaydedildi. UUID: " + result["id"] + "; durum: " + result["status"] + ". Sonucu panelden izleyebilirsiniz."
                else:
                    message = json.dumps(result, ensure_ascii=False)
                self.ui.write_log("KADO COMPANY: " + message)
                print("[KADO COMPANY] " + message, flush=True)
            except Exception as exc:
                detail = str(exc) if isinstance(exc, CompanyError) else type(exc).__name__
                self.ui.write_log("ERR: Görev gönderimi doğrulanamadı: " + detail)
                print("[KADO COMPANY] HATA:", detail, flush=True)
        loop = getattr(self, "_loop", None)
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(dispatch(), loop)
        else:
            threading.Thread(target=lambda: asyncio.run(dispatch()), daemon=True, name="kado-direct-command").start()

    def connected_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        client.attach_host(self)
        self.ui.write_log("SYS: Yeni 35 ajanlı şirket araçları yüklendi. WhatsApp arama bağlantısı ayrıca test edilmelidir.")

    def connected_config(self):
        config = original_config(self)
        config.tools = list(config.tools or []) + [types.Tool(function_declarations=TOOLS)]
        config.system_instruction = str(config.system_instruction or "") + "\n" + INSTRUCTION
        return config

    async def connected_execute(self, fc):
        if not str(fc.name).startswith(PREFIX):
            return await original_execute(self, fc)
        try:
            print("[KADO COMPANY] Model araç çağrısı:", fc.name, flush=True)
            result = await asyncio.to_thread(client.execute, fc.name, dict(fc.args or {}), getattr(fc, "id", None))
            client.phase = "tool_call_verified"
        except Exception as exc:
            result = {"ok": False, "error": str(exc) if isinstance(exc, CompanyError) else type(exc).__name__,
                      "note": "İşlem başarıyla tamamlanmış sayılmamalı."}
        return types.FunctionResponse(id=getattr(fc, "id", None), name=fc.name, response={"result": result})

    cls.__init__, cls._build_config, cls._execute_tool = connected_init, connected_config, connected_execute
    cls._on_text_command = connected_text
    return original_init, original_config, original_execute


def validate_source(kado_root):
    root = Path(kado_root).resolve()
    app_dir = root / "sistem" if (root / "sistem" / "main.py").is_file() else root
    main_path = app_dir / "main.py"
    if not main_path.is_file() or main_path.is_symlink():
        raise CompanyError("İncelenen KADO main.py dosyası bulunamadı.")
    if hashlib.sha256(main_path.read_bytes()).hexdigest() != REVIEWED_MAIN_SHA256:
        raise CompanyError("KADO main.py incelenen sürümden farklı. Güvenli bağlantı başlatılmadı; yeni kaynağı incelemek gerekir.")
    return app_dir, main_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-root", required=True, type=Path)
    parser.add_argument("--kado-root", default=r"C:\KADO\kado", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--check", action="store_true", help="Only verify source and API; do not launch KADO")
    args = parser.parse_args()
    client = None
    try:
        app_dir, main_path = validate_source(args.kado_root)
        client = CompanyClient(args.company_root, args.url)
        result = client.execute("company_connection_status", {})
        if result.get("kado_adapter_version") != VERSION:
            raise CompanyError("Backend bağlantı güncellemesi eksik. KADO_BAGLANTI_KUR.bat çalıştırın.")
        print("[KADO COMPANY] Şirket API bağlantısı ve incelenen KADO kaynak sürümü doğrulandı.")
        if args.check:
            print(json.dumps({"api_reachable": True, "source_hash_matches": True, "agent_roles": result["agent_roles"],
                              "existing_kado_started": False, "voice_tested": False, "whatsapp_tested": False}, ensure_ascii=False))
            return 0
        # Original KADO imports its own modules/config/memory with its usual cwd.
        os.chdir(app_dir)
        sys.path.insert(0, str(app_dir))
        sys.argv = [str(main_path)]
        namespace = runpy.run_path(str(main_path), run_name="kado_company_existing_host")
        install_hooks(namespace, client)
        client.heartbeat()
        client.start_monitor()
        namespace["main"]()
        return 0
    except Exception as exc:
        print("[KADO COMPANY] HATA:", str(exc) if isinstance(exc, (CompanyError, FileNotFoundError)) else type(exc).__name__)
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
