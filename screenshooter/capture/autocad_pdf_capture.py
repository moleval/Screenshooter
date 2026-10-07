"""
Экспериментальный захват области AutoCAD через фоновый PDF-plot.

экранная область -> координаты текущего вида AutoCAD
-> DWG To PDF.pc3 / monochrome.ctb -> временный PDF
-> рендер PDF в QImage с высоким DPI.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
import winreg

import pythoncom
import win32com.client
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
    right = screen_rect.right()
    bottom = screen_rect.bottom()

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

    scale = min(
        printable_width / window_width,
        printable_height / window_height,
    )
    if scale <= 0:
        raise RuntimeError("Не удалось вычислить масштаб PDF.")

    # GetCustomScale использует единицы бумаги; для DWG To PDF это обычно мм.
    if int(getattr(layout, "PaperUnits", AC_MILLIMETERS)) == 0:
        scale /= 25.4

    layout.UseStandardScale = False
    layout.SetCustomScale(scale, 1.0)
    layout.PlotRotation = (
        AC_0_DEGREES
        if abs(upper_right[0] - lower_left[0])
        >= abs(upper_right[1] - lower_left[1])
        else AC_90_DEGREES
    )
    layout.PlotWithPlotStyles = True
    layout.PlotWithLineweights = False
    layout.ScaleLineweights = False

    try:
        for style in layout.GetPlotStyleTableNames():
            if str(style).lower() == "monochrome.ctb":
                layout.StyleSheet = style
                break
    except Exception:
        pass

    layout.RefreshPlotDeviceInfo()


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


def _enhance_pdf_cad_image(image):
    """Усиливает слабые линии на белом фоне, не инвертируя фон."""
    if image.isNull():
        return image

    import numpy as np

    rgb = image.convertToFormat(QImage.Format_RGB888)
    width = rgb.width()
    height = rgb.height()
    ptr = rgb.bits()
    ptr.setsize(rgb.bytesPerLine() * height)
    array = np.frombuffer(ptr, dtype=np.uint8).reshape(
        height, rgb.bytesPerLine()
    )[:, :width * 3].reshape(height, width, 3)

    corner = np.concatenate((
        array[: max(1, height // 20), : max(1, width // 20)].reshape(-1, 3),
        array[: max(1, height // 20), -max(1, width // 20):].reshape(-1, 3),
        array[-max(1, height // 20):, : max(1, width // 20)].reshape(-1, 3),
        array[-max(1, height // 20):, -max(1, width // 20):].reshape(-1, 3),
    ))
    if float(corner.mean()) < 245.0:
        return rgb.copy()

    strengthened = 255.0 - (255.0 - array.astype(np.float32)) * 4.0
    strengthened = np.clip(strengthened, 0, 255).astype(np.uint8)
    result = QImage(
        strengthened.data,
        width,
        height,
        width * 3,
        QImage.Format_RGB888,
    ).copy()
    return result


def _trim_white_pdf_margins(image, threshold=250):
    if image.isNull():
        return image

    import numpy as np

    rgb = image.convertToFormat(QImage.Format_RGB888)
    width = rgb.width()
    height = rgb.height()
    ptr = rgb.bits()
    ptr.setsize(rgb.bytesPerLine() * height)

    array = np.frombuffer(ptr, dtype=np.uint8).reshape(
        height, rgb.bytesPerLine()
    )[:, :width * 3].reshape(height, width, 3)

    dark = np.any(array < threshold, axis=2)
    if not dark.any():
        return image

    ys, xs = np.where(dark)
    rect = QRect(
        int(xs.min()),
        int(ys.min()),
        int(xs.max() - xs.min() + 1),
        int(ys.max() - ys.min() + 1),
    )

    margin = max(2, min(12, int(min(width, height) * 0.003)))
    rect = rect.adjusted(-margin, -margin, margin, margin)
    rect = rect.intersected(QRect(0, 0, width, height))
    return rgb.copy(rect)


def _render_pdf_to_qimage(pdf_path, dpi):
    try:
        import pymupdf
    except ImportError as error:
        raise RuntimeError(
            "Для PDF-прототипа нужен PyMuPDF: pip install PyMuPDF"
        ) from error

    pdf = pymupdf.open(pdf_path)
    try:
        if pdf.page_count < 1:
            raise RuntimeError("AutoCAD создал пустой PDF.")

        page = pdf.load_page(0)
        zoom = float(dpi) / 72.0
        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(zoom, zoom),
            colorspace=pymupdf.csRGB,
            alpha=False,
        )

        image = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format_RGB888,
        ).copy()
        return _enhance_pdf_cad_image(image), (
            float(page.rect.width),
            float(page.rect.height),
        )
    finally:
        pdf.close()


def _crop_rendered_pdf_to_plot(image, page_mm, layout, lower_left, upper_right):
    """Обрезает PDF ровно до AutoCAD-окна, а не до содержимого чертежа."""
    paper_width, paper_height = page_mm
    try:
        origin = _variant_point(layout.PlotOrigin)
        rotation = int(layout.PlotRotation)
    except Exception:
        return image

    scale = None
    try:
        numerator, denominator = layout.GetCustomScale()
        if denominator:
            scale = float(numerator) / float(denominator)
        if int(getattr(layout, "PaperUnits", AC_MILLIMETERS)) == 0:
            scale *= 25.4
    except Exception:
        pass

    if scale is None or scale <= 0:
        return image

    drawing_width = abs(upper_right[0] - lower_left[0])
    drawing_height = abs(upper_right[1] - lower_left[1])
    plot_width = drawing_width * scale
    plot_height = drawing_height * scale

    if rotation in (AC_90_DEGREES, 3):
        plot_width, plot_height = plot_height, plot_width

    if paper_width <= 0 or paper_height <= 0:
        return image

    x1 = origin[0]
    y1 = paper_height - (origin[1] + plot_height)
    x2 = x1 + plot_width
    y2 = y1 + plot_height

    width = image.width()
    height = image.height()
    left = max(0, min(width - 1, round(x1 / paper_width * width)))
    top = max(0, min(height - 1, round(y1 / paper_height * height)))
    right = max(left + 1, min(width, round(x2 / paper_width * width)))
    bottom = max(top + 1, min(height, round(y2 / paper_height * height)))

    return image.copy(left, top, right - left, bottom - top)


def capture_autocad_region_via_pdf(hwnd, screen_rect, *, dpi=600, timeout=30.0):
    """
    Возвращает QImage из AutoCAD -> PDF -> raster.
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
        image, page_mm = _render_pdf_to_qimage(pdf_path, dpi)
        image = _crop_rendered_pdf_to_plot(
            image, page_mm, layout, lower_left, upper_right
        )
        _diagnostic(f"rendered at {dpi} DPI: {image.width()}x{image.height()}")
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

        try:
            if os.path.isfile(pdf_path):
                os.remove(pdf_path)
            os.rmdir(temp_dir)
        except OSError:
            pass
