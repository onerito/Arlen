import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def take_screenshot(output_path: str | None = None) -> Image.Image:
    """Capture only the focused monitor (the one the cursor is on).

    Each backend grabs a single monitor natively, so the result never spans
    the whole virtual desktop (which can exceed API image size limits).
    """
    system = platform.system()

    if system == "Windows":
        img = _screenshot_mss()
    elif system == "Linux":
        if os.environ.get("WAYLAND_DISPLAY"):
            img = _screenshot_wayland()
        else:
            img = _screenshot_mss()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    if output_path:
        img.save(output_path)

    return img


def _screenshot_mss() -> Image.Image:
    """Windows / X11: enumerate monitors and grab just the focused one."""
    import mss

    with mss.mss() as sct:
        monitors = sct.monitors[1:]  # [0] is the full virtual desktop
        if not monitors:
            raise RuntimeError("No monitors detected")

        target = None
        try:
            from pynput.mouse import Controller

            cx, cy = Controller().position
            target = next(
                (
                    m
                    for m in monitors
                    if m["left"] <= cx < m["left"] + m["width"]
                    and m["top"] <= cy < m["top"] + m["height"]
                ),
                None,
            )
        except Exception:
            pass

        if target is None:
            target = monitors[0]

        raw = sct.grab(target)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def _screenshot_wayland() -> Image.Image:
    """Capture a single monitor on Wayland.

    wlroots compositors (Sway, Hyprland, river, Wayfire, ...) use grim, with
    the focused output resolved via compositor IPC where possible. KDE Plasma
    (KWin) uses spectacle's current-monitor mode. As a last resort grim grabs
    the whole desktop — which may exceed image size limits on multi-monitor
    setups, so it is only used when nothing better is available.
    """
    if _cmd_exists("grim"):
        output = _focused_wayland_output()
        if output:
            return _capture_with_cmd(["grim", "-o", output, "{tmp}"])

    # KDE Plasma: spectacle -m captures the monitor under the cursor.
    if _cmd_exists("spectacle"):
        return _capture_with_cmd(["spectacle", "-b", "-n", "-m", "-o", "{tmp}"])

    if _cmd_exists("grim"):
        # No way to identify a single output; grab everything as a fallback.
        return _capture_with_cmd(["grim", "{tmp}"])

    raise RuntimeError(
        "No usable Wayland screenshot tool found. Install grim (wlroots: Sway, "
        "Hyprland, river, Wayfire) or spectacle (KDE Plasma)."
    )


def _focused_wayland_output() -> str | None:
    """Return the name of the focused/active output for a wlroots compositor.

    Tries compositor IPC that reports which output is focused (Hyprland, then
    Sway), then falls back to wlr-randr (generic wlroots) which only lists
    outputs — there we pick the first enabled one so grim still captures a
    single monitor rather than the entire desktop. Returns None if no output
    can be identified.
    """
    if _cmd_exists("hyprctl"):
        try:
            data = json.loads(_run(["hyprctl", "monitors", "-j"]))
            for m in data:
                if m.get("focused"):
                    return m["name"]
            if data:
                return data[0]["name"]
        except Exception:
            pass

    if _cmd_exists("swaymsg"):
        try:
            data = json.loads(_run(["swaymsg", "-t", "get_outputs"]))
            for m in data:
                if m.get("focused"):
                    return m["name"]
            active = [m for m in data if m.get("active")]
            if active:
                return active[0]["name"]
        except Exception:
            pass

    if _cmd_exists("wlr-randr"):
        try:
            data = json.loads(_run(["wlr-randr", "--json"]))
            for o in data:
                if o.get("enabled", True):
                    return o["name"]
            if data:
                return data[0]["name"]
        except Exception:
            pass

    return None


def _run(cmd: list[str]) -> str:
    return subprocess.run(
        cmd, capture_output=True, text=True, check=True
    ).stdout


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
    return shutil.which(cmd) is not None
