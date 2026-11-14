# -*- coding: utf-8 -*-
"""KADO Influencer Studio runtime - standart kutuphane."""
from __future__ import annotations
import json, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STUDIO = ROOT / "influencer_studio"

def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def status():
    identity = _read(STUDIO / "identity" / "influencer_identity.json", {})
    calendar = _read(STUDIO / "calendar" / "30_gunluk_plan.json", {})
    drafts = sorted((STUDIO / "drafts").glob("*.json"))
    return {
        "ok": True,
        "identity_name": identity.get("stage_name", ""),
        "persona": identity.get("persona", ""),
        "days_planned": len(calendar.get("days", [])),
        "draft_count": len(drafts),
        "publish_mode": "KAPALI",
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    }

def create_draft(project="KADO", topic="tanitim", platform="instagram"):
    identity = _read(STUDIO / "identity" / "influencer_identity.json", {})
    voice = identity.get("voice", {})
    hashtags = {
        "instagram": ["#kesfet", "#yenilik", "#ai", "#kado"],
        "tiktok": ["#fyp", "#kesfet", "#ai", "#kado"],
        "youtube": ["#shorts", "#ai", "#kado"]
    }.get(platform, ["#ai", "#kado"])
    slug = dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + __import__("uuid").uuid4().hex[:6]
    draft = {
        "id": slug,
        "project": project,
        "platform": platform,
        "topic": topic,
        "status": "taslak",
        "hook": f"Bugun {project} icin kisa bir fikir: {topic}.",
        "caption": f"{project} icin {topic} temali samimi ve sade bir paylasim taslagi.",
        "script": [
            f"Merhaba, ben {identity.get('stage_name', 'KADO Influencer')}.",
            f"Bugun {project} icin {topic} konusunu anlatiyorum.",
            "Yorumlara dusunceni yazmayi unutma."
        ],
        "visual_prompt": f"Ayni karakter, temiz isik, dikey kadraj, sosyal medya sunucusu tarzinda, konu: {topic}",
        "voice_style": voice.get("style", "samimi ve enerjik"),
        "hashtags": hashtags,
        "needs_human_approval": True,
        "publish_ready": False,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    }
    out = STUDIO / "drafts" / f"{slug}_{platform}_{topic}.json"
    _write(out, draft)
    return {"ok": True, "path": str(out), "draft": draft}

def report_text():
    s = status()
    return (
        f"Sanal influencer durumu: isim={s['identity_name'] or '-'}, "
        f"planli gun={s['days_planned']}, taslak={s['draft_count']}, "
        f"yayin modu={s['publish_mode']}."
    )

def main():
    print(report_text())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
