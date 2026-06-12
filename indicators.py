"""Visual indicators that work across Windows, X11 and Wayland.

Two ways to signal the user without printing anything:

* ``flash_caps_lock`` blinks the keyboard's Caps Lock LED, for the keyboards
  that have one.
* ``flash_corner_indicator`` blinks a tiny click-through square pinned to a
  screen corner.

Backends are picked the same way as the rest of the project: ``platform.system()``
plus the ``WAYLAND_DISPLAY`` env var (see ``listener.py`` / ``screenshot.py``).
"""

import os
import platform
import time

DEFAULT_INTERVAL = 0.15  # 150ms between on/off states


# --------------------------------------------------------------------------- #
# Caps Lock LED
# --------------------------------------------------------------------------- #
def flash_caps_lock(times: int, interval: float = DEFAULT_INTERVAL) -> None:
    """Blink the Caps Lock LED ``times`` times, leaving its state untouched.

    Windows has no per-LED API, so we toggle the Caps Lock *key* (the LED
    follows the lock state); each blink is two toggles, so the lock state nets
    back to where it started. Linux drives the LED directly through evdev,
    which sits at the kernel input layer and therefore works identically on
    X11 and Wayland without changing the lock state at all.
    """
    times = int(times)
    if times <= 0:
        return

    system = platform.system()
    if system == "Windows":
        _flash_caps_windows(times, interval)
    elif system == "Linux":
        _flash_caps_linux(times, interval)
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def _flash_caps_windows(times: int, interval: float) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    VK_CAPITAL = 0x14
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002

    def toggle() -> None:
        # A full press+release flips the Caps Lock lock state, which flips the
        # LED with it. 0x45 is the Caps Lock scan code.
        user32.keybd_event(VK_CAPITAL, 0x45, KEYEVENTF_EXTENDEDKEY, 0)
        user32.keybd_event(VK_CAPITAL, 0x45, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

    # Two toggles per blink means the lock state is always restored, so there
    # is no need to read (and risk mis-reading) the original state.
    for _ in range(times):
        toggle()
        time.sleep(interval)
        toggle()
        time.sleep(interval)


def _flash_caps_linux(times: int, interval: float) -> None:
    import evdev
    from evdev import ecodes

    devices: list[evdev.InputDevice[str]] = []
    for path in evdev.list_devices():  # pyright: ignore[reportUnknownMemberType]
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue  # device vanished or no permission
        if ecodes.LED_CAPSL in dev.capabilities().get(ecodes.EV_LED, []):
            devices.append(dev)
        else:
            dev.close()

    if not devices:
        raise RuntimeError(
            "No keyboard with a Caps Lock LED found. Driving the LED needs "
            "read/write access to /dev/input/event*; make sure you are in the "
            "'input' group: sudo usermod -aG input $USER"
        )

    # Remember each device's current LED state so a flash never leaves the
    # light stuck on/off if it happened to already be lit.
    original = {dev.path: (ecodes.LED_CAPSL in dev.leds()) for dev in devices}

    def set_all(on: bool) -> None:
        for dev in devices:
            try:
                dev.set_led(ecodes.LED_CAPSL, 1 if on else 0)
            except OSError:
                pass  # one flaky device shouldn't abort the rest

    try:
        for _ in range(times):
            set_all(True)
            time.sleep(interval)
            set_all(False)
            time.sleep(interval)
    finally:
        for dev in devices:
            try:
                dev.set_led(ecodes.LED_CAPSL, 1 if original[dev.path] else 0)
            except OSError:
                pass
            dev.close()


# --------------------------------------------------------------------------- #
# On-screen corner indicator
# --------------------------------------------------------------------------- #
_CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")


def flash_corner_indicator(
    times: int,
    interval: float = DEFAULT_INTERVAL,
    size: int = 8,
    corner: str = "top-right",
    on_color: str = "white",
    off_color: str = "black",
    title: str = "arlen-indicator",
    window_class: str = "arlen-indicator",
    managed_by_compositor: bool = False,
) -> None:
    """Blink a tiny borderless click-through square in a screen corner.

    The window is ``size`` x ``size`` pixels (e.g. 4 or 8), always-on-top,
    kept out of the taskbar, and transparent to mouse input so clicks land on
    whatever is underneath. It blinks ``on_color`` then ``off_color`` ``times``
    times with ``interval`` seconds between states. ``update()`` is called
    after every colour change so the window server paints each state instead of
    coalescing them into one repaint.

    Click-through is achieved with native window styles on Windows and with the
    X Shape extension's input region on X11. Under Wayland the GUI runs through
    XWayland, so the same X Shape trick still makes it click-through.

    ``title`` and ``window_class`` (the X11 WM_CLASS) are always set so a
    Wayland compositor can target the window with rules, e.g. Hyprland::

        windowrulev2 = float,    class:^(arlen-indicator)$
        windowrulev2 = pin,      class:^(arlen-indicator)$
        windowrulev2 = noborder, class:^(arlen-indicator)$
        windowrulev2 = nofocus,  class:^(arlen-indicator)$
        windowrulev2 = move 100%-8 0, class:^(arlen-indicator)$

    or Sway::

        for_window [class="arlen-indicator"] floating enable, border none, sticky enable

    Set ``managed_by_compositor=True`` on Wayland to leave the window managed
    (no override-redirect, no X Shape) and rely entirely on those rules for
    borderless/placement/click-through.

    Note: tkinter must run on the main thread, and this call blocks for roughly
    ``times * 2 * interval`` seconds while it flashes.
    """
    times = int(times)
    if times <= 0:
        return
    if corner not in _CORNERS:
        raise ValueError(f"corner must be one of {_CORNERS}, got {corner!r}")

    import tkinter as tk

    system = platform.system()
    is_wayland = system == "Linux" and bool(os.environ.get("WAYLAND_DISPLAY"))
    compositor_managed = is_wayland and managed_by_compositor

    root = tk.Tk(className=window_class)
    try:
        root.title(title)
        root.attributes("-topmost", True)
        root.configure(bg=off_color)

        # Override-redirect gives a borderless, taskbar-less, self-positioned
        # window on X11/Windows. We skip it only when the user wants the
        # Wayland compositor to manage the window via its own rules.
        if not compositor_managed:
            root.overrideredirect(True)

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x, y = _corner_position(corner, size, sw, sh)
        root.geometry(f"{size}x{size}+{x}+{y}")

        # Realise and map the window so it has a server-side handle before we
        # poke at its native styles / input region.
        root.update_idletasks()
        root.update()

        if not compositor_managed:
            if system == "Windows":
                _click_through_windows(root.winfo_id())
            elif system == "Linux":
                _click_through_x11(root.winfo_id())

        for _ in range(times):
            root.configure(bg=on_color)
            root.update()  # force a repaint now, don't let states batch
            time.sleep(interval)
            root.configure(bg=off_color)
            root.update()
            time.sleep(interval)
    finally:
        root.destroy()


def _corner_position(corner: str, size: int, sw: int, sh: int) -> tuple[int, int]:
    right = max(sw - size, 0)
    bottom = max(sh - size, 0)
    return {
        "top-left": (0, 0),
        "top-right": (right, 0),
        "bottom-left": (0, bottom),
        "bottom-right": (right, bottom),
    }[corner]


def _click_through_windows(window_id: int) -> None:
    """Make a Win32 window pass mouse input straight through.

    WS_EX_LAYERED + WS_EX_TRANSPARENT is the standard click-through combo;
    WS_EX_TOOLWINDOW keeps it out of the taskbar/alt-tab and WS_EX_NOACTIVATE
    stops it stealing focus. SetLayeredWindowAttributes is required for a
    layered window to actually paint.
    """
    import ctypes
    from ctypes import wintypes

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    LWA_ALPHA = 0x02

    user32 = ctypes.windll.user32
    user32.GetParent.restype = wintypes.HWND
    user32.GetParent.argtypes = [wintypes.HWND]

    # Tk hands us the content window; the real top-level may be its parent.
    hwnd = user32.GetParent(window_id) or window_id

    # On 64-bit Windows the *Ptr variants must be used; fall back for 32-bit.
    get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
    set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
    get_long.restype = ctypes.c_void_p
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    set_long.restype = ctypes.c_void_p
    set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]

    style = get_long(hwnd, GWL_EXSTYLE) or 0
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    set_long(hwnd, GWL_EXSTYLE, style)

    user32.SetLayeredWindowAttributes.argtypes = [
        wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD,
    ]
    user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)


