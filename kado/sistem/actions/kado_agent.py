"""
KADO — Arka plan calisani

Fare ve klavyeye DOKUNMADAN calisir: kod yazar ve calistirir, python ortami kurar, dosya okur/yazar,
internette arastirir, bilgisayardaki dosyalari arar, ogrendiklerini hatirlar.
Kullanici baska is yaparken arka planda yurur; bitince sesli haber verir.

GUVENLIK
 • Yazma/olusturma sadece CALISMA ALANINDA (varsayilan: Kullanici klasoru\\Kado-Calisma).
   Disina yazmak icin kullaniciya sorar.
 • Silme/tasima/e-posta/subprocess gibi riskli kod calistirmadan once kullaniciya sorar.
 • Fare/klavye/kayit-defteri kontrolu yapan kod calistirmaz.
 • Sifre/anahtar/gizli dosya adlari okunmaz.
"""

from __future__ import annotations

import html
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from app_config import get_app_config_value
from actions import kado_brain as brain
from actions import computer_agent as _ca

MAX_TURNS = 30
MAX_CONCURRENT = 2
OUT_LIMIT = 4000
IS_WIN = os.name == "nt"


# ── Calisma alani ────────────────────────────────────────────────────────────
def workspace() -> Path:
    custom = str(get_app_config_value("workspace_dir", "") or "").strip()
    ws = Path(os.path.expandvars(os.path.expanduser(custom))) if custom else Path.home() / "Kado-Calisma"
    for sub in ("projects", "skills", "tmp"):
        (ws / sub).mkdir(parents=True, exist_ok=True)
    return ws


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve(p: str) -> Path:
    p = os.path.expandvars(os.path.expanduser(str(p or "").strip().strip('"')))
    path = Path(p)
    if not path.is_absolute():
        path = workspace() / path
    return path.resolve()


# ── Gemini yardimcilari ──────────────────────────────────────────────────────
def _client():
    from google import genai
    key = str(get_app_config_value("gemini_api_key", "") or "").strip()
    if not key:
        raise RuntimeError("Gemini API anahtari yok.")
    return genai.Client(api_key=key)


def _generate(prompt: str, *, json_mode: bool = False, search: bool = False, fast: bool = False) -> tuple[str, list[str]]:
    """Gemini'ye metin sorar. Donus: (metin, kaynak_listesi)."""
    from google.genai import types
    client = _client()
    custom = str(get_app_config_value("agent_model", "") or "").strip()
    if custom and not custom.startswith("models/"):
        custom = "models/" + custom
    if fast:   # hizli arastirma: once hafif/hizli model (ayar: research_model)
        rm = str(get_app_config_value("research_model", "") or "").strip()
        rm = rm if (not rm or rm.startswith("models/")) else "models/" + rm
        base = ([rm] if rm else []) + ["models/gemini-3.5-flash-lite"] + list(_ca.VISION_MODELS)
    else:
        base = ([custom] if custom else []) + ([_ca._WORKING_MODEL] if _ca._WORKING_MODEL else []) + list(_ca.VISION_MODELS)
    order = list(dict.fromkeys(m for m in base if m))
    last: Exception | None = None

    def _try(models):
        nonlocal last
        for model in models:
            for attempt in range(3):
                try:
                    cfg = dict(temperature=0.2 if not search else 0.3)
                    if json_mode:
                        cfg["response_mime_type"] = "application/json"
                    if search:
                        cfg["tools"] = [types.Tool(google_search=types.GoogleSearch())]
                    if _ca._THINK_OK:
                        cfg["thinking_config"] = types.ThinkingConfig(thinking_level="low")
                    r = client.models.generate_content(
                        model=model, contents=prompt, config=types.GenerateContentConfig(**cfg))
                    if not fast:
                        _ca._WORKING_MODEL = model
                    sources = []
                    try:
                        gm = r.candidates[0].grounding_metadata
                        for ch in (gm.grounding_chunks or [])[:6]:
                            if ch.web and ch.web.uri:
                                sources.append(f"{ch.web.title or ch.web.uri} ({ch.web.uri})")
                    except Exception:
                        pass
                    return (r.text or ""), sources
                except Exception as e:  # noqa: BLE001
                    last = e
                    msg = str(e).lower()
                    if _ca._THINK_OK and "thinking" in msg:
                        _ca._THINK_OK = False
                        continue
                    if _ca._is_not_found(e):
                        break
                    if any(k in msg for k in ("quota", "429", "resource exhausted", "rate")):
                        time.sleep(5 * (attempt + 1))
                        continue
                    if any(k in msg for k in ("503", "unavailable", "overloaded", "timeout")):
                        time.sleep(2 * (attempt + 1))
                        continue
                    break
        return None

    res = _try(order)
    if res is None and last is not None and _ca._is_not_found(last):
        res = _try([m for m in _ca._discover_models(client) if m not in order])
    if res is None:
        raise RuntimeError(f"Gemini yanit vermedi ({str(last)[:160]})")
    return res


