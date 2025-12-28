import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools import log, log_error


def _tmp_image_path() -> Path:
    return Path(tempfile.gettempdir()) / "femboydownloader" / "response.jpg"


def download(save_path: str):
    try:
        src = _tmp_image_path()
        if not src.exists():
            log_error(f"Brak pliku do zapisania: {src}")
            return

        shutil.copy(str(src), save_path)
        log(f"File successfully saved to: {save_path}")

    except Exception as e:
        log_error(f"Error saving file: {e}")


def wallpaper():
    try:
        src = _tmp_image_path()
        if not src.exists():
            log_error(f"Brak pliku do ustawienia tapety: {src}")
            return

        scriptpath = Path(__file__).parent / "set_wallpaper"

        destination_dir = Path(os.path.expanduser("~")) / ".config" / "wallpaper"
        destination_dir.mkdir(parents=True, exist_ok=True)

        dst = destination_dir / "wallpaper.jpg"
        shutil.copy(str(src), str(dst))

        subprocess.run(["/bin/bash", str(scriptpath), str(dst)], check=False)

    except Exception as e:
        log_error(f"An error occurred: {e}")
