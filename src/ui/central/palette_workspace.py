from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Signal, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.color_utils import normalize_hex_color
from ui.theme import (
    ACCENT,
    BG_CARD,
    BG_HOVER,
    BORDER,
    ICON_BUTTON_STYLE,
    SMALL_BUTTON_STYLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.icons import line_icon


BASIC_COLOR_COLUMNS = [
    "#000000", "#dc2626", "#f97316", "#facc15",
    "#16a34a", "#0d9488", "#2563eb", "#7c3aed",
]


def _blend_hex(color: str, target: str, ratio: float) -> str:
    src = QColor(color)
    dst = QColor(target)
    r = round(src.red() + (dst.red() - src.red()) * ratio)
    g = round(src.green() + (dst.green() - src.green()) * ratio)
    b = round(src.blue() + (dst.blue() - src.blue()) * ratio)
    return QColor(r, g, b).name()


BASIC_COLORS = [
    _blend_hex(color, "#ffffff", ratio)
    for ratio in (0.0, 0.16, 0.30, 0.44, 0.58, 0.72, 0.84)
    for color in BASIC_COLOR_COLUMNS
]

DEFAULT_CUSTOM_COLORS = [
    "#2563eb", "#db2777", "#0891b2", "#16a34a", "#f59e0b", "#7c3aed",
    "#dc2626", "#0f766e", "#6366f1", "#ea580c", "#0d9488", "#a21caf",
    "#111827", "#475569", "#94a3b8", "#e5e7eb", "#7f1d1d", "#1e3a8a",
    "#064e3b", "#713f12", "#581c87", "#831843", "#fef3c7", "#dcfce7",
]


class ScreenColorPickerOverlay(QWidget):
    color_picked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self._preview_color = QColor("#000000")
        self._preview_pos = QPoint(24, 24)
        geometry = QRect()
        for screen in QGuiApplication.screens():
            geometry = geometry.united(screen.geometry())
        self.setGeometry(geometry)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(15, 23, 42, 55))
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "点击屏幕任意位置取色 · Esc 取消",
        )
        box = QRect(self._preview_pos + QPoint(18, 18), self._preview_pos + QPoint(230, 92))
        if box.right() > self.width():
            box.moveRight(self._preview_pos.x() - 18)
        if box.bottom() > self.height():
            box.moveBottom(self._preview_pos.y() - 18)
        painter.setPen(QPen(QColor("#e2e8f0")))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(box, 8, 8)
        swatch = QRect(box.left() + 12, box.top() + 12, 48, 48)
        painter.setBrush(self._preview_color)
        painter.drawRoundedRect(swatch, 6, 6)
        painter.setPen(QPen(QColor("#0f172a")))
        painter.drawText(box.left() + 72, box.top() + 28, self._preview_color.name().upper())
        painter.setPen(QPen(QColor("#475569")))
        painter.drawText(
            box.left() + 72,
            box.top() + 52,
            f"RGB {self._preview_color.red()}, {self._preview_color.green()}, {self._preview_color.blue()}",
        )
        painter.end()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            self.close()
            return
        pos = event.globalPosition().toPoint()
        color = self._sample_color(pos)
        if color.isValid():
            self.color_picked.emit(color.name())
        self.close()

    def mouseMoveEvent(self, event) -> None:
        self._preview_pos = event.position().toPoint()
        color = self._sample_color(event.globalPosition().toPoint())
        if color.isValid():
            self._preview_color = color
        self.update()

    def _sample_color(self, pos: QPoint) -> QColor:
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        if screen is None:
            return QColor()
        local = pos - screen.geometry().topLeft()
        pixmap = screen.grabWindow(0, local.x(), local.y(), 1, 1)
        if not pixmap.isNull():
            color = pixmap.toImage().pixelColor(0, 0)
            if color.isValid():
                return color
        return QColor()