def quick_research(query: str) -> str:
    """Hizli arastirma: Google aramasina dayali, kaynakli, kisa cevap (birkac saniye)."""
    query = (query or "").strip()
    if not query:
        return "Arastirilacak konu bos."
    prompt = ("Asagidaki konuyu internette arastir ve Turkce, kisa, net ve GUNCEL bir cevap ver "
              "(en fazla 5 cumle; sayilar/fiyatlar/tarihler varsa yaz; tahmin etme; giris/uzatma yapma).\n\nKONU: " + query)
    try:
        text, sources = _generate(prompt, search=True, fast=True)
    except Exception as e:  # noqa: BLE001
        return f"Arastirma yapilamadi: {str(e)[:160]}"
    out = text.strip() or "Sonuc bulunamadi."
    if sources:
        out += "\nKaynaklar: " + "; ".join(sources[:4])
    return out


# ── Araclar ──────────────────────────────────────────────────────────────────
_BLOCK_CODE = re.compile(r"pyautogui|keybd_event|mouse_event|SetCursorPos|SendInput|pynput|winreg|"
                         r"ImageGrab|GetAsyncKeyState", re.I)
_CONFIRM_CODE = re.compile(r"rmtree|os\.remove|os\.unlink|os\.rmdir|\.unlink\(|\.rmdir\(|send2trash|"
                           r"shutil\.move|os\.rename|os\.replace|Remove-Item|smtplib|startfile|"
                           r"os\.system|subprocess|webbrowser", re.I)


def _clip(text: str, n: int = OUT_LIMIT) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n // 2] + "\n… [kisaltildi] …\n" + text[-n // 2:]


def _spawn(cmd: list[str], cwd: Path, timeout: int) -> str:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    kw = {}
    if IS_WIN:
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=timeout, env=env, **kw)
    except subprocess.TimeoutExpired:
        return f"ZAMAN ASIMI ({timeout} sn) — komut durduruldu."
    except Exception as e:  # noqa: BLE001
        return f"Calistirilamadi: {e}"
    out = (p.stdout or b"").decode("utf-8", errors="replace")
    err = (p.stderr or b"").decode("utf-8", errors="replace")
    res = f"[cikis kodu {p.returncode}]\n{out}"
    if err.strip():
        res += f"\n[hata]\n{err}"
    return _clip(res)


def _venv_python(project: Path) -> Path:
    return project / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")


def _safe_url(url: str) -> str | None:
    u = urlparse(url if re.match(r"^https?://", url, re.I) else "https://" + url)
    host = u.hostname or ""
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
    except Exception:
        return None
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return None
    return u.geturl()


class Job:
    def __init__(self, jid: int, goal: str):
        self.id, self.goal = jid, goal
        self.status = "calisiyor"
        self.last_step = ""
        self.question = ""
        self.result = ""
        self.stop = threading.Event()
        self.reply_evt = threading.Event()
        self.reply_text = ""
        self.thread: threading.Thread | None = None


