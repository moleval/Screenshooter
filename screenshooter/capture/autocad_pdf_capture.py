"""
Экспериментальный захват области AutoCAD через фоновый PDF-plot.

экранная область -> координаты текущего вида AutoCAD
-> DWG To PDF.pc3 / monochrome.ctb -> PDF
-> открыть PDF во внешнем viewer -> screenshot экрана -> QImage.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
import winreg

import mss
from PIL import Image

import pythoncom
import win32com.client
import win32api
import win32con
import win32gui
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QImage


AC_WORLD = 0
AC_UCS = 1
AC_WINDOW = 4
AC_SCALE_TO_FIT = 0
AC_0_DEGREES = 0
AC_90_DEGREES = 1
AC_MILLIMETERS = 1


def _diagnostic(message):
    print(f"[AUTOCAD PDF] {message}", flush=True)


def _variant_point(values):
    value = getattr(values, "value", values)
    return tuple(float(item) for item in value[:3])


def _as_com_point(point):
    """Создаёт Variant с SAFEARRAY из трёх double для AutoCAD ActiveX."""
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        tuple(float(value) for value in point[:3]),
    )


def _as_com_xy(point):
    """Создаёт Variant с SAFEARRAY из двух double для окна печати."""
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        tuple(float(value) for value in point[:2]),
    )


def _get_autocad_progid_candidates():
    """Возвращает общий и зарегистрированные версионные ProgID AutoCAD."""
    candidates = ["AutoCAD.Application"]
    pattern = re.compile(r"^AutoCAD\.Application\.(\d+)$", re.IGNORECASE)

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "") as root:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1

                match = pattern.match(name)
                if match:
                    candidates.append(name)
    except OSError:
        pass

    def version_key(progid):
        match = pattern.match(progid)
        return int(match.group(1)) if match else -1

    return sorted(set(candidates), key=version_key, reverse=True)


def _get_acad_application():
    """Возвращает уже запущенный AutoCAD, не запуская новый экземпляр."""
    candidates = _get_autocad_progid_candidates()
    _diagnostic(f"COM ProgID кандидаты: {', '.join(candidates)}")

    for progid in candidates:
        try:
            application = win32com.client.GetActiveObject(progid)
            _diagnostic(f"COM подключение успешно: {progid}")
            return application
        except Exception as error:
            _diagnostic(
                f"COM недоступен: {progid} "
                f"({type(error).__name__}: {error})"
            )

    return None


def _get_view_state(document):
    center = _variant_point(document.GetVariable("VIEWCTR"))
    view_size = float(document.GetVariable("VIEWSIZE"))
    screen_size = _variant_point(document.GetVariable("SCREENSIZE"))
    view_dir = _variant_point(document.GetVariable("VIEWDIR"))
    view_twist = float(document.GetVariable("VIEWTWIST"))

    if view_size <= 0 or screen_size[0] <= 0 or screen_size[1] <= 0:
        raise RuntimeError("Некорректные параметры текущего вида AutoCAD.")

    return {
        "center": center,
        "view_size": view_size,
        "screen_size": screen_size,
        "view_dir": view_dir,
        "view_twist": view_twist,
    }


def _is_supported_2d_view(view_state):
    direction = view_state["view_dir"]
    twist = view_state["view_twist"]
    return (
        abs(direction[0]) < 1e-6
        and abs(direction[1]) < 1e-6
        and abs(abs(direction[2]) - 1.0) < 1e-6
        and abs(twist) < 1e-6
    )


def _graphics_rect(hwnd, screen_size):
    """Находит дочернюю область графики AutoCAD по SCREENSIZE."""
    target_w = float(screen_size[0])
    target_h = float(screen_size[1])
    candidates = []

    def visit(child, _):
        try:
            rect = win32gui.GetClientRect(child)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            if width <= 200 or height <= 150:
                return
            origin = win32gui.ClientToScreen(child, (0, 0))
            dw = abs(width - target_w) / max(target_w, 1.0)
            dh = abs(height - target_h) / max(target_h, 1.0)
            score = dw + dh
            if dw <= 0.20 and dh <= 0.20:
                candidates.append((score, origin, width, height, child))
        except Exception:
            pass

    try:
        win32gui.EnumChildWindows(hwnd, visit, None)
    except Exception:
        candidates = []

    if candidates:
        _, origin, width, height, child = min(candidates, key=lambda item: item[0])
        return origin, width, height, child

    client = win32gui.GetClientRect(hwnd)
    origin = win32gui.ClientToScreen(hwnd, (0, 0))
    return origin, client[2] - client[0], client[3] - client[1], hwnd


def _screen_point_to_wcs(document, hwnd, screen_x, screen_y, view_state):
    origin, client_width, client_height, _ = _graphics_rect(
        hwnd, view_state["screen_size"]
    )

    if client_width <= 0 or client_height <= 0:
        raise RuntimeError("Не удалось определить графическую область AutoCAD.")

    rel_x = float(screen_x - origin[0])
    rel_y = float(screen_y - origin[1])

    screen_w = float(view_state["screen_size"][0])
    screen_h = float(view_state["screen_size"][1])
    view_h = float(view_state["view_size"])
    view_w = view_h * screen_w / screen_h
    center = view_state["center"]

    cad_x = rel_x * screen_w / client_width
    cad_y = rel_y * screen_h / client_height

    ucs_x = center[0] + (cad_x / screen_w - 0.5) * view_w
    ucs_y = center[1] + (0.5 - cad_y / screen_h) * view_h
    ucs_point = (ucs_x, ucs_y, center[2])

    return _variant_point(
        document.Utility.TranslateCoordinates(
            _as_com_point(ucs_point),
            AC_UCS,
            AC_WORLD,
            False,
        )
    )


def screen_rect_to_autocad_window(document, hwnd, screen_rect):
    """Переводит QRect экранного выделения в пару WCS-точек AutoCAD."""
    view_state = _get_view_state(document)

    if not _is_supported_2d_view(view_state):
        raise RuntimeError(
            "PDF-прототип поддерживает только 2D вид сверху без VIEWTWIST."
        )

    left = screen_rect.left()
    top = screen_rect.top()
    right = left + screen_rect.width()
    bottom = top + screen_rect.height()

    p1 = _screen_point_to_wcs(document, hwnd, left, bottom, view_state)
    p2 = _screen_point_to_wcs(document, hwnd, right, top, view_state)

    lower_left = (
        min(p1[0], p2[0]),
        min(p1[1], p2[1]),
        min(p1[2], p2[2]),
    )
    upper_right = (
        max(p1[0], p2[0]),
        max(p1[1], p2[1]),
        max(p1[2], p2[2]),
    )

    if (
        abs(upper_right[0] - lower_left[0]) < 1e-9
        or abs(upper_right[1] - lower_left[1]) < 1e-9
    ):
        raise RuntimeError("Выделенная область AutoCAD слишком мала.")

    return lower_left, upper_right


def _get_paper_size(layout):
    result = layout.GetPaperSize()
    if isinstance(result, tuple) and len(result) >= 2:
        return float(result[0]), float(result[1])
    raise RuntimeError("AutoCAD не вернул размер бумаги.")


def _get_paper_margins(layout):
    result = layout.GetPaperMargins()
    if isinstance(result, tuple) and len(result) >= 2:
        return _variant_point(result[0])[:2], _variant_point(result[1])[:2]
    raise RuntimeError("AutoCAD не вернул поля бумаги.")


def _find_pdf_media(layout):
    layout.RefreshPlotDeviceInfo()
    names = layout.GetCanonicalMediaNames()
    normalized = [(str(name).lower(), str(name)) for name in names]

    for token in ("a4", "iso_a4", "ansi_a"):
        for lower, original in normalized:
            if token in lower:
                return original

    if not normalized:
        raise RuntimeError("DWG To PDF.pc3 не предоставил форматы бумаги.")

    return normalized[0][1]


def _snapshot_layout(layout):
    names = (
        "ConfigName",
        "CanonicalMediaName",
        "CenterPlot",
        "PlotRotation",
        "PlotType",
        "PlotWithLineweights",
        "PlotWithPlotStyles",
        "ScaleLineweights",
        "PlotTransparency",
        "StyleSheet",
        "UseStandardScale",
        "StandardScale",
    )
    snapshot = {}
    for name in names:
        try:
            snapshot[name] = getattr(layout, name)
        except Exception:
            pass

    try:
        lower_left, upper_right = layout.GetWindowToPlot()
        snapshot["Window"] = (
            _variant_point(lower_left),
            _variant_point(upper_right),
        )
    except Exception:
        pass

    return snapshot


def _restore_layout(layout, snapshot):
    for name, value in snapshot.items():
        if name == "Window":
            continue
        try:
            setattr(layout, name, value)
        except Exception:
            pass

    window = snapshot.get("Window")
    if window is not None:
        try:
            layout.SetWindowToPlot(_as_com_xy(window[0]), _as_com_xy(window[1]))
        except Exception:
            pass


def _configure_monochrome_pdf(layout, lower_left, upper_right):
    layout.ConfigName = "DWG To PDF.pc3"
    layout.RefreshPlotDeviceInfo()
    layout.CanonicalMediaName = _find_pdf_media(layout)
    layout.SetWindowToPlot(_as_com_xy(lower_left), _as_com_xy(upper_right))
    layout.PlotType = AC_WINDOW
    layout.CenterPlot = True

    paper_width, paper_height = _get_paper_size(layout)
    margin_ll, margin_ur = _get_paper_margins(layout)
    printable_width = paper_width - (margin_ur[0] - margin_ll[0])
    printable_height = paper_height - (margin_ur[1] - margin_ll[1])
    window_width = abs(upper_right[0] - lower_left[0])
    window_height = abs(upper_right[1] - lower_left[1])

    if printable_width <= 0 or printable_height <= 0:
        raise RuntimeError("AutoCAD не вернул рабочую область бумаги.")

    landscape = window_width >= window_height
    layout.PlotRotation = AC_90_DEGREES if landscape else AC_0_DEGREES

    effective_printable_width = printable_width
    effective_printable_height = printable_height
    if landscape:
        effective_printable_width, effective_printable_height = (
            printable_height,
            printable_width,
        )

    scale = min(
        effective_printable_width / window_width,
        effective_printable_height / window_height,
    )
    if scale <= 0:
        raise RuntimeError("Не удалось вычислить масштаб PDF.")

    if int(getattr(layout, "PaperUnits", AC_MILLIMETERS)) == 0:
        scale /= 25.4

    layout.UseStandardScale = False
    layout.SetCustomScale(scale, 1.0)
    layout.PlotWithPlotStyles = True
    layout.PlotWithLineweights = False
    layout.ScaleLineweights = False
    # Прозрачность должна участвовать в печати PDF.
    try:
        layout.PlotTransparency = True
    except Exception:
        pass

    try:
        for style in layout.GetPlotStyleTableNames():
            if str(style).lower() == "monochrome.ctb":
                layout.StyleSheet = style
                break
    except Exception:
        pass

    # RefreshPlotDeviceInfo может сбросить PlotTransparency,
    # поэтому включаем её после последнего обновления устройства печати.
    layout.RefreshPlotDeviceInfo()
    try:
        layout.PlotTransparency = True
        _diagnostic("PlotTransparency=True")
    except Exception as error:
        _diagnostic(f"WARNING: PlotTransparency недоступен: {error}")


def _find_pdf_window(file_name):
    """
    Находит активное окно PDF-XChange после открытия PDF.

    В заголовке верхнего окна имя файла может отсутствовать: PDF-XChange
    способен показывать имя документа только во вкладке. Поэтому сначала
    проверяем активное окно, затем ищем видимые окна PDF-XChange и только
    потом используем точное совпадение имени PDF.
    """
    needle = str(file_name).lower()

    try:
        foreground = win32gui.GetForegroundWindow()
        if foreground and win32gui.IsWindowVisible(foreground):
            title = win32gui.GetWindowText(foreground).lower()
            if (
                "pdf-xchange" in title
                or "pdf xchange" in title
                or needle in title
            ):
                return foreground
    except Exception:
        pass

    candidates = []

    def visit(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            lower = title.lower()
            if "pdf-xchange" in lower or "pdf xchange" in lower:
                candidates.append(hwnd)
            elif needle in lower:
                candidates.append(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(visit, None)
    except Exception:
        pass

    return candidates[0] if candidates else None


def _send_key(vk, modifiers=()):
    """Эмулирует короткое нажатие клавиши через Win32."""
    for modifier in modifiers:
        win32api.keybd_event(modifier, 0, 0, 0)
    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    for modifier in reversed(modifiers):
        win32api.keybd_event(modifier, 0, win32con.KEYEVENTF_KEYUP, 0)


def _capture_pdf_viewport(viewer_hwnd):
    """Снимает один физический экранный кадр PDF-XChange."""
    left, top, right, bottom = win32gui.GetWindowRect(viewer_hwnd)
    width = max(1, int(right - left))
    height = max(1, int(bottom - top))
    if width < 200 or height < 200:
        raise RuntimeError(
            f"слишком маленькое окно PDF-viewer: {width}x{height}"
        )

    with mss.mss() as sct:
        shot = sct.grab({
            "left": int(left),
            "top": int(top),
            "width": width,
            "height": height,
        })

    return Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)


def _pan_pdf_view(viewer_hwnd, dx, dy):
    """
    Сдвигает страницу PDF мышью, используя штатный Hand Tool PDF-XChange.

    PDF-XChange документирует Space как временное включение Hand Tool,
    поэтому здесь не используется программный рендеринг или экспорт.
    """
    left, top, right, bottom = win32gui.GetWindowRect(viewer_hwnd)
    center_x = int((left + right) / 2)
    center_y = int((top + bottom) / 2)

    win32api.SetCursorPos((center_x, center_y))
    win32api.keybd_event(ord(" "), 0, 0, 0)
    try:
        time.sleep(0.05)
        win32api.mouse_event(
            win32con.MOUSEEVENTF_LEFTDOWN,
            0,
            0,
            0,
            0,
        )
        time.sleep(0.05)
        win32api.SetCursorPos((
            center_x - int(dx),
            center_y - int(dy),
        ))
        time.sleep(0.12)
        win32api.mouse_event(
            win32con.MOUSEEVENTF_LEFTUP,
            0,
            0,
            0,
            0,
        )
    finally:
        win32api.keybd_event(
            ord(" "),
            0,
            win32con.KEYEVENTF_KEYUP,
            0,
        )

    time.sleep(0.45)


def _crop_to_pdf_page(image):
    """
    Убирает серое поле PDF-viewer вокруг белой страницы.

    Это не обработка PDF: кадр уже получен с экрана. Мы только удаляем
    окружающее окно просмотра перед сборкой tiled screenshot.
    """
    gray = image.convert("L")
    mask = gray.point(lambda value: 255 if value >= 235 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return image

    left, top, right, bottom = bbox
    if right - left < 400 or bottom - top < 400:
        return image

    return image.crop(bbox)


def _image_to_qimage(image):
    image = image.convert("RGBA")
    raw = image.tobytes("raw", "RGBA")
    qimage = QImage(
        raw,
        image.width,
        image.height,
        image.width * 4,
        QImage.Format_RGBA8888,
    )
    return qimage.copy()


def _capture_open_pdf_window(pdf_path, timeout=15.0):
    """
    Открывает PDF-XChange и получает tiled screenshot страницы.

    PDF-XChange сам растеризует векторную страницу в масштабе 250%.
    Мы снимаем несколько физических экранных кадров соседних участков
    и собираем их без интерполяции в один большой QImage.

    В отличие от PyMuPDF-render это именно screenshot уже открытого PDF.
    """
    file_name = os.path.basename(pdf_path)
    try:
        os.startfile(pdf_path)
    except Exception as error:
        raise RuntimeError(f"не удалось открыть PDF: {error}") from error

    deadline = time.monotonic() + timeout
    viewer_hwnd = None
    while time.monotonic() < deadline:
        viewer_hwnd = _find_pdf_window(file_name)
        if viewer_hwnd:
            break
        time.sleep(0.15)

    if not viewer_hwnd:
        raise RuntimeError(f"не найдено окно PDF-viewer для {file_name}")

    try:
        win32gui.ShowWindow(viewer_hwnd, win32con.SW_MAXIMIZE)
        win32gui.SetForegroundWindow(viewer_hwnd)
    except Exception:
        pass

    time.sleep(0.5)

    # Сначала нормализуем страницу, затем включаем fullscreen.
    _send_key(ord("0"), modifiers=(win32con.VK_CONTROL,))
    time.sleep(0.45)
    _send_key(win32con.VK_F11)
    time.sleep(0.8)

    # В fullscreen убираем панели, чтобы каждый tile состоял только
    # из физического экранного представления страницы.
    _send_key(win32con.VK_F8)
    time.sleep(0.4)

    # PDF-XChange поддерживает Zoom To через Ctrl+Shift+M.
    # Ставим 250%: это заметно повышает исходное число пикселей,
    # но не раздувает количество tiles настолько, как 300%.
    _send_key(ord("M"), modifiers=(win32con.VK_CONTROL, win32con.VK_SHIFT))
    time.sleep(0.35)
    for char in "250":
        _send_key(ord(char))
        time.sleep(0.04)
    _send_key(win32con.VK_RETURN)
    time.sleep(0.9)

    # Физический размер одного tile определяется реальным экраном.
    # Шаги намеренно перекрываются: это безопаснее для тонких CAD-линий
    # и позволяет не терять границы при склейке.
    first = _capture_pdf_viewport(viewer_hwnd)
    tile_width, tile_height = first.size
    horizontal_step = min(900, max(500, tile_width // 2))
    vertical_step = min(600, max(400, tile_height // 2))

    tiles = []
    for row in range(4):
        row_tiles = []
        for col in range(2):
            if row == 0 and col == 0:
                tile = first
            else:
                tile = _capture_pdf_viewport(viewer_hwnd)

            row_tiles.append(tile)

            if col == 0:
                _pan_pdf_view(
                    viewer_hwnd,
                    horizontal_step,
                    0,
                )

        # Вернуться к левой колонке.
        _pan_pdf_view(
            viewer_hwnd,
            -horizontal_step,
            0,
        )

        tiles.append(row_tiles)

        if row < 3:
            _pan_pdf_view(
                viewer_hwnd,
                0,
                vertical_step,
            )

    # Восстанавливаем исходную позицию перед выходом.
    for _ in range(3):
        _pan_pdf_view(
            viewer_hwnd,
            0,
            -vertical_step,
        )

    canvas_width = tile_width + horizontal_step
    canvas_height = tile_height + vertical_step * 3
    canvas = Image.new("RGB", (canvas_width, canvas_height), (128, 128, 128))

    for row, row_tiles in enumerate(tiles):
        for col, tile in enumerate(row_tiles):
            canvas.paste(
                tile,
                (
                    col * horizontal_step,
                    row * vertical_step,
                ),
            )

    # Убираем только внешнее серое поле. Само содержимое — результат
    # экранных screenshots PDF-XChange и не подвергается масштабированию.
    canvas = _crop_to_pdf_page(canvas)

    image = _image_to_qimage(canvas)
    _diagnostic(
        f"PDF viewer tiled screenshot: {image.width()}x{image.height()} "
        f"zoom=250% tiles=2x4 window=0x{int(viewer_hwnd):X}"
    )

    # ВАЖНО: выход из fullscreen выполняется именно F11, не Escape.
    try:
        _send_key(win32con.VK_F11)
        time.sleep(0.45)
        _send_key(ord("W"), modifiers=(win32con.VK_CONTROL,))
        time.sleep(0.35)
        _diagnostic("PDF viewer: F11 fullscreen exited, PDF tab closed")
    except Exception as error:
        _diagnostic(f"WARNING: не удалось закрыть вкладку PDF: {error}")

    return image


def _wait_for_file(path, timeout):
    deadline = time.monotonic() + timeout
    previous_size = -1
    stable_since = None

    while time.monotonic() < deadline:
        if os.path.isfile(path):
            try:
                size = os.path.getsize(path)
            except OSError:
                size = -1

            if size > 0 and size == previous_size:
                if stable_since is None:
                    stable_since = time.monotonic()
                elif time.monotonic() - stable_since >= 0.35:
                    return True
            else:
                previous_size = size
                stable_since = None

        time.sleep(0.08)

    return False


def capture_autocad_region_via_pdf(hwnd, screen_rect, *, dpi=900, timeout=30.0):
    """
    Возвращает QImage из цепочки AutoCAD -> PDF -> PDF-viewer -> screenshot.

    PDF считается эталонным векторным источником: после его создания PDF
    не растеризуется библиотекой. Пиксели получает только экранный screenshot
    уже открытой страницы PDF-XChange.

    При любой невозможности возвращает None для безопасного fallback.
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        _diagnostic("FALLBACK: недействительный hwnd AutoCAD")
        return None
    if screen_rect is None or screen_rect.isNull():
        _diagnostic("FALLBACK: пустое выделение")
        return None

    _diagnostic(
        f"запуск захвата hwnd=0x{int(hwnd):X}, "
        f"rect={screen_rect.x()},{screen_rect.y()},"
        f"{screen_rect.width()}x{screen_rect.height()}"
    )
    acad = _get_acad_application()
    if acad is None:
        _diagnostic("FALLBACK: AutoCAD не найден через COM")
        return None

    temp_dir = tempfile.mkdtemp(prefix="screenshooter_autocad_pdf_")
    pdf_path = os.path.join(temp_dir, "capture.pdf")
    document = None
    layout = None
    snapshot = None
    original_background_plot = None

    try:
        document = acad.ActiveDocument
        _diagnostic("connected")
        lower_left, upper_right = screen_rect_to_autocad_window(
            document, hwnd, screen_rect
        )

        _diagnostic(f"WCS window: {lower_left} -> {upper_right}")

        layout = document.ActiveLayout
        snapshot = _snapshot_layout(layout)

        try:
            original_background_plot = document.GetVariable("BACKGROUNDPLOT")
        except Exception:
            pass

        document.SetVariable("BACKGROUNDPLOT", 0)
        _diagnostic("BACKGROUNDPLOT=0")
        _configure_monochrome_pdf(layout, lower_left, upper_right)
        _diagnostic(
            f"plot device={layout.ConfigName}, "
            f"media={layout.CanonicalMediaName}, "
            f"plot_type={layout.PlotType}"
        )
        document.Regen(0)
        _diagnostic(f"plotting to: {pdf_path}")

        result = document.Plot.PlotToFile(pdf_path)
        _diagnostic(f"PlotToFile returned: {result}")
        if result is False:
            _diagnostic("FALLBACK: PlotToFile вернул False")
            return None

        if not _wait_for_file(pdf_path, timeout):
            _diagnostic("FALLBACK: PDF не появился или не стабилизировался")
            return None

        _diagnostic(f"PDF created: {pdf_path}")
        image = _capture_open_pdf_window(pdf_path, timeout=timeout)
        _diagnostic(
            f"captured from opened PDF viewer: "
            f"{image.width()}x{image.height()}"
        )
        _diagnostic("SUCCESS")
        return image
    except Exception as error:
        _diagnostic(f"FALLBACK: {type(error).__name__}: {error}")
        return None
    finally:
        if document is not None and layout is not None and snapshot is not None:
            try:
                _restore_layout(layout, snapshot)
                document.Regen(0)
            except Exception:
                pass

        if document is not None and original_background_plot is not None:
            try:
                document.SetVariable("BACKGROUNDPLOT", original_background_plot)
            except Exception:
                pass

        # PDF-viewer может удерживать временный файл открытым. Сначала
        # пытаемся удалить PDF, затем каталог; если viewer его держит,
        # оставляем файл до следующего запуска Windows/очистки temp.
        for _ in range(40):
            try:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                if os.path.isdir(temp_dir):
                    os.rmdir(temp_dir)
                _diagnostic("temporary PDF removed")
                break
            except OSError:
                time.sleep(0.1)
        else:
            _diagnostic(f"WARNING: не удалось удалить временный PDF: {pdf_path}")
