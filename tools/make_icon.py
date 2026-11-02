"""Generate a multi-resolution Windows app icon from the supplied PNG."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "student_raising_hand.png"
DESTINATION = ROOT / "assets" / "icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) == 2 else SOURCE
    if len(sys.argv) > 2:
        print("Usage: python tools/make_icon.py [path/to/icon.png]")
        return 2
    try:
        with Image.open(source) as image:
            image.load()
            image = image.convert("RGBA")
    except OSError as exc:
        print(f"Could not read image {source}: {exc}")
        return 1
    if image.width != image.height:
        # Icons must be square; crop from the center if the supplied image is not.
        side = min(image.size)
        left = (image.width - side) // 2
        top = (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side))

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    image.save(DESTINATION, format="ICO", sizes=[(size, size) for size in SIZES])
    print(f"Wrote {DESTINATION.relative_to(ROOT)} with sizes {', '.join(map(str, SIZES))} px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())