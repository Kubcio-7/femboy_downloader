import json
import os
from pathlib import Path

# =========================
# TAGI USERA
# =========================
_tags = []

BLOCKED = {
    "child","children","kid","minor","underage","young","teen",
    "loli","lolicon","shota","shotacon","toddler","baby",
    "schoolgirl","schoolboy","middle_school","elementary_school",
    "scat","coprophagia","feces","poop",
    "ai","ai_generated","stable_diffusion","midjourney",
    "nai_diffusion","novelai","generated",
}

# =========================
# KONFIG
# =========================
_CFG_DIR = Path(os.path.expanduser("~")) / ".config" / "femboydownloader"
_CFG_FILE = _CFG_DIR / "config.json"

_state = {
    "nsfw": True,
    "astolfo": False,
    "genshin": False,
    # 0..100 (soft -> hardcore)
    "nsfw_level": 70,
}

def _load():
    if _CFG_FILE.exists():
        try:
            data = json.loads(_CFG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _state.update(data)
        except Exception:
            pass

def _save():
    _CFG_DIR.mkdir(parents=True, exist_ok=True)
    _CFG_FILE.write_text(json.dumps(_state, indent=2), encoding="utf-8")

_load()

def set_nsfw(v):
    _state["nsfw"] = bool(v)
    _save()

def is_nsfw():
    return bool(_state.get("nsfw", True))

def set_astolfo(v):
    _state["astolfo"] = bool(v)
    _save()

def is_astolfo():
    return bool(_state.get("astolfo", False))

def set_genshin(v):
    _state["genshin"] = bool(v)
    _save()

def is_genshin():
    return bool(_state.get("genshin", False))

def set_nsfw_level(v):
    try:
        iv = int(float(v))
    except Exception:
        iv = 70
    if iv < 0:
        iv = 0
    if iv > 100:
        iv = 100
    _state["nsfw_level"] = iv
    _save()

def get_nsfw_level():
    try:
        return int(_state.get("nsfw_level", 70))
    except Exception:
        return 70

# =========================
# TAGI
# =========================
def add_tag(tag):
    t = (tag or "").strip().lower()
    if not t:
        return False, "Pusty tag"
    if t in BLOCKED:
        return False, f"Zablokowany tag: {t}"
    if t not in _tags:
        _tags.append(t)
    return True, ""

def remove_tag(tag):
    t = (tag or "").strip().lower()
    if t in _tags:
        _tags.remove(t)

def get_tag_list():
    return list(_tags)

def get_tags_query():
    return " ".join(_tags).strip()
