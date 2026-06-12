import os
import platform

from session import CaptureSession


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

    session = CaptureSession()

    def on_press(key: object) -> None:
        try:
            char = getattr(key, "char", None)
            if char == "[":
                session.capture()
            elif char == "]":
                session.finish()
        except Exception as exc:
            print(f"[listener] error: {exc}")

    print("[listener] Listening for '[' (capture) and ']' (finish) via pynput (Windows/X11)…")
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
    devices: list[evdev.InputDevice[str]] = []
    for p in device_paths:
        try:
            devices.append(evdev.InputDevice(p))
        except OSError:
            continue  # no permission or device vanished; skip it instead of crashing the whole listener
    keyboards: list[evdev.InputDevice[str]] = [d for d in devices if ecodes.EV_KEY in d.capabilities()]

    if not keyboards:
        raise RuntimeError(
            "No keyboard input devices found. "
            + "Make sure you are in the 'input' group: sudo usermod -aG input $USER"
        )

    print(f"[listener] Listening for '[' (capture) and ']' (finish) via evdev on {len(keyboards)} device(s)…")

    session = CaptureSession()

    async def _handle(device: evdev.InputDevice[str]) -> None:
        try:
            async for event in cast(_AsyncEventIO, device).async_read_loop():
                if event.type == ecodes.EV_KEY and event.value == _KEY_DOWN:
                    if event.code == ecodes.KEY_LEFTBRACE:
                        print("[ detected, taking screenshot…")
                        session.capture()
                    elif event.code == ecodes.KEY_RIGHTBRACE:
                        print("] detected, finishing burst…")
                        session.finish()
        except asyncio.CancelledError:
            return

    async def _run() -> None:
        _ = await asyncio.gather(*[_handle(d) for d in keyboards])

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
