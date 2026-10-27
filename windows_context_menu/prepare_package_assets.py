"""Generate MSIX manifest PNG assets from the existing Screenshooter icon."""

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "screenshooter" / "resources" / "icon.ico"
OUTPUT = Path(__file__).resolve().parent / "package_assets" / "Assets"


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Application icon not found: {SOURCE}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as image:
        image = image.convert("RGBA")
        for name, size in (
            ("StoreLogo.png", (50, 50)),
            ("Square150x150Logo.png", (150, 150)),
            ("Square44x44Logo.png", (44, 44)),
        ):
            image.resize(size, Image.Resampling.LANCZOS).save(OUTPUT / name)

    print(f"Package assets generated in: {OUTPUT}")


if __name__ == "__main__":
    main()
