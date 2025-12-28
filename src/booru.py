import json
import os
import random
import tempfile
import threading
from pathlib import Path

import requests
import app_state

HEADERS = {
    "User-Agent": "FemboyDownloader/0.4 (GTK)",
    "Accept": "application/json",
}

TMP = Path(tempfile.gettempdir()) / "femboydownloader"
TMP.mkdir(parents=True, exist_ok=True)

DANBOORU = "https://danbooru.donmai.us/posts.json"
LAST_META = {}

# =========================
# FAST HTTP (keep-alive)
# =========================
_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)

# twarde timeouty (connect, read)
HTTP_TIMEOUT = (4, 8)

# =========================
# ANTI-REPEAT (id) — NA DYSKU
# =========================
CACHE_DIR = Path(os.path.expanduser("~")) / ".cache" / "femboydownloader"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SEEN_FILE = CACHE_DIR / "seen.json"
SEEN_MAX = 2500

def _load_seen():
    try:
        if SEEN_FILE.exists():
            data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("ids"), list):
                return set(map(str, data["ids"]))
    except Exception:
        pass
    return set()

SEEN_IDS = _load_seen()

def _save_seen():
    try:
        SEEN_FILE.write_text(
            json.dumps({"ids": list(SEEN_IDS)[-SEEN_MAX:]}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

def _seen(pid: str) -> bool:
    return pid in SEEN_IDS

def _remember(pid: str):
    SEEN_IDS.add(pid)
    if len(SEEN_IDS) > SEEN_MAX:
        # szybki trim
        tmp = list(SEEN_IDS)
        SEEN_IDS.clear()
        SEEN_IDS.update(tmp[-SEEN_MAX:])
    _save_seen()

# =========================
# FILTRY
# =========================
EXCLUDED = {
    "female","girl","1girl","2girls","3girls",
    "scat","coprophagia","feces","poop",
    "ai","ai_generated","stable_diffusion","midjourney",
    "nai_diffusion","novelai","generated","sd","prompt","txt2img",
}

REQUIRED_NSF = {"penis"}

FEMBOY_VIBE = {
    "femboy",
    "otokonoko",
    "androgynous_male",
    "crossdressing",
    "feminine_male",
}

# =========================
def _weighted_page():
    return random.choice([
        random.randint(1, 40),
        random.randint(40, 220),
        random.randint(220, 900),
    ])

def _forced_tags():
    if hasattr(app_state, "is_genshin") and app_state.is_genshin():
        return "genshin_impact femboy"
    if hasattr(app_state, "is_astolfo") and app_state.is_astolfo():
        return "astolfo"
    return None

# =========================
# RAM CACHE + PRELOAD (bez wieszania UI)
# =========================
_PRELOAD_LOCK = threading.Lock()
_PRELOAD_THREAD = None

NEXT_BYTES = None
NEXT_PID = None
NEXT_META = None
NEXT_MODE_KEY = None

def _mode_key(sfw: bool) -> str:
    forced = _forced_tags() or ""
    lvl = str(app_state.get_nsfw_level()) if hasattr(app_state, "get_nsfw_level") else "70"
    return f"{'SFW' if sfw else 'NSFW'}|forced={forced}|lvl={lvl}"

def _download_bytes(url: str) -> bytes | None:
    try:
        r = _SESSION.get(url, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.content
    except Exception:
        return None

def _write_response_bytes(b: bytes):
    (TMP / "response.jpg").write_bytes(b)

def _safe_get_posts(params: dict) -> list | None:
    try:
        r = _SESSION.get(DANBOORU, params=params, timeout=HTTP_TIMEOUT)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except Exception:
        return None
    return data if isinstance(data, list) else None

def _fetch_post(sfw: bool):
    forced = _forced_tags()
    lvl = app_state.get_nsfw_level() if hasattr(app_state, "get_nsfw_level") else 70

    ratings = ["rating:s", "rating:g"] if sfw else ["rating:q", "rating:e"]

    forced_has_two = bool(forced and (" " in forced.strip()))
    tries = 14 if not sfw else 10

    for _ in range(tries):
        page = _weighted_page()
        tag = forced if forced else random.choice(list(FEMBOY_VIBE))

        # limit 2 tagów: jeżeli forced ma 2 tagi, nie dokładamy rating w query
        if forced and forced_has_two:
            q = f"{tag}"
            params = {"tags": q, "limit": 70 if not sfw else 55, "page": page}
        else:
            q = f"{tag} {random.choice(ratings)}"
            params = {"tags": q, "limit": 70 if not sfw else 55, "page": page}

        data = _safe_get_posts(params)
        if not data:
            continue

        random.shuffle(data)

        for p in data:
            pid = str(p.get("id") or "")
            url = p.get("file_url")
            toks = set((p.get("tag_string") or "").split())
            rating = (p.get("rating") or "").lower()

            if not pid or not url:
                continue
            if _seen(pid):
                continue
            if EXCLUDED & toks:
                continue

            # rating filtr lokalny jeśli forced=2 tagi
            if forced and forced_has_two:
                if sfw and rating not in ("s", "g"):
                    continue
                if (not sfw) and rating not in ("q", "e"):
                    continue

            # NSFW level: tylko w normalnym trybie
            if (not sfw) and (not forced):
                if lvl >= 70 and "penis" not in toks:
                    continue

            meta = {"Source": "danbooru", "Author": "danbooru", "PostID": pid}
            return pid, url, meta

    return None

def _prefetch_next(sfw: bool):
    global NEXT_BYTES, NEXT_PID, NEXT_META, NEXT_MODE_KEY

    mk = _mode_key(sfw)

    picked = _fetch_post(sfw)
    if not picked:
        return
    pid, url, meta = picked

    b = _download_bytes(url)
    if not b:
        return

    with _PRELOAD_LOCK:
        NEXT_BYTES = b
        NEXT_PID = pid
        NEXT_META = meta
        NEXT_MODE_KEY = mk

def _ensure_prefetch_thread(sfw: bool):
    global _PRELOAD_THREAD
    with _PRELOAD_LOCK:
        if _PRELOAD_THREAD is not None and _PRELOAD_THREAD.is_alive():
            return
        _PRELOAD_THREAD = threading.Thread(target=_prefetch_next, args=(sfw,), daemon=True)
        _PRELOAD_THREAD.start()

def _take_preload_if_matches(sfw: bool):
    global NEXT_BYTES, NEXT_PID, NEXT_META, NEXT_MODE_KEY

    mk = _mode_key(sfw)
    with _PRELOAD_LOCK:
        if NEXT_BYTES is not None and NEXT_PID is not None and NEXT_MODE_KEY == mk:
            b = NEXT_BYTES
            pid = NEXT_PID
            meta = NEXT_META or {"Source": "danbooru", "Author": "danbooru"}
            NEXT_BYTES = None
            NEXT_PID = None
            NEXT_META = None
            NEXT_MODE_KEY = None
            return b, pid, meta
    return None

# =========================
# SFW / NSFW
# =========================
def _danbooru_sfw():
    preload = _take_preload_if_matches(True)
    if preload:
        b, pid, meta = preload
        _write_response_bytes(b)
        _remember(pid)
        LAST_META.update(meta)
        _ensure_prefetch_thread(True)
        return True

    picked = _fetch_post(True)
    if not picked:
        _ensure_prefetch_thread(True)
        return ("Download error", {"errors": "Danbooru SFW: brak wyników"})

    pid, url, meta = picked
    b = _download_bytes(url)
    if not b:
        _ensure_prefetch_thread(True)
        return ("Download error", {"errors": "Danbooru SFW: download failed"})

    _write_response_bytes(b)
    _remember(pid)
    LAST_META.update(meta)
    _ensure_prefetch_thread(True)
    return True

def _danbooru_nsfw():
    preload = _take_preload_if_matches(False)
    if preload:
        b, pid, meta = preload
        _write_response_bytes(b)
        _remember(pid)
        LAST_META.update(meta)
        _ensure_prefetch_thread(False)
        return True

    picked = _fetch_post(False)
    if not picked:
        _ensure_prefetch_thread(False)
        return ("Download error", {"errors": "Danbooru NSFW: brak wyników"})

    pid, url, meta = picked
    b = _download_bytes(url)
    if not b:
        _ensure_prefetch_thread(False)
        return ("Download error", {"errors": "Danbooru NSFW: download failed"})

    _write_response_bytes(b)
    _remember(pid)
    LAST_META.update(meta)
    _ensure_prefetch_thread(False)
    return True

# =========================
def reloadimage():
    # odpal preload ASAP (nawet jeśli aktualny fetch się wysypie)
    if not app_state.is_nsfw():
        out = _danbooru_sfw()
        _ensure_prefetch_thread(True)
        return out
    out = _danbooru_nsfw()
    _ensure_prefetch_thread(False)
    return out

def getresponce():
    return LAST_META
