import os
import platform
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def take_screenshot(output_path: str | None = None) -> Image.Image:
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

    img = _crop_to_focused(img)

    if output_path:
        img.save(output_path)

    return img


def _crop_to_focused(img: Image.Image) -> Image.Image:
    """Crop a full (all-monitors) grab down to the focused monitor.

    "Focused" = the monitor the mouse cursor is on, falling back to the
    primary monitor. If monitor info isn't available, returns img unchanged.
    """
    try:
        from screeninfo import get_monitors
        monitors = get_monitors()
    except Exception:
        return img

    if not monitors:
        return img

    target = None
    try:
        from pynput.mouse import Controller
        cx, cy = Controller().position
        target = next(
            (m for m in monitors
             if m.x <= cx < m.x + m.width and m.y <= cy < m.y + m.height),
            None,
        )
    except Exception:
        pass

    if target is None:
        target = next((m for m in monitors if m.is_primary), monitors[0])

    # The full grab's (0, 0) is the top-left of the bounding box of all
    # monitors, so offset each monitor's virtual coords by that corner.
    left = min(m.x for m in monitors)
    top = min(m.y for m in monitors)
    box = (
        target.x - left,
        target.y - top,
        target.x - left + target.width,
        target.y - top + target.height,
    )
    return img.crop(box)


def _screenshot_windows() -> Image.Image:
    from PIL import ImageGrab
    return ImageGrab.grab(all_screens=True)


def _screenshot_x11() -> Image.Image:
    try:
        from PIL import ImageGrab
        return ImageGrab.grab()
    except Exception:
        pass

    return _capture_with_cmd(["scrot", "{tmp}"])


def _screenshot_wayland() -> Image.Image:
    if _cmd_exists("grim"):
        return _capture_with_cmd(["grim", "{tmp}"])

    if _cmd_exists("gnome-screenshot"):
        return _capture_with_cmd(["gnome-screenshot", "--file={tmp}"])

    if _cmd_exists("spectacle"):
        return _capture_with_cmd(["spectacle", "-b", "-f", "-o", "{tmp}"])

    raise RuntimeError(
        "No Wayland screenshot tool found. Install grim (wlroots/Sway), gnome-screenshot (GNOME), or spectacle (KDE)."
    )


def _capture_with_cmd(cmd: list[str]) -> Image.Image:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = f.name
    try:
        resolved = [arg.replace("{tmp}", tmp) for arg in cmd]
        _ = subprocess.run(resolved, check=True, capture_output=True, start_new_session=True)
        img = Image.open(tmp)
        _ = img.load()
        return img
    finally:
        Path(tmp).unlink(missing_ok=True)


def _cmd_exists(cmd: str) -> bool:
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0
