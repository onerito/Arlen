# Arlen

A cross-platform full-desktop screenshot utility that returns a PIL `Image` object and optionally saves it to disk.

Supports Windows, Linux/X11, and Linux/Wayland.

## Usage

```python
from main import take_screenshot

# Return image only
img = take_screenshot()

# Return image and save to file
img = take_screenshot("screenshot.png")
```

## Dependencies

### Python Package

| Package | Install |
|---------|---------|
| Pillow | `pip install Pillow` |

### Linux

#### X11

Pillow's `ImageGrab` is attempted first. If it fails, `scrot` is used as a fallback.

| Tool | Install |
|------|---------|
| scrot (fallback) | `sudo apt install scrot` / `sudo pacman -S scrot` |

> Note: `python3-xlib` or `python3-tk` may be required for `ImageGrab` on X11 depending on your distro.

#### Wayland

One of the following tools must be installed:

| Tool | Desktop | Install |
|------|---------|---------|
| grim | wlroots / Sway | `sudo apt install grim` / `sudo pacman -S grim` |
| gnome-screenshot | GNOME | `sudo apt install gnome-screenshot` / `sudo pacman -S gnome-screenshot` |
| spectacle | KDE | `sudo apt install spectacle` / `sudo pacman -S spectacle` |

### Windows

No additional system tools required. Pillow's built-in `ImageGrab` handles screenshots natively.

| Package | Note |
|---------|------|
| Pillow | Includes `ImageGrab` for Windows — no extras needed |

## Quick Install

```bash
pip install Pillow
```

### Linux (Wayland — pick one)

```bash
# wlroots / Sway
sudo apt install grim

# GNOME
sudo apt install gnome-screenshot

# KDE
sudo apt install spectacle
```

### Linux (X11 fallback)

```bash
sudo apt install scrot
```
