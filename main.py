import os
import platform
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def take_screenshot(output_path: str | None = None) -> Image.Image:
    """Take a full-desktop screenshot. Returns a PIL Image.

    Args:
        output_path: Optional path to save the PNG. If None, image is only returned.

    Supports Windows, Linux/X11, and Linux/Wayland (grim, gnome-screenshot, spectacle).
    """
    system = platform.system()

    if system == "Windows":
        img = _screenshot_windows()
    elif system == "Linux":
        if os.environ.get("WAYLAND_DISPLAY"):
            img = _screenshot_wayland()
        else:
            img = _screenshot_x11()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    if output_path:
        img.save(output_path)

    return img


def _screenshot_windows() -> Image.Image:
    from PIL import ImageGrab
    return ImageGrab.grab(all_screens=True)


def _screenshot_x11() -> Image.Image:
    try:
        from PIL import ImageGrab
        return ImageGrab.grab()
    except Exception:
        pass

    # Fallback to scrot
    return _capture_with_cmd(["scrot", "{tmp}"])


def _screenshot_wayland() -> Image.Image:
    if _cmd_exists("grim"):
        return _capture_with_cmd(["grim", "{tmp}"])

    if _cmd_exists("gnome-screenshot"):
        return _capture_with_cmd(["gnome-screenshot", "--file={tmp}"])

    if _cmd_exists("spectacle"):
        # -b = background (no GUI), -f = fullscreen, -o = output
        return _capture_with_cmd(["spectacle", "-b", "-f", "-o", "{tmp}"])

    raise RuntimeError(
        "No Wayland screenshot tool found. Install grim (wlroots/Sway), gnome-screenshot (GNOME), or spectacle (KDE)."
    )


def _capture_with_cmd(cmd: list[str]) -> Image.Image:
    """Run a command that writes a screenshot to a temp file, return the image."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = f.name
    try:
        resolved = [arg.replace("{tmp}", tmp) for arg in cmd]
        _ = subprocess.run(resolved, check=True, capture_output=True)
        img = Image.open(tmp)
        _ = img.load()
        return img
    finally:
        Path(tmp).unlink(missing_ok=True)


def _cmd_exists(cmd: str) -> bool:
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0
