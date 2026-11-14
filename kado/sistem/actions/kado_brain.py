"""
KADO — Beyin: kalici hafiza + bilgisayardaki dosyalarin yerel indeksi.

• Her sey YEREL (SQLite). Dosya iceriklerinin tamami internete gonderilmez;
  sadece aramada bulunan kisa parcalar, gorev icin gerektiginde modele gider.
• Notlar (dersler, tercihler, yapilan isler) ve beceriler (kaydedilmis kodlar) burada durur,
  Kado yeniden acilsa da unutmaz.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
import zipfile
from pathlib import Path

from app_paths import data_path

DB_PATH = data_path("kado_brain.db")
_lock = threading.RLock()
_conn_cache: sqlite3.Connection | None = None
HAS_FTS = True

_TR = str.maketrans({"ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i",
                     "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u"})


def norm(text: str) -> str:
    return (text or "").translate(_TR).lower()


def _db() -> sqlite3.Connection:
    global _conn_cache, HAS_FTS
    with _lock:
        if _conn_cache is not None:
            return _conn_cache
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
        c.execute("CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, ts REAL, kind TEXT, text TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, size INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS skills(name TEXT PRIMARY KEY, description TEXT, path TEXT, ts REAL, uses INTEGER DEFAULT 0)")
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5("
                      "kind UNINDEXED, ref UNINDEXED, raw UNINDEXED, content, "
                      "tokenize='unicode61 remove_diacritics 2')")
            HAS_FTS = True
        except sqlite3.OperationalError:
            HAS_FTS = False
            c.execute("CREATE TABLE IF NOT EXISTS docs(kind TEXT, ref TEXT, raw TEXT, content TEXT)")
        c.commit()
        _conn_cache = c
        return c


def _tokens(q: str) -> list[str]:
    return [t for t in re.findall(r"\w+", norm(q)) if len(t) > 1][:12]


def _search_docs(query: str, kinds: tuple[str, ...], limit: int = 8) -> list[tuple[str, str, str]]:
    toks = _tokens(query)
    if not toks:
        return []
    c = _db()
    ph = ",".join("?" * len(kinds))
    with _lock:
        if HAS_FTS:
            match = " OR ".join(f'"{t}"*' for t in toks)
            rows = c.execute(
                f"SELECT kind, ref, snippet(docs, 3, '[', ']', ' … ', 18) FROM docs "
                f"WHERE docs MATCH ? AND kind IN ({ph}) ORDER BY rank LIMIT ?",
                (match, *kinds, limit)).fetchall()
        else:
            cond = " OR ".join("content LIKE ?" for _ in toks)
            rows = c.execute(
                f"SELECT kind, ref, substr(raw,1,200) FROM docs WHERE kind IN ({ph}) AND ({cond}) LIMIT ?",
                (*kinds, *[f"%{t}%" for t in toks], limit)).fetchall()
    return rows


# ── Notlar ───────────────────────────────────────────────────────────────────
def remember(text: str, kind: str = "not") -> str:
    text = (text or "").strip()
    if not text:
        return "Bos not."
    c = _db()
    with _lock:
        dup = c.execute("SELECT id FROM notes WHERE text=?", (text,)).fetchone()
        if dup:
            return "Bu not zaten kayitli."
        cur = c.execute("INSERT INTO notes(ts, kind, text) VALUES(?,?,?)", (time.time(), kind, text))
        c.execute("INSERT INTO docs(kind, ref, raw, content) VALUES('note', ?, ?, ?)",
                  (str(cur.lastrowid), text[:400], norm(text)))
        c.commit()
    return "Hafizaya kaydettim."


def recall(query: str, limit: int = 6) -> list[str]:
    out = []
    c = _db()
    for _, ref, _snip in _search_docs(query, ("note",), limit):
        with _lock:
            row = c.execute("SELECT kind, text FROM notes WHERE id=?", (ref,)).fetchone()
        if row:
            out.append(f"[{row[0]}] {row[1]}")
    return out


# ── Beceriler (kaydedilmis kodlar) ───────────────────────────────────────────
def save_skill(name: str, description: str, path: str):
    name = re.sub(r"[^\w\-]", "_", name.strip().lower())[:40] or "beceri"
    c = _db()
    with _lock:
        c.execute("INSERT OR REPLACE INTO skills(name, description, path, ts, uses) VALUES(?,?,?,?,COALESCE((SELECT uses FROM skills WHERE name=?),0))",
                  (name, description, path, time.time(), name))
        c.execute("DELETE FROM docs WHERE kind='skill' AND ref=?", (name,))
        c.execute("INSERT INTO docs(kind, ref, raw, content) VALUES('skill', ?, ?, ?)",
                  (name, description[:400], norm(name + " " + description)))
        c.commit()
    return name


def list_skills() -> list[tuple[str, str, str]]:
    with _lock:
        return _db().execute("SELECT name, description, path FROM skills ORDER BY uses DESC, ts DESC LIMIT 60").fetchall()


def get_skill(name: str):
    with _lock:
        return _db().execute("SELECT name, description, path FROM skills WHERE name=?", (name.strip().lower(),)).fetchone()


def bump_skill(name: str):
    with _lock:
        _db().execute("UPDATE skills SET uses=uses+1 WHERE name=?", (name,))
        _db().commit()


# ── Dosya indeksi ────────────────────────────────────────────────────────────
TEXT_EXT = {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css", ".json",
            ".csv", ".log", ".ini", ".yaml", ".yml", ".xml", ".bat", ".ps1", ".java", ".c", ".cpp",
            ".h", ".cs", ".sql", ".tex", ".rst", ".toml", ".sh", ".go", ".rs", ".php", ".kt", ".swift"}
DOC_EXT = {".docx", ".pptx", ".pdf"}
SKIP_DIRS = {"node_modules", "venv", ".venv", "env", "site-packages", "__pycache__", "appdata",
             "windows", "program files", "program files (x86)", "programdata", "$recycle.bin",
             "system volume information", "cache", "caches", "temp", "tmp", "dist", "build", "target"}
SENSITIVE = ("password", "parola", "sifre", "şifre", "secret", "token", ".env", "id_rsa", "api_key",
             "apikey", "api_keys", "credential", "cookie", "login data", ".kdbx", ".pem", ".key",
             ".pfx", "wallet", "seed", "private", "kimlik", "iban", "kredi", "banka")
MAX_FILE_BYTES = 3 * 1024 * 1024
MAX_CHARS = 300_000

INDEX_STATUS = {"running": False, "folder": "", "indexed": 0, "skipped": 0, "current": "", "last": ""}


def _read_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXT:
            return path.read_text(encoding="utf-8", errors="ignore")[:MAX_CHARS]
        if ext in (".docx", ".pptx"):
            parts = []
            with zipfile.ZipFile(path) as z:
                names = ([n for n in z.namelist() if n == "word/document.xml"] if ext == ".docx"
                         else sorted(n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml", n)))
                for n in names:
                    xml = z.read(n).decode("utf-8", errors="ignore")
                    parts.append(re.sub(r"<[^>]+>", " ", xml))
            return re.sub(r"\s+", " ", " ".join(parts))[:MAX_CHARS]
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
            except Exception:
                return ""
            r = PdfReader(str(path))
            return "\n".join((p.extract_text() or "") for p in r.pages[:80])[:MAX_CHARS]
    except Exception:
        return ""
    return ""


def _is_sensitive(path: Path) -> bool:
    low = path.name.lower()
    return any(s in low for s in SENSITIVE)


def index_folder(folder: str, max_files: int = 20000) -> str:
    """Klasoru tarar ve indeksler (senkron). Ayri thread'den cagir."""
    root = Path(os.path.expandvars(os.path.expanduser(folder))).resolve()
    if not root.exists() or not root.is_dir():
        return f"Klasor bulunamadi: {folder}"
    if INDEX_STATUS["running"]:
        return "Zaten bir indeksleme suruyor."
    INDEX_STATUS.update(running=True, folder=str(root), indexed=0, skipped=0, current="")
    c = _db()
    seen = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                p = Path(dirpath) / fn
                ext = p.suffix.lower()
                if ext not in TEXT_EXT and ext not in DOC_EXT:
                    continue
                seen += 1
                if seen > max_files:
                    raise StopIteration
                if _is_sensitive(p):
                    INDEX_STATUS["skipped"] += 1
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size > MAX_FILE_BYTES or st.st_size == 0:
                    INDEX_STATUS["skipped"] += 1
                    continue
                with _lock:
                    row = c.execute("SELECT mtime FROM files WHERE path=?", (str(p),)).fetchone()
                if row and abs(row[0] - st.st_mtime) < 1:
                    continue
                INDEX_STATUS["current"] = p.name
                text = _read_text(p)
                if not text.strip():
                    INDEX_STATUS["skipped"] += 1
                    continue
                with _lock:
                    c.execute("DELETE FROM docs WHERE kind='file' AND ref=?", (str(p),))
                    c.execute("INSERT INTO docs(kind, ref, raw, content) VALUES('file', ?, ?, ?)",
                              (str(p), text[:300], norm(p.name + " " + text)))
                    c.execute("INSERT OR REPLACE INTO files(path, mtime, size) VALUES(?,?,?)",
                              (str(p), st.st_mtime, st.st_size))
                    if INDEX_STATUS["indexed"] % 50 == 0:
                        c.commit()
                INDEX_STATUS["indexed"] += 1
    except StopIteration:
        pass
    finally:
        with _lock:
            c.commit()
        INDEX_STATUS["running"] = False
        INDEX_STATUS["current"] = ""
    msg = (f"'{root}' tarandi: {INDEX_STATUS['indexed']} dosya ogrendim, "
           f"{INDEX_STATUS['skipped']} dosya atladim (cok buyuk/bos/gizli).")
    INDEX_STATUS["last"] = msg
    return msg


def search_files(query: str, limit: int = 8) -> str:
    rows = _search_docs(query, ("file",), limit)
    if not rows:
        return "Dosyalarda bulamadim. (Once ilgili klasoru ogrenmem gerekebilir.)"
    return "\n".join(f"- {ref}\n    …{snip.strip()}…" for _, ref, snip in rows)


def stats() -> str:
    c = _db()
    with _lock:
        nf = c.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        nn = c.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        ns = c.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    return f"{nf} dosya, {nn} not, {ns} beceri biliyorum."