class JobManager:
    def __init__(self):
        self.jobs: dict[int, Job] = {}
        self._n = 0
        self._lock = threading.Lock()

    # -- disa acik
    def start(self, goal: str, notify) -> str:
        goal = (goal or "").strip()
        if not goal:
            return "Gorev bos."
        with self._lock:
            running = [j for j in self.jobs.values() if j.status == "calisiyor"]
            if len(running) >= MAX_CONCURRENT:
                return f"Zaten {len(running)} arka plan isi suruyor, biri bitince yenisini baslatirim."
            self._n += 1
            job = Job(self._n, goal)
            self.jobs[job.id] = job
        job.thread = threading.Thread(target=self._run, args=(job, notify), daemon=True)
        job.thread.start()
        return f"{job.id} numarali is arka planda basladi. Sen bilgisayarda devam et, bitince haber veririm."

    def _pick(self, jid):
        running = [j for j in self.jobs.values() if j.status == "calisiyor"]
        if jid is not None:
            return self.jobs.get(int(jid))
        return running[0] if len(running) == 1 else (running[0] if running else None)

    def stop(self, jid=None) -> str:
        targets = ([self.jobs.get(int(jid))] if jid else
                   [j for j in self.jobs.values() if j.status == "calisiyor"])
        targets = [t for t in targets if t and t.status == "calisiyor"]
        if not targets:
            return ""
        for t in targets:
            t.stop.set()
            t.reply_evt.set()
        return f"{len(targets)} arka plan isini durduruyorum."

    def reply(self, answer: str, jid=None) -> str:
        waiting = [j for j in self.jobs.values() if j.status == "calisiyor" and j.question]
        job = self.jobs.get(int(jid)) if jid else (waiting[0] if waiting else None)
        if not job or not job.question:
            return ""
        job.reply_text = (answer or "").strip()
        job.reply_evt.set()
        return "Cevabi arka plan isine ilettim."

    def status(self) -> str:
        if not self.jobs:
            return ""
        lines = []
        for j in list(self.jobs.values())[-4:]:
            extra = (f" SORU: {j.question}" if j.question else
                     f" son adim: {j.last_step}" if j.status == "calisiyor" else f" sonuc: {j.result}")
            lines.append(f"Is {j.id} [{j.status}] '{j.goal[:70]}'.{extra}")
        return "\n".join(lines)

    # -- is dongusu
    def _confirm(self, job: Job, question: str, notify) -> bool | None:
        job.question = question
        job.reply_evt.clear()
        job.reply_text = ""
        notify(question)
        got = job.reply_evt.wait(_ca.CONFIRM_TIMEOUT)
        job.question = ""
        if job.stop.is_set() or not got:
            return None
        low = job.reply_text.lower()
        if re.search(r"hay[ıi]r|yapma|olmaz|iptal|\bdur\b|vazge", low):
            return False
        return bool(re.search(r"\b(evet|tamam|onay|olur|yap|devam|ok|tabii|tabi)\b", low))

    def _tool(self, job: Job, name: str, a: dict, notify) -> str:
        ws = workspace()

        if name == "web_search":
            text, src = _generate("Su konuyu internette arastir, Turkce ve ayrintili ozetle (sayilar, tarihler, "
                                  "isimler dahil):\n" + str(a.get("query", "")), search=True)
            return _clip(text + ("\nKaynaklar: " + "; ".join(src[:5]) if src else ""))

        if name == "fetch_url":
            url = _safe_url(str(a.get("url", "")))
            if not url:
                return "Bu adres getirilemez (gecersiz ya da yerel ag)."
            import requests
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 KADO"}, stream=True)
            raw = r.raw.read(2_000_000, decode_content=True).decode(r.encoding or "utf-8", errors="ignore")
            if "html" in r.headers.get("content-type", "") or raw.lstrip().startswith("<"):
                raw = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", raw)
                raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
            raw = re.sub(r"\s+", " ", raw)
            n = max(500, min(int(a.get("max_chars") or 6000), 15000))
            return f"[HTTP {r.status_code}] " + raw[:n]

        if name == "list_dir":
            p = _resolve(a.get("path", "."))
            if not p.is_dir():
                return "Klasor degil / yok."
            rows = []
            for e in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:80]:
                rows.append(("[K] " if e.is_dir() else "    ") + e.name +
                            ("" if e.is_dir() else f"  ({e.stat().st_size} B)"))
            return "\n".join(rows) or "(bos)"

        if name == "read_file":
            p = _resolve(a.get("path", ""))
            if brain._is_sensitive(p):
                return "Gizli olabilecek dosya, okunmuyor."
            if not p.is_file():
                return "Dosya yok."
            text = brain._read_text(p) if p.suffix.lower() in brain.TEXT_EXT | brain.DOC_EXT else \
                p.read_bytes()[:200000].decode("utf-8", errors="ignore")
            off = int(a.get("offset") or 0)
            n = max(500, min(int(a.get("max_chars") or 6000), 20000))
            return text[off:off + n] + (f"\n[… toplam {len(text)} karakter, offset={off + n} ile devam]"
                                         if len(text) > off + n else "")

        if name == "write_file":
            p = _resolve(a.get("path", ""))
            if not _inside(p, ws):
                ok = self._confirm(job, f"{p} dosyasini calisma alani disinda yazmak istiyorum. Onayliyor musun?", notify)
                if not ok:
                    return "Kullanici onaylamadi / cevap yok; yazilmadi."
            if brain._is_sensitive(p):
                return "Gizli olabilecek dosya adi, yazilmiyor."
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(str(a.get("content", "")), encoding="utf-8")
            return f"Yazildi: {p} ({len(str(a.get('content','')))} karakter)"

        if name == "search_files":
            return brain.search_files(str(a.get("query", "")))

        if name == "remember":
            return brain.remember(str(a.get("text", "")), str(a.get("kind", "ders")))

        if name == "recall":
            r = brain.recall(str(a.get("query", "")))
            return "\n".join(r) or "Ilgili not yok."

        if name == "new_project":
            nm = re.sub(r"[^\w\-]", "_", str(a.get("name", "proje")).strip())[:40] or "proje"
            proj = ws / "projects" / nm
            proj.mkdir(parents=True, exist_ok=True)
            out = ""
            if not _venv_python(proj).exists():
                out += _spawn([sys.executable, "-m", "venv", str(proj / ".venv")], proj, 300) + "\n"
            pk = [x for x in (a.get("packages") or []) if re.match(r"^[A-Za-z0-9_.\-\[\]=<>~!,]+$", str(x))]
            if pk:
                out += _spawn([str(_venv_python(proj)), "-m", "pip", "install", "-q", *pk], proj, 900)
            return f"Proje klasoru: {proj}\n" + _clip(out, 1500)

        if name == "run_python":
            code = a.get("code")
            proj = None
            if a.get("project"):
                proj = ws / "projects" / re.sub(r"[^\w\-]", "_", str(a["project"]))
                if not proj.exists():
                    return "Proje yok; once new_project ile olustur."
            cwd = proj or (ws / "tmp")
            if code is None:
                f = _resolve(a.get("file", ""))
                if not f.is_file():
                    return "Dosya yok."
                code = f.read_text(encoding="utf-8", errors="ignore")
                script = f
            else:
                script = ws / "tmp" / f"job{job.id}_{int(time.time())}.py"
                script.write_text(str(code), encoding="utf-8")
            if _BLOCK_CODE.search(code):
                return "ENGELLENDI: Arka planda fare/klavye/ekran/kayit-defteri kodu calistirilmaz."
            if _CONFIRM_CODE.search(code) and not _inside(script, ws / "skills"):
                ok = self._confirm(job, "Calistiracagim kod dosya silme/tasima ya da dis komut iceriyor. Onayliyor musun?", notify)
                if not ok:
                    return "Kullanici onaylamadi / cevap yok; calistirilmadi."
            py = _venv_python(proj) if proj and _venv_python(proj).exists() else Path(sys.executable)
            timeout = max(10, min(int(a.get("timeout") or 120), 900))
            return _spawn([str(py), str(script), *[str(x) for x in (a.get("args") or [])]], cwd, timeout)

        if name == "run_shell":
            from actions.shell import _blocked_patterns, _unsafe_prefixes
            cmd = str(a.get("command", "")).strip()
            low = cmd.lower()
            if not cmd:
                return "Komut bos."
            if low.startswith(_unsafe_prefixes()) or any(b in low for b in _blocked_patterns()):
                return "ENGELLENDI: Bu komut guvenlik icin calistirilmiyor."
            if re.search(r"pyautogui|sendkeys|mouse_event|keybd_event|reg\s+add|new-itemproperty", low):
                return "ENGELLENDI: Fare/klavye/kayit-defteri komutlari arka planda calismaz."
            cwd = _resolve(a.get("cwd", "")) if a.get("cwd") else ws
            if not _inside(cwd, ws):
                cwd = ws
            timeout = max(5, min(int(a.get("timeout") or 120), 900))
            if IS_WIN:
                full = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + cmd]
            else:
                full = ["bash", "-lc", cmd]
            return _spawn(full, cwd, timeout)

        if name == "save_skill":
            nm = brain.save_skill(str(a.get("name", "beceri")), str(a.get("description", "")), "")
            path = ws / "skills" / f"{nm}.py"
            path.write_text(str(a.get("code", "")), encoding="utf-8")
            with brain._lock:
                brain._db().execute("UPDATE skills SET path=? WHERE name=?", (str(path), nm))
                brain._db().commit()
            return f"Beceri kaydedildi: {nm} ({path})"

        if name == "list_skills":
            rows = brain.list_skills()
            return "\n".join(f"- {n}: {d}" for n, d, _ in rows) or "Henuz beceri yok."

        if name == "run_skill":
            row = brain.get_skill(str(a.get("name", "")))
            if not row:
                return "Boyle bir beceri yok."
            brain.bump_skill(row[0])
            return self._tool(job, "run_python", {"file": row[2], "args": a.get("args") or [],
                                                  "timeout": a.get("timeout") or 120}, notify)

        if name == "open_path":
            p = _resolve(a.get("path", ""))
            if not _inside(p, ws) or not p.exists():
                return "Sadece calisma alanindaki mevcut yollar acilir."
            if IS_WIN:
                os.startfile(str(p))  # noqa: S606
            return f"Acildi: {p}"

        return f"Bilinmeyen arac: {name}"

    def _run(self, job: Job, notify):
        ws = workspace()
        steps: list[str] = []
        outcome = ""
        try:
            notes = brain.recall(job.goal, 6)
            mem = "\n".join(f"- {n}" for n in notes) or "(ilgili not yok)"
            skills = "\n".join(f"- {n}: {d}" for n, d, _ in brain.list_skills()[:15]) or "(yok)"
            tail = 0
            for turn in range(1, MAX_TURNS + 1):
                if job.stop.is_set():
                    outcome = "Is durduruldu."
                    break
                hist = "\n".join(steps[-12:]) or "(henuz adim yok)"
                prompt = (f"{AGENT_SYSTEM.replace('{WS}', str(ws))}\n\nGOREV: {job.goal}\n\n"
                          f"HAFIZA NOTLARI:\n{mem}\n\nKAYITLI BECERILER:\n{skills}\n\n"
                          f"ONCEKI ADIMLAR:\n{hist}\n\nTUR {turn}/{MAX_TURNS}. Sonraki adimi ver.")
                try:
                    text, _ = _generate(prompt, json_mode=True)
                    step = _ca._extract_json(text)
                except Exception as e:  # noqa: BLE001
                    tail += 1
                    if tail >= 3:
                        raise
                    steps.append(f"(gecersiz cevap: {str(e)[:80]})")
                    continue
                tail = 0
                tool = str(step.get("tool", "")).strip()
                args = step.get("args") if isinstance(step.get("args"), dict) else {}
                job.last_step = f"{tool}: {str(step.get('thought', ''))[:100]}"
                print(f"[KADO-IS {job.id}] {tool} {json.dumps(args, ensure_ascii=False)[:200]}")

                if tool == "finish":
                    outcome = str(args.get("summary") or step.get("thought") or "Is tamam.")
                    break
                if tool == "ask_user":
                    ok_txt = self._ask_text(job, str(args.get("question", "Ne yapmami istersin?")), notify)
                    if ok_txt is None:
                        outcome = "Cevap gelmedi, isi durdurdum."
                        break
                    steps.append(f"ask_user -> kullanici: {ok_txt}")
                    continue
                try:
                    res = self._tool(job, tool, args, notify)
                except Exception as e:  # noqa: BLE001
                    res = f"ARAC HATASI: {e}"
                steps.append(f"{turn}. {tool} {json.dumps(args, ensure_ascii=False)[:300]}\n   -> {_clip(res, 1400)}")
            else:
                outcome = "Tur sinirina ulastim; is yarim kalmis olabilir."
        except Exception as e:  # noqa: BLE001
            outcome = f"Is hata verdi: {str(e)[:160]}"
        finally:
            job.result = outcome
            job.status = "durduruldu" if job.stop.is_set() else "bitti"
            try:
                brain.remember(f"Is: {job.goal[:140]} -> {outcome[:200]}", kind="is")
            except Exception:
                pass
            try:
                notify(f"{outcome}" if outcome else "Is bitti.")
            except Exception:
                pass

    def _ask_text(self, job: Job, question: str, notify) -> str | None:
        job.question = question
        job.reply_evt.clear()
        job.reply_text = ""
        notify(question)
        got = job.reply_evt.wait(_ca.CONFIRM_TIMEOUT)
        job.question = ""
        if job.stop.is_set() or not got:
            return None
        return job.reply_text


