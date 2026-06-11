from pathlib import Path

from PIL import Image

from handler import on_screenshot
from screenshot import take_screenshot

script_dir = Path(__file__).parent
SCREENSHOT_PATH = str(script_dir / "mrbeast.png")


def _indexed_path(index: int) -> str:
    p = Path(SCREENSHOT_PATH)
    return str(p.with_name(f"{p.stem}_{index}{p.suffix}"))


class CaptureSession:
    """Accumulates screenshots taken with '[' until ']' ends the burst."""

    def __init__(self) -> None:
        self.images: list[Image.Image] = []
        self.paths: list[str] = []

    def capture(self) -> None:
        index = len(self.images)
        path = _indexed_path(index)
        img = take_screenshot(path)
        self.images.append(img)
        self.paths.append(path)
        print(f"[capture] screenshot {index} saved to {path}")

    def finish(self) -> None:
        if not self.images:
            # ']' pressed without a '[' burst: take a single screenshot, then run on_screenshot.
            print("[capture] ']' pressed alone, taking a single screenshot…")
            self.capture()
        print(f"[capture] ']' pressed, handing {len(self.images)} screenshot(s) to on_screenshot")
        on_screenshot(self.images, self.paths)
        self.images = []
        self.paths = []
