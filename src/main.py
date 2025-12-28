import sys
import gi
import threading
import os
from pathlib import Path
import tempfile

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, Adw, GLib  # type: ignore

import buttons as buttons
import booru as jp
from settings import settingswindow
from tools import log, log_error

apppath = str(Path(__file__).parent.parent / "data" / "main.ui")


class femboydownloaderApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(
            application_id="moe.wawa.femboydownloader",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

        self.create_action("quit", self.quit, ["<primary>q"])
        self.create_action("about", self.on_about_action)
        self.create_action("show-art-about", self.on_art_about_action)

        self.app_icon = str(Path(__file__).parent.parent / "data" / "icon.png")

    def do_activate(self):
        builder = Gtk.Builder()
        builder.add_from_file(apppath)

        self.win = builder.get_object("main")
        self.win.set_application(self)
        self.win.set_title("Femboy Downloader")

        self.settings = builder.get_object("settings")
        self.download = builder.get_object("download")
        self.wallpaper = builder.get_object("wallpaper")
        self.refresh = builder.get_object("refresh")

        self.settings.connect("clicked", self.on_settings_action)
        self.download.connect("clicked", self.on_download_action)
        self.wallpaper.connect("clicked", self.on_wallpaper_action)
        self.refresh.connect("clicked", self.async_on_refresh_action)

        self.image = builder.get_object("image")      # GtkPicture (po zmianie w UI)
        self.spinner = builder.get_object("spinner")

        self.spinner.stop()
        self.spinner.set_visible(False)

        self.win.present()

        path = Path(tempfile.gettempdir()) / "femboydownloader" / "response.jpg"
        self.image.set_file(Gio.File.new_for_path(str(path)))

    def on_about_action(self, widget, _):
        about = Adw.AboutWindow(
            transient_for=self.win,
            application_name="femboy Downloader",
            application_icon=self.app_icon,
            developer_name="wawa",
            version="0.0.1",
            developers=["Princess_wawa"],
            copyright="© 2025 princess_wawa",
        )
        about.present()

    def on_art_about_action(self, widget, _):
        response = jp.getresponce()
        if response.get("Source"):
            about = Adw.AboutWindow(
                transient_for=self.props.active_window,
                artists=[f"u/{response.get('Author', '')}"],
                website=response["Source"],
            )
        else:
            about = Adw.AboutWindow(
                transient_for=self.props.active_window,
                artists=[f"u/{response.get('Author', '')}"],
            )
        about.present()

    def on_settings_action(self, widget):
        log("Opening preferences window.")
        active_window = self.get_active_window()
        if not active_window:
            log_error("No active window found.")
            return
        prefs = settingswindow(active_window)
        prefs.present()

    def on_download_action(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Save File",
            action=Gtk.FileChooserAction.SAVE,
        )

        downloads_folder = str(Path(os.path.expanduser("~")) / "Downloads")
        dialog.set_current_folder(Gio.File.new_for_path(downloads_folder))

        dialog.set_current_name("downloaded_wallpaper.jpg")
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.ACCEPT)

        def on_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                save_path = dialog.get_file().get_path()
                log(f"File will be saved to: {save_path}")
                buttons.download(save_path)
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def on_wallpaper_action(self, widget):
        buttons.wallpaper()

    def show_error_dialog(self, aaa, title, message):
        dialog = Adw.AlertDialog.new(title, None)
        dialog.set_body(message)
        dialog.add_response("ok", "_OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.connect("response", self.on_response)
        dialog.present(self.refresh)

    def on_response(self, dialog, response):
        return

    def async_on_refresh_action(self, widget=None):
        # UI (main thread)
        self.image.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

        # Worker thread (NO GTK here)
        t = threading.Thread(target=self.on_refresh_action, daemon=True)
        t.start()

    def on_refresh_action(self):
        a = jp.reloadimage()
        path = Path(tempfile.gettempdir()) / "femboydownloader" / "response.jpg"

        def update_ui():
            # GTK update MUST be in main thread
            self.image.set_file(Gio.File.new_for_path(str(path)))
            self.spinner.stop()
            self.spinner.set_visible(False)
            self.image.set_visible(True)

            if a is not True:
                error = a[1].get("errors", "Unknown error")
                log_error(f"{a[0]}, {a[1]}")
                self.show_error_dialog(self, str(a[0]), str(error))

            return False

        GLib.idle_add(update_ui)

    def create_action(self, name, callback, shortcuts=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main():
    app = femboydownloaderApplication()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
