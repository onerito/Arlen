import os
import platform
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

script_dir = Path(__file__).parent
SCREENSHOT_PATH = str(script_dir / "mrbeast.png")


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


def on_screenshot(img: Image.Image, path: str) -> None:
    # resume here and shit
    


def start_listener() -> None:
    system = platform.system()
    if system == "Windows":
        _listen_pynput()
    elif system == "Linux":
        if os.environ.get("WAYLAND_DISPLAY"):
            _listen_evdev()
        else:
            _listen_pynput()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def _listen_pynput() -> None:
    from pynput import keyboard

    def on_press(key: object) -> None:
        try:
            if getattr(key, "char", None) == "]":
                img = take_screenshot(SCREENSHOT_PATH)
                on_screenshot(img, SCREENSHOT_PATH)
        except Exception as exc:
            print(f"[listener] error: {exc}")

    print("[listener] Listening for ']' via pynput (Windows/X11)…")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


def _listen_evdev() -> None:
    import asyncio
    from typing import cast
    import evdev
    from evdev import ecodes
    from evdev.eventio_async import EventIO as _AsyncEventIO

    _KEY_DOWN = 1

    device_paths: list[str] = evdev.list_devices()  # pyright: ignore[reportUnknownMemberType]
    devices: list[evdev.InputDevice[str]] = [evdev.InputDevice(p) for p in device_paths]
    keyboards: list[evdev.InputDevice[str]] = [d for d in devices if ecodes.EV_KEY in d.capabilities()]

    if not keyboards:
        raise RuntimeError(
            "No keyboard input devices found. "
            + "Make sure you are in the 'input' group: sudo usermod -aG input $USER"
        )

    print(f"[listener] Listening for ']' via evdev on {len(keyboards)} device(s)…")

    async def _handle(device: evdev.InputDevice[str]) -> None:
        try:
            async for event in cast(_AsyncEventIO, device).async_read_loop():
                if event.type == ecodes.EV_KEY and event.value == _KEY_DOWN and event.code == ecodes.KEY_RIGHTBRACE:
                    print("] detected, taking screenshot…")
                    img = take_screenshot(SCREENSHOT_PATH)
                    on_screenshot(img, SCREENSHOT_PATH)
        except asyncio.CancelledError:
            return

    async def _run() -> None:
        _ = await asyncio.gather(*[_handle(d) for d in keyboards])

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    start_listener()