def _click_through_x11(window_id: int) -> None:
    """Make an X11 (or XWayland) window pass mouse input straight through.

    Setting the window's *input* shape to an empty region via the X Shape
    extension means the pointer never lands on it. We open our own display
    connection because tkinter doesn't expose its Display* pointer; X lets any
    client reshape a window by its (global) XID. XWayland forwards the input
    shape to the Wayland surface, so this also works under Wayland. Failures
    are swallowed: a missing libXext just means no click-through, not a crash.
    """
    import ctypes

    ShapeInput = 2  # vs ShapeBounding/ShapeClip
    ShapeSet = 0
    Unsorted = 0

    try:
        x11 = ctypes.CDLL("libX11.so.6")
        xext = ctypes.CDLL("libXext.so.6")
    except OSError:
        return

    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    dpy = x11.XOpenDisplay(None)
    if not dpy:
        return

    try:
        xext.XShapeCombineRectangles.argtypes = [
            ctypes.c_void_p,  # Display *
            ctypes.c_ulong,   # Window
            ctypes.c_int,     # kind (ShapeInput)
            ctypes.c_int,     # x offset
            ctypes.c_int,     # y offset
            ctypes.c_void_p,  # XRectangle * (NULL => empty)
            ctypes.c_int,     # n_rects (0 => empty)
            ctypes.c_int,     # op (ShapeSet)
            ctypes.c_int,     # ordering
        ]
        xext.XShapeCombineRectangles(
            dpy, ctypes.c_ulong(window_id), ShapeInput, 0, 0, None, 0, ShapeSet, Unsorted
        )
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XFlush(dpy)
    finally:
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay(dpy)


if __name__ == "__main__":
    # Quick manual smoke test: blink the LED, then the corner square.
    print("flashing caps lock LED 3x…")
    try:
        flash_caps_lock(3)
    except RuntimeError as exc:
        print(f"  skipped: {exc}")
    print("flashing corner indicator 3x…")
    flash_corner_indicator(3, corner="top-right")
