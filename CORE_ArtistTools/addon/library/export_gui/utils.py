# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import os

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from .theme import FONT_FAMILY, THEME

_orbitron_registered_family: str | None = None
# True when ``Orbitron-SemiBold.ttf`` is loaded — outlines are already semibold; avoid synthetic bold.
_orbitron_header_intrinsic_semibold: bool = False


def _resolve_bundled_orbitron_font_path() -> tuple[str | None, bool]:
    """Pick a bundled Orbitron file under ``export_gui/fonts/``.

    Returns ``(path, intrinsic_semibold)``. Prefer the Google Fonts zip layout
    (``fonts/Orbitron/``) and static SemiBold so Qt matches desktop design tools.
    """
    fonts_root = os.path.join(os.path.dirname(__file__), "fonts")
    semibold = os.path.join(fonts_root, "Orbitron", "static", "Orbitron-SemiBold.ttf")
    if os.path.isfile(semibold):
        return semibold, True
    variable_official = os.path.join(fonts_root, "Orbitron", "Orbitron-VariableFont_wght.ttf")
    if os.path.isfile(variable_official):
        return variable_official, False
    legacy = os.path.join(fonts_root, "Orbitron-Variable.ttf")
    if os.path.isfile(legacy):
        return legacy, False
    return None, False


def orbitron_font_family_for_ui() -> str:
    """Register bundled Orbitron (``fonts/Orbitron/``, see ``Orbitron/OFL.txt``) for Qt.

    Falls back to the primary face from :data:`FONT_FAMILY` if no file is found
    or registration fails (e.g. before ``QGuiApplication`` exists).
    """
    global _orbitron_registered_family, _orbitron_header_intrinsic_semibold
    if _orbitron_registered_family is not None:
        return _orbitron_registered_family

    from PySide6.QtGui import QFontDatabase

    font_path, intrinsic_semibold = _resolve_bundled_orbitron_font_path()
    if font_path is not None:
        fid = QFontDatabase.addApplicationFont(font_path)
        if fid >= 0:
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                _orbitron_header_intrinsic_semibold = intrinsic_semibold
                _orbitron_registered_family = families[0]
                return _orbitron_registered_family

    _orbitron_header_intrinsic_semibold = False
    primary = FONT_FAMILY.split(",")[0].strip().strip("\"'")
    _orbitron_registered_family = primary
    return _orbitron_registered_family


def orbitron_header_title_qfont() -> QFont:
    """QFont for the Autochecker dialog header: 26px Orbitron SemiBold when bundled.

    Note: On widgets that use Qt Style Sheets, any ``font-*`` rule in the sheet
    overrides :meth:`QWidget.setFont`; use :func:`orbitron_header_title_stylesheet_font_block`
    for those (e.g. ``QLabel#HeaderTitle``).
    """
    family = orbitron_font_family_for_ui()
    font = QFont(family)
    font.setPixelSize(26)
    if _orbitron_header_intrinsic_semibold:
        font.setWeight(QFont.Weight.Normal)
    else:
        font.setWeight(QFont.Weight.DemiBold)
    return font


def orbitron_header_title_stylesheet_font_block() -> str:
    """``font-family`` / size / weight for ``QLabel#HeaderTitle`` (stylesheet-safe).

    Stylesheet fonts win over :func:`orbitron_header_title_qfont` on the same widget.
    """
    family = orbitron_font_family_for_ui()
    esc = family.replace("\\", "\\\\").replace("'", "\\'")
    weight = "normal" if _orbitron_header_intrinsic_semibold else "600"
    return f"font-family: '{esc}'; font-size: 26px; font-weight: {weight};"


def svg_config_qicon(
    svg_basename: str,
    fill_color: str,
    size: int = 16,
) -> QIcon:
    """Rasterize ``export_gui/icons/{svg_basename}`` for :meth:`QAbstractButton.setIcon`."""
    path = os.path.join(os.path.dirname(__file__), "icons", svg_basename)
    try:
        from PySide6.QtSvg import QSvgRenderer

        with open(path, encoding="utf-8") as f:
            raw = f.read()
        svg_data = raw.replace("{{FILL}}", fill_color).replace("currentColor", fill_color)
        renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
        if not renderer.isValid():
            raise ValueError(f"invalid svg: {svg_basename}")
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        return QIcon(pix)
    except Exception:
        return QIcon()


def _svg_renderer_to_square_pixmap(renderer, pixel_size: int) -> QPixmap:
    """Paint SVG into a square pixmap without stretching non-square viewBoxes."""
    vb = renderer.viewBoxF()
    if not vb.isValid() or vb.width() <= 0 or vb.height() <= 0:
        ds = renderer.defaultSize()
        w, h = max(1, ds.width()), max(1, ds.height())
        vb = QRectF(0, 0, float(w), float(h))

    scale = min(pixel_size / vb.width(), pixel_size / vb.height())
    tw = vb.width() * scale
    th = vb.height() * scale
    x = (pixel_size - tw) * 0.5
    y = (pixel_size - th) * 0.5

    pix = QPixmap(pixel_size, pixel_size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(x, y, tw, th))
    painter.end()
    return pix


