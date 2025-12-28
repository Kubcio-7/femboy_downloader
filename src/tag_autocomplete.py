import threading
import requests
from gi.repository import Gtk, GLib  # type: ignore

# Blokowane (Twoje + bezpieczeństwo)
BLOCKED_TOKENS = {
    "female", "girl", "1girl", "2girls", "3girls",
    "child", "children", "kid", "minor", "underage", "young", "teen",
    "loli", "lolicon", "shota", "shotacon", "toddler", "baby",
    "schoolgirl", "schoolboy", "middle_school", "elementary_school",
}

# Mapowanie źródło -> endpoint podpowiedzi tagów
# Danbooru: JSON tags.json
DANBOORU_TAGS = "https://danbooru.donmai.us/tags.json"

# DAPI booru: tag index (zwykle działa tak samo)
DAPI_TAG_ENDPOINTS = {
    "gelbooru": "https://gelbooru.com/index.php",
    "rule34": "https://api.rule34.xxx/index.php",
    "realbooru": "https://realbooru.com/index.php",
    "safebooru": "https://safebooru.org/index.php",
}

# (opcjonalnie) spróbujemy też:
YANDERE_TAGS = "https://yande.re/tag.json"
E621_TAGS = "https://e621.net/tags.json"


def _norm_tokens(text: str) -> list[str]:
    cleaned = " ".join((text or "").replace(",", " ").split()).strip().lower()
    return cleaned.split() if cleaned else []


def _current_prefix(entry_text: str) -> str:
    t = entry_text.rstrip()
    if not t:
        return ""
    parts = t.split()
    return parts[-1] if parts else ""


def _replace_last_token(entry_text: str, new_token: str) -> str:
    parts = entry_text.rstrip().split()
    if not parts:
        return new_token + " "
    parts[-1] = new_token
    return " ".join(parts) + " "


