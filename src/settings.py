import gi
gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk  # type: ignore

import app_state


class settingswindow(Adw.PreferencesWindow):
    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("Preferences")

        page = Adw.PreferencesPage(title="Content")
        group = Adw.PreferencesGroup(title="Filters")

        self.nsfw = Adw.SwitchRow(
            title="NSFW",
            subtitle="Treści NSFW (Danbooru)",
        )
        self.nsfw.set_active(app_state.is_nsfw())
        self.nsfw.connect("notify::active", self._on_nsfw)
        group.add(self.nsfw)

        # --- NSFW LEVEL (soft <-> hardcore) ---
        self.nsfw_level_row = Adw.ActionRow(
            title="NSFW accuracy",
            subtitle=self._level_subtitle(app_state.get_nsfw_level()),
        )

        adj = Gtk.Adjustment(
            value=float(app_state.get_nsfw_level()),
            lower=0.0,
            upper=100.0,
            step_increment=1.0,
            page_increment=10.0,
            page_size=0.0,
        )
        self.nsfw_level = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=adj,
        )
        self.nsfw_level.set_digits(0)
        self.nsfw_level.set_hexpand(True)
        self.nsfw_level.connect("value-changed", self._on_nsfw_level)

        self.nsfw_level_row.add_suffix(self.nsfw_level)
        self.nsfw_level_row.set_activatable_widget(self.nsfw_level)
        group.add(self.nsfw_level_row)

        self.astolfo = Adw.SwitchRow(
            title="Astolfo mode",
            subtitle="Wymusza tag 'astolfo'",
        )
        self.astolfo.set_active(app_state.is_astolfo())
        self.astolfo.connect("notify::active", self._on_astolfo)
        group.add(self.astolfo)

        self.genshin = Adw.SwitchRow(
            title="Genshin mode",
            subtitle="Wymusza tagi 'genshin_impact femboy'",
        )
        self.genshin.set_active(app_state.is_genshin())
        self.genshin.connect("notify::active", self._on_genshin)
        group.add(self.genshin)

        page.add(group)
        self.add(page)

    def _level_subtitle(self, v: int) -> str:
        if v <= 30:
            return "Soft (więcej vibe, mniej wymagań)"
        if v <= 70:
            return "Balanced (mniej randomów)"
        return "Hardcore (maks femboy accuracy)"

    def _on_nsfw(self, row, _):
        app_state.set_nsfw(row.get_active())

    def _on_nsfw_level(self, scale):
        v = int(scale.get_value())
        app_state.set_nsfw_level(v)
        self.nsfw_level_row.set_subtitle(self._level_subtitle(v))

    def _on_astolfo(self, row, _):
        app_state.set_astolfo(row.get_active())

    def _on_genshin(self, row, _):
        app_state.set_genshin(row.get_active())
