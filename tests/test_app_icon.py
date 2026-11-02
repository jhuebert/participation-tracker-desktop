"""Windows app icon asset tests."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_app_icon_contains_common_windows_sizes():
    icon_path = ROOT / "assets" / "icon.ico"
    with Image.open(icon_path) as icon:
        assert icon.format == "ICO"
        assert set(icon.ico.sizes()) >= {
            (16, 16), (32, 32), (48, 48), (256, 256)
        }


def test_app_icon_source_is_bundled():
    with Image.open(ROOT / "assets" / "student_raising_hand.png") as source:
        assert source.width == source.height
        assert source.width >= 256