class ColorPalette(QWidget):
    color_changed = Signal(int, int)  # hue, saturation

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 221
        self._sat = 215
        self._value = 235
        self._image: QImage | None = None
        self.setFixedHeight(190)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_hsv(self, hue: int, sat: int, value: int) -> None:
        hue = max(0, min(359, int(hue)))
        sat = max(0, min(255, int(sat)))
        value = max(0, min(255, int(value)))
        self._hue, self._sat, self._value = hue, sat, value
        self.update()

    def resizeEvent(self, _event) -> None:
        self._image = None

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        rect = self.rect()
        if self._image is None or self._image.size() != rect.size():
            self._image = QImage(rect.size(), QImage.Format.Format_RGB32)
            w = max(1, rect.width() - 1)
            h = max(1, rect.height() - 1)
            for y in range(rect.height()):
                sat = int(255 * (1 - y / h))
                for x in range(rect.width()):
                    hue = int(359 * x / w)
                    self._image.setPixelColor(x, y, QColor.fromHsv(hue, sat, 255))
        painter.drawImage(rect.topLeft(), self._image)
        x = int(self._hue / 359 * max(1, rect.width() - 1))
        y = int((1 - self._sat / 255) * max(1, rect.height() - 1))
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawEllipse(QPoint(x, y), 7, 7)
        painter.setPen(QPen(QColor("#0f172a"), 1))
        painter.drawEllipse(QPoint(x, y), 8, 8)
        painter.end()

    def mousePressEvent(self, event) -> None:
        self._pick(event.position().toPoint())

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position().toPoint())

    def _pick(self, point: QPoint) -> None:
        rect = self.rect()
        x = max(0, min(point.x(), rect.width() - 1))
        y = max(0, min(point.y(), rect.height() - 1))
        hue = int(359 * x / max(1, rect.width() - 1))
        sat = int(255 * (1 - y / max(1, rect.height() - 1)))
        self._hue, self._sat = hue, sat
        self.update()
        self.color_changed.emit(hue, sat)


class ValueSlider(QWidget):
    value_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 235
        self._hue = 221
        self._sat = 215
        self.setFixedWidth(28)
        self.setCursor(Qt.CursorShape.SizeVerCursor)

    def set_hsv(self, hue: int, sat: int, value: int) -> None:
        self._hue = max(0, min(359, int(hue)))
        self._sat = max(0, min(255, int(sat)))
        self._value = max(0, min(255, int(value)))
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        rect = self.rect().adjusted(7, 0, -7, 0)
        h = max(1, rect.height() - 1)
        for y in range(rect.height()):
            value = int(255 * (1 - y / h))
            painter.setPen(QColor.fromHsv(self._hue, self._sat, value))
            painter.drawLine(rect.left(), rect.top() + y, rect.right(), rect.top() + y)
        y = rect.top() + int((1 - self._value / 255) * h)
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawLine(3, y, self.width() - 3, y)
        painter.setPen(QPen(QColor("#0f172a"), 1))
        painter.drawLine(3, y + 2, self.width() - 3, y + 2)
        painter.end()

    def mousePressEvent(self, event) -> None:
        self._pick(event.position().toPoint())

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position().toPoint())

    def _pick(self, point: QPoint) -> None:
        h = max(1, self.height() - 1)
        y = max(0, min(point.y(), self.height() - 1))
        self._value = int(255 * (1 - y / h))
        self.update()
        self.value_changed.emit(self._value)