class TagAutocomplete:
    """
    Autocomplete + walidacja tagów na żywo (multi-source).
    Działa bez crashy na GTK4 (EventControllerFocus zamiast focus-out-event).
    """
    def __init__(self, entry: Gtk.Entry, parent_window: Gtk.Window):
        self.entry = entry
        self.parent = parent_window

        self._debounce_id = 0
        self._cache: dict[tuple[str, str], list[str]] = {}  # (source, prefix) -> [tags]
        self._last_prefix = ""
        self._selected_source_getter = None

        # Popover z listą
        self.popover = Gtk.Popover()
        self.popover.set_has_arrow(False)
        self.popover.set_position(Gtk.PositionType.BOTTOM)
        self.popover.set_parent(self.entry)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", self._on_row_activated)
        self.popover.set_child(self.listbox)

        # GTK4: focus leave przez EventControllerFocus
        focus = Gtk.EventControllerFocus.new()
        focus.connect("leave", lambda *_: self.popover.popdown())
        self.entry.add_controller(focus)

        # Events
        self.entry.connect("changed", self._on_changed)

    def set_source_getter(self, fn):
        self._selected_source_getter = fn

    def _get_source(self) -> str:
        try:
            return (self._selected_source_getter() if self._selected_source_getter else "danbooru") or "danbooru"
        except Exception:
            return "danbooru"

    def _on_changed(self, *_):
        if self._debounce_id:
            GLib.source_remove(self._debounce_id)
        self._debounce_id = GLib.timeout_add(180, self._debounced_fetch)

    def _debounced_fetch(self):
        self._debounce_id = 0
        text = self.entry.get_text()
        prefix = _current_prefix(text)

        if not prefix or len(prefix) < 2:
            self.popover.popdown()
            return False

        if prefix.lower() in BLOCKED_TOKENS:
            self._show_suggestions([f"⛔ {prefix} (zablokowany tag)"], blocked=True)
            return False

        src = self._get_source()

        key = (src, prefix)
        if key in self._cache:
            self._show_suggestions(self._cache[key])
            return False

        self._last_prefix = prefix
        threading.Thread(target=self._fetch_tags_for_source, args=(src, prefix), daemon=True).start()
        return False

    def _fetch_tags_for_source(self, src: str, prefix: str):
        try:
            out: list[str] = []

            if src == "danbooru":
                out = self._fetch_danbooru(prefix)

            elif src in DAPI_TAG_ENDPOINTS:
                out = self._fetch_dapi_tags(DAPI_TAG_ENDPOINTS[src], prefix)

            elif src == "yandere":
                out = self._fetch_yandere(prefix)

            elif src == "e621":
                out = self._fetch_e621(prefix)

            # cache + UI
            self._cache[(src, prefix)] = out
            GLib.idle_add(self._show_suggestions, out)

        except Exception:
            GLib.idle_add(self.popover.popdown)

    def _fetch_danbooru(self, prefix: str) -> list[str]:
        params = {"search[name_matches]": f"{prefix}*", "limit": 20}
        r = requests.get(DANBOORU_TAGS, params=params, timeout=10)
        data = r.json()

        out = []
        if isinstance(data, list):
            for t in data:
                name = (t or {}).get("name")
                if isinstance(name, str) and name:
                    out.append(name)
        return out

    def _fetch_dapi_tags(self, base_url: str, prefix: str) -> list[str]:
        # Standard booru DAPI tag index
        params = {
            "page": "dapi",
            "s": "tag",
            "q": "index",
            "json": 1,
            "limit": 30,
            "name_pattern": f"{prefix}*",
            # fallback param (niektóre booru używają "name" zamiast "name_pattern")
            "name": prefix,
        }
        r = requests.get(base_url, params=params, timeout=10)
        data = r.json()

        out = []
        if isinstance(data, list):
            for t in data:
                name = (t or {}).get("name")
                if isinstance(name, str) and name:
                    out.append(name)
        return out

    def _fetch_yandere(self, prefix: str) -> list[str]:
        # yande.re tag.json (zwykle: name=prefix lub name_matches)
        params = {"name": prefix, "limit": 20}
        r = requests.get(YANDERE_TAGS, params=params, timeout=10)
        data = r.json()

        out = []
        if isinstance(data, list):
            for t in data:
                name = (t or {}).get("name")
                if isinstance(name, str) and name:
                    out.append(name)
        return out

    def _fetch_e621(self, prefix: str) -> list[str]:
        # e621 tags.json (różnie bywa; próbujemy “search[name_matches]”)
        params = {"search[name_matches]": f"{prefix}*", "limit": 20}
        r = requests.get(E621_TAGS, params=params, timeout=10)
        data = r.json()

        out = []
        if isinstance(data, list):
            for t in data:
                name = (t or {}).get("name")
                if isinstance(name, str) and name:
                    out.append(name)
        return out

    def _show_suggestions(self, items: list[str], blocked: bool = False):
        if not blocked:
            cur_prefix = _current_prefix(self.entry.get_text())
            if cur_prefix != self._last_prefix:
                return

        # Clear listbox
        child = self.listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt

        if not items:
            self.popover.popdown()
            return

        for s in items[:20]:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=s, xalign=0)
            row.set_child(lbl)
            self.listbox.append(row)

        self.popover.popup()

    def _on_row_activated(self, _lb, row: Gtk.ListBoxRow):
        label = row.get_child()
        if not isinstance(label, Gtk.Label):
            return
        text = label.get_text()

        if text.startswith("⛔"):
            return

        new_text = _replace_last_token(self.entry.get_text(), text)
        self.entry.set_text(new_text)
        self.entry.set_position(len(new_text))
        self.popover.popdown()

    def validate_or_error(self) -> tuple[bool, str]:
        """
        “Tylko poprawne tagi” – walidujemy pod aktualne źródło.
        Jeśli nie umiemy zweryfikować (endpoint nie działa) -> nie blokujemy na siłę,
        bo lepszy UX to pozwolić i ewentualnie źródło zwróci “no posts”.
        """
        src = self._get_source()
        tokens = _norm_tokens(self.entry.get_text())

        for t in tokens:
            if t in BLOCKED_TOKENS:
                return False, f"Zablokowany tag: {t}"

        # sprawdzamy każdy token: czy istnieje (best-effort)
        for t in tokens:
            ok = self._exists_tag(src, t)
            if ok is False:
                return False, f"Nieznany tag: {t}"
            # ok is None => nie umiemy sprawdzić (nie blokuj)

        return True, ""

    def _exists_tag(self, src: str, tag: str):
        # True/False/None (None = nie umiemy sprawdzić)
        try:
            # jeżeli tag był w cache jako sugestia => OK
            for (s, _p), lst in self._cache.items():
                if s == src and tag in lst:
                    return True

            if src == "danbooru":
                params = {"search[name]": tag, "limit": 1}
                r = requests.get(DANBOORU_TAGS, params=params, timeout=10)
                data = r.json()
                if isinstance(data, list) and data:
                    return (data[0] or {}).get("name") == tag
                return False

            if src in DAPI_TAG_ENDPOINTS:
                base = DAPI_TAG_ENDPOINTS[src]
                params = {"page":"dapi","s":"tag","q":"index","json":1,"limit":1,"name":tag}
                r = requests.get(base, params=params, timeout=10)
                data = r.json()
                if isinstance(data, list) and data:
                    return (data[0] or {}).get("name") == tag
                return False

            if src == "yandere":
                params = {"name": tag, "limit": 1}
                r = requests.get(YANDERE_TAGS, params=params, timeout=10)
                data = r.json()
                if isinstance(data, list) and data:
                    return (data[0] or {}).get("name") == tag
                return False

            if src == "e621":
                params = {"search[name]": tag, "limit": 1}
                r = requests.get(E621_TAGS, params=params, timeout=10)
                data = r.json()
                if isinstance(data, list) and data:
                    return (data[0] or {}).get("name") == tag
                return False

            return None
        except Exception:
            return None