AGENT_SYSTEM = """Sen KADO'nun ARKA PLAN CALISANISIN. Windows bilgisayarda kullanicinin istedigi isi FARE VE
KLAVYEYE DOKUNMADAN yaparsin: kod yazip calistirir, python ortami kurar, dosya okuyup yazar,
internette arastirir, bilgisayardaki dosyalari arar, ogrendiklerini hatirlarsin. Kullanici baska is yapiyor;
ona karisma.

SADECE su JSON'u dondur: {"thought": "kisa Turkce dusunce", "tool": "arac_adi", "args": {...}}

ARACLAR (args):
- web_search {query}                      internette arastir (kaynakli, ozet)
- fetch_url {url, max_chars?}             sayfa metnini getir
- search_files {query}                    kullanicinin ogretilmis dosyalarinda ara
- read_file {path, offset?, max_chars?}   dosya oku (txt/kod/docx/pptx/pdf)
- list_dir {path}                         klasor listele
- write_file {path, content}              dosya yaz (goreli yol = calisma alani)
- new_project {name, packages:[...]}      python projesi + sanal ortam kur, paketleri yukle
- run_python {code | file, project?, args?, timeout?}   python calistir (project verirse onun ortaminda)
- run_shell {command, cwd?, timeout?}     PowerShell komutu (calisma alani icinde)
- save_skill {name, description, code}    tekrar kullanilabilir kodu beceri olarak kaydet
- list_skills {} / run_skill {name, args?}
- remember {text, kind?}                  KALICI hafizaya yaz (tercih, ders, ise yarayan yontem)
- recall {query}                          hafizada ara
- open_path {path}                        calisma alanindaki dosyayi/klasoru ac (sadece kullanici gormek isterse)
- ask_user {question}                     emin degilsen / onay gerekiyorsa sor
- finish {summary}                        BITTI: sesli okunacak 1-3 cumlelik Turkce ozet (yol/isim ver)

KURALLAR:
- Calisma alani: {WS}   Tum projeleri/dosyalari orada olustur.
- Kod yazinca CALISTIR, ciktiyi/hatayi oku, duzelt (birkac deneme). Test etmeden "bitti" deme.
- Uygulama fikri istenirse: new_project -> kodu yaz -> calistirip test et -> finish'te klasor yolu ve nasil acilacagini soyle.
- Kalici ogrendigin seyi (kullanici tercihi, hata cozumu, ise yarayan yontem) remember ile kaydet; tekrar kullanilabilir kodu save_skill ile.
- Arastirmada once web_search; gerekirse fetch_url ile kaynagi oku; sayilari uydurma.
- Silme, calisma alani disina yazma, mesaj/e-posta gonderme, odeme: sormadan YAPMA (ask_user).
- Sifre, API anahtari, kisisel gizli bilgi okuma/yazma/paylasma.
- Fare/klavye/ekran kontrolu YOK (arka plandasin).
- Hedefe ulastiysan hemen finish."""


JOBS = JobManager()