class PaletteWorkspace(QWidget):
    swatch_clicked = Signal(int, str)  # index, new_hex
    color_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD};")
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)

        self._selected_index = 0
        self._colors: list[str] = []
        self._custom_colors = list(DEFAULT_CUSTOM_COLORS)
        self._selected_custom_index = 0
        self._syncing = False
        self._preserve_palette_on_next_scheme = False
        self._picker_overlay: ScreenColorPickerOverlay | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("配色方案编辑")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        self.scheme_label = QLabel("方案")
        self.scheme_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        header.addWidget(self.scheme_label)
        root.addLayout(header)

        root.addWidget(self._build_current_strip())

        middle = QHBoxLayout()
        middle.setSpacing(12)
        middle.addWidget(self._build_palette_card(), stretch=1)
        middle.addWidget(self._build_basic_colors_card(), stretch=1)
        root.addLayout(middle)

        root.addWidget(self._build_controls_card())
        root.addWidget(self._build_custom_colors_card())
        root.addStretch()

    def _card(self, object_name: str) -> QWidget:
        card = QWidget()
        card.setObjectName(object_name)
        card.setStyleSheet(
            f"QWidget#{object_name} {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}"
        )
        return card

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {TEXT_PRIMARY};")
        return label

    def _section_header(self, text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._section_label(text))
        return row

    def _build_current_strip(self) -> QWidget:
        strip = QWidget()
        strip.setObjectName("CurrentColorStrip")
        strip.setStyleSheet("QWidget#CurrentColorStrip { background: transparent; border: none; }")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.preview = QWidget()
        self.preview.setObjectName("CurrentColorPreview")
        self.preview.setFixedSize(34, 24)
        layout.addWidget(self.preview)
        self.selected_label = QLabel("颜色 1")
        self.selected_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(self.selected_label)
        layout.addStretch()
        return strip

    def _build_basic_colors_card(self) -> QWidget:
        card = self._card("BasicColorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        row = self._section_header("基础颜色")
        row.addStretch()
        layout.addLayout(row)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for i, color in enumerate(BASIC_COLORS):
            grid.addWidget(self._color_button(color), i // 8, i % 8)
        layout.addLayout(grid)
        return card

    def _build_palette_card(self) -> QWidget:
        card = self._card("PaletteCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        row = self._section_header("色板")
        row.addStretch()
        btn_pick = QToolButton()
        btn_pick.setIcon(line_icon("eyedropper", color=TEXT_SECONDARY, size=16))
        btn_pick.setText("取色")
        btn_pick.setToolTip("屏幕取色")
        btn_pick.setStatusTip("屏幕取色")
        btn_pick.setAccessibleName("屏幕取色")
        btn_pick.setToolTipDuration(5000)
        btn_pick.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn_pick.setStyleSheet(ICON_BUTTON_STYLE)
        btn_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pick.clicked.connect(self._pick_screen_color)
        row.addWidget(btn_pick)
        layout.addLayout(row)
        self.color_palette = ColorPalette()
        self.color_palette.color_changed.connect(self._on_palette_changed)
        palette_row = QHBoxLayout()
        palette_row.setSpacing(8)
        palette_row.addWidget(self.color_palette, stretch=1)
        self.value_slider = ValueSlider()
        self.value_slider.value_changed.connect(self._on_value_slider_changed)
        palette_row.addWidget(self.value_slider)
        layout.addLayout(palette_row)
        return card

    def _build_controls_card(self) -> QWidget:
        card = self._card("ControlsCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(16)

        rgb = QVBoxLayout()
        rgb.addWidget(self._section_label("RGB"))
        self.r_slider, self.r_spin = self._add_slider_row(rgb, "R", 0, 255)
        self.g_slider, self.g_spin = self._add_slider_row(rgb, "G", 0, 255)
        self.b_slider, self.b_spin = self._add_slider_row(rgb, "B", 0, 255)
        rgb.addStretch()

        hsv = QVBoxLayout()
        hsv.addWidget(self._section_label("HSV"))
        self.h_slider, self.h_spin = self._add_slider_row(hsv, "H", 0, 359)
        self.s_slider, self.s_spin = self._add_slider_row(hsv, "S", 0, 255)
        self.v_slider, self.v_spin = self._add_slider_row(hsv, "V", 0, 255)
        hsv.addStretch()

        layout.addLayout(rgb, stretch=1)
        layout.addLayout(hsv, stretch=1)
        return card

    def _build_custom_colors_card(self) -> QWidget:
        card = self._card("CustomColorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(self._section_label("自定义颜色"))
        top.addStretch()
        btn_save = QPushButton("保存当前到选中")
        btn_save.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._save_current_to_custom)
        btn_add = QPushButton("添加当前")
        btn_add.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._add_current_to_custom)
        top.addWidget(btn_save)
        top.addWidget(btn_add)
        layout.addLayout(top)
        self.custom_grid = QGridLayout()
        self.custom_grid.setHorizontalSpacing(8)
        self.custom_grid.setVerticalSpacing(8)
        layout.addLayout(self.custom_grid)
        self._refresh_custom_colors()
        return card

    def _add_slider_row(self, parent: QVBoxLayout, label_text: str, minimum: int, maximum: int):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(18)
        label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setFixedWidth(84)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        slider.valueChanged.connect(self._on_controls_changed)
        row.addWidget(label)
        row.addWidget(slider, stretch=1)
        row.addWidget(spin)
        parent.addLayout(row)
        return slider, spin

    def _color_button(self, color: str, *, custom_index: int | None = None) -> QPushButton:
        button = QPushButton()
        button.setFixedSize(30, 24)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 1px solid {BORDER}; border-radius: 5px; }}"
            f"QPushButton:hover {{ border: 2px solid {ACCENT}; }}"
        )
        if custom_index is None:
            button.clicked.connect(lambda _checked=False, c=color: self._apply_selected_color(c))
        else:
            button.clicked.connect(lambda _checked=False, i=custom_index: self._select_custom_color(i))
        return button

    def set_scheme(self, name: str, colors: list[str], segment_names: list[str]) -> None:
        self.scheme_label.setText(f"方案: {name}  ({len(colors)} 色)")
        self._colors = [normalize_hex_color(c) for c in colors]
        self._selected_index = min(self._selected_index, max(len(self._colors) - 1, 0))
        preserve_palette = self._preserve_palette_on_next_scheme
        self._preserve_palette_on_next_scheme = False
        self._refresh_selected_editor(sync_palette=not preserve_palette, preserve_hs=preserve_palette)

    def set_selected_index(self, index: int) -> None:
        if 0 <= index < len(self._colors):
            self._selected_index = int(index)
            self._refresh_selected_editor(sync_palette=False)

    def _refresh_selected_editor(self, *, sync_palette: bool = True, preserve_hs: bool = False) -> None:
        if not self._colors:
            self.selected_label.setText("无颜色")
            return
        self._set_editor_color(
            self._colors[self._selected_index],
            sync_palette=sync_palette,
            preserve_hs=preserve_hs,
        )

    def _set_editor_color(self, color_text: str, *, sync_palette: bool = True, preserve_hs: bool = False) -> None:
        color = QColor(normalize_hex_color(color_text))
        hue = self.h_slider.value() if preserve_hs else max(0, color.hue())
        saturation = self.s_slider.value() if preserve_hs else color.saturation()
        self._syncing = True
        try:
            self.selected_label.setText(f"颜色 {self._selected_index + 1}")
            self.preview.setStyleSheet(
                f"QWidget#CurrentColorPreview {{ background: {color.name()}; border: 1px solid {BORDER}; border-radius: 9px; }}"
            )
            for slider, value in (
                (self.r_slider, color.red()),
                (self.g_slider, color.green()),
                (self.b_slider, color.blue()),
                (self.h_slider, hue),
                (self.s_slider, saturation),
                (self.v_slider, color.value()),
            ):
                slider.setValue(value)
            if sync_palette:
                self.color_palette.set_hsv(hue, saturation, color.value())
                self.value_slider.set_hsv(hue, saturation, color.value())
            else:
                self.value_slider.set_hsv(hue, saturation, color.value())
        finally:
            self._syncing = False

    def _on_controls_changed(self) -> None:
        if self._syncing or not self._colors:
            return
        sender = self.sender()
        if sender in {self.r_slider, self.g_slider, self.b_slider}:
            color = QColor(self.r_slider.value(), self.g_slider.value(), self.b_slider.value())
        else:
            color = QColor.fromHsv(self.h_slider.value(), self.s_slider.value(), self.v_slider.value())
        self._apply_selected_color(color.name(), sync_palette=sender in {self.h_slider, self.s_slider, self.v_slider})

    def _on_palette_changed(self, hue: int, saturation: int) -> None:
        if self._syncing or not self._colors:
            return
        self._syncing = True
        try:
            self.h_slider.setValue(hue)
            self.s_slider.setValue(saturation)
        finally:
            self._syncing = False
        color = QColor.fromHsv(hue, saturation, self.v_slider.value())
        self._apply_selected_color(color.name(), sync_palette=False, preserve_hs=True)

    def _on_value_slider_changed(self, value: int) -> None:
        if self._syncing or not self._colors:
            return
        color = QColor.fromHsv(self.h_slider.value(), self.s_slider.value(), value)
        self._apply_selected_color(color.name(), sync_palette=False, preserve_hs=True)

    def _pick_screen_color(self) -> None:
        self._picker_overlay = ScreenColorPickerOverlay(self)
        self._picker_overlay.color_picked.connect(self._apply_selected_color)
        self._picker_overlay.showFullScreen()

    def _apply_selected_color(self, color_text: str, *, sync_palette: bool = True, preserve_hs: bool = False) -> None:
        if not self._colors:
            return
        color = normalize_hex_color(color_text)
        self._colors[self._selected_index] = color
        self._set_editor_color(color, sync_palette=sync_palette, preserve_hs=preserve_hs)
        if preserve_hs and not sync_palette:
            self._preserve_palette_on_next_scheme = True
        self.swatch_clicked.emit(self._selected_index, color)

    def _select_custom_color(self, index: int) -> None:
        if 0 <= index < len(self._custom_colors):
            self._selected_custom_index = index
            self._apply_selected_color(self._custom_colors[index])
            self._refresh_custom_colors()

    def _save_current_to_custom(self) -> None:
        if not self._colors:
            return
        self._custom_colors[self._selected_custom_index] = self._colors[self._selected_index]
        self._refresh_custom_colors()

    def _add_current_to_custom(self) -> None:
        if not self._colors:
            return
        self._custom_colors.append(self._colors[self._selected_index])
        self._selected_custom_index = len(self._custom_colors) - 1
        self._refresh_custom_colors()

    def _refresh_custom_colors(self) -> None:
        while self.custom_grid.count():
            item = self.custom_grid.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for i, color in enumerate(self._custom_colors):
            button = self._color_button(color, custom_index=i)
            if i == self._selected_custom_index:
                button.setStyleSheet(
                    f"QPushButton {{ background: {color}; border: 2px solid {ACCENT}; border-radius: 5px; }}"
                )
            self.custom_grid.addWidget(button, i // 13, i % 13)
