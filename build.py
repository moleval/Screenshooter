"""
Скрипт сборки exe с автоинкрементом номера сборки.

Использование:
    python build.py            # onefile + windowed
    python build.py --console  # для отладки
    python build.py --onedir   # папка вместо одного файла
    python build.py --no-increment  # пересборка текущего номера
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "screenshooter" / "version.py"
VERSION_INFO_FILE = ROOT / "build" / "file_version_info.txt"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"

BUILD_PATTERN = re.compile(r"^BUILD\s*=\s*(\d+)\s*$", re.MULTILINE)
VERSION_PATTERN = re.compile(r'^VERSION\s*=\s*"([^"]+)"\s*$', re.MULTILINE)

VERSION_INFO_TEMPLATE = """\\
# UTF-8
#
# Файл сгенерирован build.py. Не редактировать вручную.

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v0}, {v1}, {v2}, {build}),
    prodvers=({v0}, {v1}, {v2}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Screenshooter'),
            StringStruct('FileDescription', 'Screenshooter — редактор скриншотов'),
            StringStruct('FileVersion', '{version}.{build}'),
            StringStruct('InternalName', 'Screenshooter'),
            StringStruct('LegalCopyright', '© Screenshooter'),
            StringStruct('OriginalFilename', 'Screenshooter.exe'),
            StringStruct('ProductName', 'Screenshooter'),
            StringStruct('ProductVersion', '{version}.{build}'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def read_version() -> tuple[str, int]:
    text = VERSION_FILE.read_text(encoding="utf-8")

    version_match = VERSION_PATTERN.search(text)
    build_match = BUILD_PATTERN.search(text)

    if not version_match or not build_match:
        raise RuntimeError(
            "Не найдены VERSION или BUILD в screenshooter/version.py"
        )

    return version_match.group(1), int(build_match.group(1))


def increment_build() -> tuple[str, int, int]:
    """Увеличивает BUILD и возвращает (version, old_build, new_build)."""
    text = VERSION_FILE.read_text(encoding="utf-8")

    version_match = VERSION_PATTERN.search(text)
    build_match = BUILD_PATTERN.search(text)

    if not version_match or not build_match:
        raise RuntimeError(
            "Не найдены VERSION или BUILD в screenshooter/version.py"
        )

    version = version_match.group(1)
    old_build = int(build_match.group(1))
    new_build = old_build + 1

    text = BUILD_PATTERN.sub(f"BUILD = {new_build}", text, count=1)
    VERSION_FILE.write_text(text, encoding="utf-8")

    return version, old_build, new_build


def generate_version_info(version: str, build: int) -> Path:
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")

    try:
        v0, v1, v2 = (int(x) for x in parts[:3])
    except ValueError as exc:
        raise RuntimeError(
            f"VERSION должна иметь числовой формат X.Y.Z: {version!r}"
        ) from exc

    VERSION_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_INFO_FILE.write_text(
        VERSION_INFO_TEMPLATE.format(
            v0=v0,
            v1=v1,
            v2=v2,
            version=version,
            build=build,
        ),
        encoding="utf-8",
    )
    return VERSION_INFO_FILE


def build_exe(console: bool, onedir: bool, no_increment: bool) -> None:
    if no_increment:
        version, build = read_version()
        print(f"Сборка без инкремента: {version}.{build}")
    else:
        version, old_build, build = increment_build()
        print(f"Инкремент BUILD: {old_build} -> {build}")

    version_info = generate_version_info(version, build)
    print(f"Version info: {version_info}")

    mode_flag = "--onedir" if onedir else "--onefile"
    console_flag = "--console" if console else "--windowed"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        mode_flag,
        console_flag,
        "--name",
        "Screenshooter",
        "--icon",
        "screenshooter/resources/icon.ico",
        "--add-data",
        "screenshooter/resources;screenshooter/resources",
        "--hidden-import",
        "keyboard._winkeyboard",
        "--hidden-import",
        "keyboard._generic",
        "--hidden-import",
        "win32timezone",
        "--version-file",
        str(version_info),
        "main.py",
    ]

    print("Команда:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)

    if result.returncode != 0:
        print(f"PyInstaller завершился с кодом {result.returncode}")
        sys.exit(result.returncode)

    exe_path = (
        DIST_DIR / "Screenshooter" / "Screenshooter.exe"
        if onedir
        else DIST_DIR / "Screenshooter.exe"
    )

    print(f"\nГотово: {exe_path}")
    print(f"Build: {version}.{build}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка Screenshooter")
    parser.add_argument(
        "--console",
        action="store_true",
        help="собрать с консолью (для отладки)",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="собрать папку вместо одного exe",
    )
    parser.add_argument(
        "--no-increment",
        action="store_true",
        help="не увеличивать BUILD (пересборка того же номера)",
    )
    args = parser.parse_args()

    build_exe(
        console=args.console,
        onedir=args.onedir,
        no_increment=args.no_increment,
    )


if __name__ == "__main__":
    main()