def window_icon_qicon() -> QIcon:
    """Icon for :meth:`QWidget.setWindowIcon` (title bar, taskbar, Alt+Tab).

    Uses ``icons/app_window.ico`` when present (strongest on Windows). Otherwise
    rasterizes ``icons/app_window_icon.svg`` at several sizes so scaling stays sharp.
    """
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    ico_path = os.path.join(icons_dir, "app_window.ico")
    if os.path.isfile(ico_path):
        icon = QIcon(ico_path)
        if not icon.isNull():
            return icon

    svg_path = os.path.join(icons_dir, "app_window_icon.svg")
    icon = QIcon()
    if not os.path.isfile(svg_path):
        return icon
    try:
        from PySide6.QtSvg import QSvgRenderer

        with open(svg_path, encoding="utf-8") as f:
            svg_data = f.read().replace("{{ACCENT}}", THEME["accent"])
        ba = QByteArray(svg_data.encode("utf-8"))
        renderer = QSvgRenderer(ba)
        if not renderer.isValid():
            return icon
        for size in (16, 24, 32, 48, 64):
            pix = _svg_renderer_to_square_pixmap(renderer, size)
            icon.addPixmap(pix, QIcon.Mode.Normal, QIcon.State.Off)
    except Exception:
        pass
    return icon


def svg_config_icon_label(
    svg_basename: str,
    fill_color: str,
    size: int = 16,
    *,
    fallback_text: str | None = None,
) -> QLabel:
    """Load a small SVG from ``export_gui/icons/`` and display it in a QLabel.

    SVG files may use ``{{FILL}}`` as a placeholder for the icon color. If QtSvg
    is unavailable or the asset fails to load, ``fallback_text`` is shown with
    the same tint (Unicode / text stub).
    """
    label = QLabel()
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    path = os.path.join(os.path.dirname(__file__), "icons", svg_basename)
    try:
        from PySide6.QtSvg import QSvgRenderer

        with open(path, encoding="utf-8") as f:
            svg_data = f.read().replace("{{FILL}}", fill_color)
        renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
        if not renderer.isValid():
            raise ValueError(f"invalid svg: {svg_basename}")
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        label.setPixmap(pix)
    except Exception:
        if fallback_text:
            label.setText(fallback_text)
            label.setStyleSheet(f"color: {fill_color}; font-size: 14px;")
    return label


def message_box(title="Task Complete", message="Your operation finished successfully.", details=None):
    msg = QMessageBox()
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setStyleSheet(f"""
        QMessageBox {{
            background-color: {THEME['bg_mid']};
            color: {THEME['text_primary']};
            font-family: {FONT_FAMILY};
        }}
        QLabel {{
            color: {THEME['text_primary']};
        }}
        QPushButton {{
            background-color: transparent;
            color: {THEME['text_primary']};
            border: 2px solid {THEME['border_strong']};
            border-radius: 4px;
            padding: 6px 16px;
            font-size: 12px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton:hover {{
            border-color: {THEME['accent']};
            color: {THEME['accent']};
        }}
        QPushButton:disabled {{
            background-color: {THEME['bg_mid']};
            color: {THEME['text_dim']};
            border-color: {THEME['border']};
        }}
    """)

    # Show captured stdout/log output in the expandable Details section
    if details and details.strip():
        msg.setDetailedText(details)

    copy_button = None
    copy_folder_button = None

    # Add Copy Path and Copy Folder buttons if message contains a file path
    if "File saved to:" in message:
        file_path = message.split("File saved to:")[1].strip()

        copy_button = msg.addButton("Copy File Path", QMessageBox.NoRole)
        copy_button.clicked.disconnect()
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(file_path))

        copy_folder_button = msg.addButton("Copy Folder", QMessageBox.NoRole)
        copy_folder_button.clicked.disconnect()
        copy_folder_button.clicked.connect(lambda: QApplication.clipboard().setText(os.path.dirname(file_path)))

    msg.setStandardButtons(QMessageBox.Ok)

    # Fix: QMessageBox ignores the X / Escape key when there is no RejectRole button.
    # Explicitly nominate Ok as the escape button so X always closes the dialog.
    ok_button = msg.button(QMessageBox.Ok)
    if ok_button:
        msg.setEscapeButton(ok_button)

    msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)

    def on_button_clicked(button):
        if button == copy_button or button == copy_folder_button:
            return
        msg.accept()

    msg.buttonClicked.connect(on_button_clicked)
    msg.exec()


def determine_asset_type(filepath):
    filepath_lower = filepath.lower()

    # TODO: come up with a better way to determine the asset type...
    # TODO: Write a new tool that'll append type of asset it is at the top of the file...
    if "props" in filepath_lower or "general" in filepath_lower or "agility3" in filepath_lower:
        return "prop"
    elif "vehicles" in filepath_lower:
        return "vehicle"
    else:
        return "none"
