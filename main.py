import sys
import os
import json
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve, QRectF, QUrl, QEvent, QPoint
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QCheckBox, 
                             QScrollArea, QFrame, QSystemTrayIcon, QMenu,
                             QGraphicsDropShadowEffect, QInputDialog, QDialog, QSizePolicy)
from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QPainter, QBrush, QPen, QPixmap, QKeySequence, QShortcut, QPainterPath, QRegion
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from qframelesswindow import AcrylicWindow, StandardTitleBar

def get_translucent_background_attribute():
    """Return the correct translucent-background attribute for the active Qt binding."""
    widget_attr_enum = getattr(Qt, "WidgetAttribute", None)
    if widget_attr_enum is not None and hasattr(widget_attr_enum, "WA_TranslucentBackground"):
        return widget_attr_enum.WA_TranslucentBackground
    # Fallback for older bindings/layouts
    return getattr(Qt, "WA_TranslucentBackground", None)

class TaskItem(QFrame):
    deleteRequested = pyqtSignal(object)
    changed = pyqtSignal()
    
    def __init__(self, text, checked=False, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskItem")
        self.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMouseTracking(True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(10)
        
        self.checkbox = QCheckBox()
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.stateChanged.connect(self.on_state_changed)
        
        self.label = QLabel(text)
        self.label.setFont(QFont("Inter", 11))
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.label.setStyleSheet("color: #E0E0E0;")
        
        # Reminder Icon
        self.reminder_btn = QPushButton("🔔")
        self.reminder_btn.setFixedSize(24, 24)
        self.reminder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reminder_btn.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        self.reminder_btn.clicked.connect(self.set_reminder)
        
        # Delete Icon
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setFixedSize(62, 28)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self))
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 70, 70, 0.15);
                border: 1px solid rgba(255, 90, 90, 0.35);
                color: #FFDADA;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 8px;
            }
            QPushButton:hover {
                background: rgba(255, 70, 70, 0.28);
                border: 1px solid rgba(255, 120, 120, 0.5);
            }
        """)
        
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.reminder_btn)
        layout.addWidget(self.delete_btn)
        
        self.setStyleSheet("""
            #TaskItem {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            #TaskItem:hover {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)
        self.checkbox.setChecked(checked)

    def on_state_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            self.label.setStyleSheet("color: rgba(255, 255, 255, 0.3); text-decoration: line-through;")
        else:
            self.label.setStyleSheet("color: #E0E0E0; text-decoration: none;")
        self.changed.emit()

    def set_reminder(self):
        # Simply a mock for now
        self.reminder_btn.setText("⏰")

    def to_dict(self):
        return {
            "text": self.label.text(),
            "checked": self.checkbox.isChecked(),
        }

class PomodoroTimer(AcrylicWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pomodoro Timer")
        self.resize(900, 550)
        
        self.acrylic_enabled = False
        
        # Customizing the title bar for frameless experience
        self.titleBar.hide() 
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        # Enable true edge/corner resizing on frameless window.
        self.setResizeEnabled(True)
        
        translucent_attr = get_translucent_background_attribute()
        if translucent_attr is not None:
            try:
                self.setAttribute(translucent_attr, True)
            except Exception:
                pass
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        except Exception:
            pass
        self.setAutoFillBackground(False)
        
        # Config
        self.is_compact = False
        self.is_clock_mode = False
        self.is_focus_mode = False
        self.focus_restore_pin_state = False
        self.normal_size = (900, 550)
        self.compact_size = (620, 550)
        self.clock_size = (420, 250)
        self.focus_size = (280, 110)
        self.remaining_seconds = 25 * 60
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.drag_pos = None
        self.current_layout_mode = None
        self.focus_drag_start_global = None
        self.focus_drag_window_start = None
        self.resize_margin = 8
        self.resize_edges = None
        self.resize_start_global = None
        self.resize_start_geometry = None
        self._using_override_cursor = False
        self.alarm_clip_duration_ms = 11000
        self.alarm_loop_timer = QTimer(self)
        self.alarm_loop_timer.setSingleShot(True)
        self.alarm_loop_timer.timeout.connect(self.loop_alarm_clip)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)
        self.alarm_player = QMediaPlayer(self)
        self.alarm_player.setAudioOutput(self.audio_output)
        self.alarm_player.errorOccurred.connect(self.on_alarm_error)
        self.alarm_active = False
        
        self.init_ui()
        self.install_resize_event_filters()
        self.load_tasks()
        self.setup_shortcuts()
        self.setup_tray()
        self.set_rounded_corners()
        QTimer.singleShot(0, self.try_enable_blur)

    def set_rounded_corners(self):
        self.update_window_mask()

    def update_window_mask(self):
        radius = 25
        path = QPainterPath()
        adjusted_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path.addRoundedRect(adjusted_rect, radius, radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def try_enable_blur(self):
        try:
            self.windowEffect.setAcrylicEffect(self.winId(), "66101010", True)
            self.acrylic_enabled = True
        except Exception:
            self.acrylic_enabled = False
        self.apply_container_style()

    def init_ui(self):
        # Global Styles
        self.setStyleSheet("""
            QWidget {
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #FFFFFF;
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                color: white;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.25);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.05);
            }
            QLineEdit {
                background: rgba(0, 0, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                color: white;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(255, 255, 255, 0.3);
                background: rgba(0, 0, 0, 0.3);
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: transparent;
            }
        """)

        # Container with 1px border and soft glow effect
        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        self.apply_container_style()
        
        self.window_layout = QHBoxLayout(self)
        # Zero outer margins remove the visible rectangular corner artifacts.
        self.window_layout.setContentsMargins(0, 0, 0, 0)
        self.window_layout.addWidget(self.container)
        
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(14, 12, 14, 14)
        self.container_layout.setSpacing(14)

        # Header / drag bar
        self.header_bar = QFrame()
        self.header_bar.setObjectName("HeaderBar")
        self.header_bar.setFixedHeight(44)
        self.header_bar.setStyleSheet("""
            #HeaderBar {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
            }
        """)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(14, 6, 10, 6)
        header_layout.setSpacing(8)

        self.drag_title = QLabel("Pomodoro Timer")
        self.drag_title.setStyleSheet("color: rgba(255, 255, 255, 0.80); font-size: 12px; font-weight: 600;")

        self.pin_btn = QPushButton("PIN")
        self.pin_btn.setFixedSize(74, 32)
        self.pin_btn.setCheckable(True)
        self.pin_btn.clicked.connect(self.toggle_always_on_top)
        self.pin_btn.setToolTip("Immer im Vordergrund (Ctrl+Shift+P)")

        self.clock_btn = QPushButton("CLOCK")
        self.clock_btn.setFixedSize(92, 32)
        self.clock_btn.setCheckable(True)
        self.clock_btn.clicked.connect(self.toggle_clock_mode)
        self.clock_btn.setToolTip("Nur Uhrzeit anzeigen (Ctrl+Shift+M)")

        self.focus_btn = QPushButton("FOCUS")
        self.focus_btn.setFixedSize(92, 32)
        self.focus_btn.setCheckable(True)
        self.focus_btn.clicked.connect(self.toggle_focus_mode)
        self.focus_btn.setToolTip("Mini-Zeitfenster, immer im Vordergrund (Ctrl+Shift+F)")

        self.compact_btn = QPushButton("SIDE")
        self.compact_btn.setFixedSize(74, 32)
        self.compact_btn.setCheckable(True)
        self.compact_btn.clicked.connect(self.toggle_compact)
        self.compact_btn.setToolTip("To-Do ausblenden (Ctrl+Shift+C)")

        self.minimize_btn = QPushButton("MIN")
        self.minimize_btn.setFixedSize(68, 32)
        self.minimize_btn.clicked.connect(self.minimize_to_tray)
        self.minimize_btn.setToolTip("Minimieren")

        self.close_btn = QPushButton("X")
        self.close_btn.setFixedSize(52, 32)
        self.close_btn.clicked.connect(QApplication.instance().quit)
        self.close_btn.setToolTip("Beenden")

        for header_btn in (self.pin_btn, self.clock_btn, self.focus_btn, self.compact_btn, self.minimize_btn, self.close_btn):
            header_btn.setStyleSheet(self.header_button_style(False))

        header_layout.addWidget(self.drag_title)
        header_layout.addStretch()
        header_layout.addWidget(self.pin_btn)
        header_layout.addWidget(self.clock_btn)
        header_layout.addWidget(self.focus_btn)
        header_layout.addWidget(self.compact_btn)
        header_layout.addWidget(self.minimize_btn)
        header_layout.addWidget(self.close_btn)

        # drag behavior on the header bar
        self.header_bar.mousePressEvent = self.header_mouse_press_event
        self.header_bar.mouseMoveEvent = self.header_mouse_move_event

        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(8, 6, 8, 8)
        self.main_layout.setSpacing(30)

        # Left Pane: Timer
        self.timer_pane = QFrame()
        timer_layout = QVBoxLayout(self.timer_pane)
        timer_layout.setSpacing(20)
        
        # Timer Display
        self.timer_label = QLabel("25:00")
        self.timer_label.setFont(QFont("Inter", 110, QFont.Weight.Bold))
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timer_label.mousePressEvent = self.on_timer_clicked
        self.timer_label.mouseDoubleClickEvent = self.on_timer_double_clicked
        self.timer_label.mouseMoveEvent = self.on_timer_mouse_move
        self.timer_label.mouseReleaseEvent = self.on_timer_mouse_release
        self.timer_label.setStyleSheet("color: #FFFFFF; letter-spacing: -2px;")
        
        # Start/Pause Button (Large)
        self.start_btn = QPushButton("START")
        self.start_btn.setMinimumHeight(46)
        self.start_btn.setMinimumWidth(130)
        self.start_btn.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.9);
                color: #000;
                border-radius: 25px;
            }
            QPushButton:hover {
                background: #FFFFFF;
            }
        """)
        self.start_btn.clicked.connect(self.toggle_timer)
        
        self.reset_btn = QPushButton("RESET")
        self.reset_btn.setMinimumHeight(46)
        self.reset_btn.setMinimumWidth(96)
        self.reset_btn.setStyleSheet("border-radius: 25px;")
        self.reset_btn.clicked.connect(self.reset_timer)
        
        btns_layout = QHBoxLayout()
        btns_layout.addStretch()
        btns_layout.addWidget(self.start_btn)
        btns_layout.addWidget(self.reset_btn)
        btns_layout.addStretch()
        
        # Presets (Quick Access)
        presets_layout = QHBoxLayout()
        presets_layout.setSpacing(15)
        presets = [("25m", 25), ("50m", 50), ("90m", 90)]
        self.preset_buttons = []
        for label, mins in presets:
            btn = QPushButton(label)
            btn.setMinimumHeight(38)
            btn.setMinimumWidth(68)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked, m=mins: self.set_timer(m))
            self.preset_buttons.append(btn)
            presets_layout.addWidget(btn)
        
        timer_layout.addSpacing(6)
        timer_layout.addStretch()
        timer_layout.addWidget(self.timer_label)
        timer_layout.addLayout(btns_layout)
        timer_layout.addStretch()
        timer_layout.addLayout(presets_layout)

        # Right Pane: To-Do
        self.todo_pane = QFrame()
        self.todo_pane.setMinimumWidth(280)
        self.todo_pane.setMaximumWidth(540)
        self.todo_pane.setObjectName("TodoPane")
        self.todo_pane.setStyleSheet("""
            #TodoPane {
                background: rgba(255, 255, 255, 0.04);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        todo_layout = QVBoxLayout(self.todo_pane)
        todo_layout.setContentsMargins(20, 25, 20, 20)
        
        todo_title = QLabel("To-Do List")
        todo_title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        todo_title.setStyleSheet("margin-bottom: 10px;")
        
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Add new task...")
        self.task_input.returnPressed.connect(self.add_task)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.tasks_layout = QVBoxLayout(self.scroll_content)
        self.tasks_layout.setContentsMargins(0, 10, 0, 0)
        self.tasks_layout.setSpacing(10)
        self.tasks_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_content)
        
        todo_layout.addWidget(todo_title)
        todo_layout.addWidget(self.task_input)
        todo_layout.addWidget(self.scroll_area)

        self.main_layout.addWidget(self.timer_pane, 6)
        self.main_layout.addWidget(self.todo_pane, 4)
        self.container_layout.addWidget(self.header_bar)
        self.container_layout.addLayout(self.main_layout)
        self.update_responsive_ui()

    def install_resize_event_filters(self):
        self.setMouseTracking(True)
        self._set_mouse_tracking_recursive(self)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def _set_mouse_tracking_recursive(self, widget):
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.setMouseTracking(True)

    def _event_window_pos(self, watched, event):
        global_pos = watched.mapToGlobal(event.position().toPoint())
        return self.mapFromGlobal(global_pos), global_pos

    def _detect_resize_edges(self, pos):
        if self.is_focus_mode:
            return None
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        margin = self.resize_margin

        left = x <= margin
        right = x >= w - margin
        top = y <= margin
        bottom = y >= h - margin

        edges = []
        if left:
            edges.append(Qt.Edge.LeftEdge)
        if right:
            edges.append(Qt.Edge.RightEdge)
        if top:
            edges.append(Qt.Edge.TopEdge)
        if bottom:
            edges.append(Qt.Edge.BottomEdge)
        return edges or None

    def _cursor_for_edges(self, edges):
        edge_set = set(edges or [])
        if {Qt.Edge.LeftEdge, Qt.Edge.TopEdge} == edge_set or {Qt.Edge.RightEdge, Qt.Edge.BottomEdge} == edge_set:
            return Qt.CursorShape.SizeFDiagCursor
        if {Qt.Edge.RightEdge, Qt.Edge.TopEdge} == edge_set or {Qt.Edge.LeftEdge, Qt.Edge.BottomEdge} == edge_set:
            return Qt.CursorShape.SizeBDiagCursor
        if Qt.Edge.LeftEdge in edge_set or Qt.Edge.RightEdge in edge_set:
            return Qt.CursorShape.SizeHorCursor
        if Qt.Edge.TopEdge in edge_set or Qt.Edge.BottomEdge in edge_set:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def _apply_resize(self, global_pos):
        if not self.resize_edges or self.resize_start_geometry is None or self.resize_start_global is None:
            return
        delta = global_pos - self.resize_start_global
        geom = self.resize_start_geometry

        left = geom.left()
        top = geom.top()
        right = geom.right()
        bottom = geom.bottom()

        if Qt.Edge.LeftEdge in self.resize_edges:
            left += delta.x()
        if Qt.Edge.RightEdge in self.resize_edges:
            right += delta.x()
        if Qt.Edge.TopEdge in self.resize_edges:
            top += delta.y()
        if Qt.Edge.BottomEdge in self.resize_edges:
            bottom += delta.y()

        new_width = right - left + 1
        new_height = bottom - top + 1

        min_w, min_h = self.minimumWidth(), self.minimumHeight()
        max_w, max_h = self.maximumWidth(), self.maximumHeight()

        if new_width < min_w:
            if Qt.Edge.LeftEdge in self.resize_edges:
                left = right - min_w + 1
            else:
                right = left + min_w - 1
            new_width = min_w
        elif new_width > max_w:
            if Qt.Edge.LeftEdge in self.resize_edges:
                left = right - max_w + 1
            else:
                right = left + max_w - 1
            new_width = max_w

        if new_height < min_h:
            if Qt.Edge.TopEdge in self.resize_edges:
                top = bottom - min_h + 1
            else:
                bottom = top + min_h - 1
            new_height = min_h
        elif new_height > max_h:
            if Qt.Edge.TopEdge in self.resize_edges:
                top = bottom - max_h + 1
            else:
                bottom = top + max_h - 1
            new_height = max_h

        self.setGeometry(left, top, new_width, new_height)

    def _set_resize_cursor(self, cursor_shape):
        if cursor_shape == Qt.CursorShape.ArrowCursor:
            if self._using_override_cursor:
                QApplication.restoreOverrideCursor()
                self._using_override_cursor = False
            return
        if self._using_override_cursor:
            QApplication.changeOverrideCursor(cursor_shape)
        else:
            QApplication.setOverrideCursor(cursor_shape)
            self._using_override_cursor = True

    def eventFilter(self, watched, event):
        if not isinstance(watched, QWidget):
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            window_pos, global_pos = self._event_window_pos(watched, event)
            edges = self._detect_resize_edges(window_pos)
            if edges:
                self.resize_edges = edges
                self.resize_start_global = global_pos
                self.resize_start_geometry = self.geometry()
                return True

        if event.type() == QEvent.Type.MouseMove:
            window_pos, global_pos = self._event_window_pos(watched, event)
            if self.resize_edges and event.buttons() & Qt.MouseButton.LeftButton:
                self._apply_resize(global_pos)
                return True

            if not (event.buttons() & Qt.MouseButton.LeftButton):
                edges = self._detect_resize_edges(window_pos)
                self._set_resize_cursor(self._cursor_for_edges(edges))

        if event.type() == QEvent.Type.MouseButtonRelease:
            if self.resize_edges:
                self.resize_edges = None
                self.resize_start_global = None
                self.resize_start_geometry = None
                self._set_resize_cursor(Qt.CursorShape.ArrowCursor)
                return True

        return super().eventFilter(watched, event)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, activated=self.toggle_always_on_top)
        QShortcut(QKeySequence("Ctrl+Shift+M"), self, activated=self.toggle_clock_mode)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.toggle_compact)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, activated=self.toggle_focus_mode)

    def apply_container_style(self):
        container_background = "rgba(255, 255, 255, 0.02)" if self.acrylic_enabled else "rgba(18, 18, 18, 0.88)"
        self.container.setStyleSheet(
            """
            #MainContainer {{
                background: {0};
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 25px;
            }}
            """.format(container_background)
        )

    def header_button_style(self, active):
        if active:
            return (
                "QPushButton {"
                "background: rgba(120, 180, 255, 0.40);"
                "border: 1px solid rgba(170, 210, 255, 0.85);"
                "color: white;"
                "border-radius: 12px;"
                "font-size: 12px;"
                "font-weight: 700;"
                "padding: 0 14px;"
                "}"
            )
        return (
            "QPushButton {"
            "background: rgba(255, 255, 255, 0.10);"
            "border: 1px solid rgba(255, 255, 255, 0.20);"
            "color: white;"
            "border-radius: 12px;"
            "font-size: 12px;"
            "font-weight: 700;"
            "padding: 0 14px;"
            "}"
            "QPushButton:hover {"
            "background: rgba(255, 255, 255, 0.18);"
            "border: 1px solid rgba(255, 255, 255, 0.30);"
            "}"
        )

    def apply_layout_mode(self):
        layout_mode = "focus" if self.is_focus_mode else "clock" if self.is_clock_mode else "compact" if self.is_compact else "normal"
        mode_changed = layout_mode != self.current_layout_mode
        self.current_layout_mode = layout_mode

        in_clock_like_mode = self.is_clock_mode or self.is_focus_mode
        show_todo = (not self.is_compact) and (not self.is_clock_mode) and (not self.is_focus_mode)

        self.todo_pane.setVisible(show_todo)
        self.start_btn.setVisible(not in_clock_like_mode)
        self.reset_btn.setVisible(not in_clock_like_mode)
        for preset_btn in self.preset_buttons:
            preset_btn.setVisible(not in_clock_like_mode)

        self.header_bar.setVisible(not self.is_focus_mode)

        if layout_mode == "focus":
            self.container_layout.setContentsMargins(8, 6, 8, 8)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)
            self.timer_pane.layout().setContentsMargins(0, 0, 0, 0)
            self.timer_pane.layout().setSpacing(0)
            self.timer_label.setFont(QFont("Inter", 54, QFont.Weight.Bold))
            self.setMinimumSize(*self.focus_size)
            self.setMaximumSize(*self.focus_size)
            if mode_changed:
                self.resize(*self.focus_size)
                self.move_focus_to_top_right()
        elif layout_mode == "clock":
            self.container_layout.setContentsMargins(14, 12, 14, 14)
            self.main_layout.setContentsMargins(8, 6, 8, 8)
            self.main_layout.setSpacing(30)
            self.timer_pane.layout().setContentsMargins(9, 9, 9, 9)
            self.timer_pane.layout().setSpacing(20)
            self.setMinimumSize(360, 220)
            self.apply_maximum_to_screen()
            if mode_changed:
                self.resize(*self.clock_size)
        elif layout_mode == "compact":
            self.container_layout.setContentsMargins(14, 12, 14, 14)
            self.main_layout.setContentsMargins(8, 6, 8, 8)
            self.main_layout.setSpacing(30)
            self.timer_pane.layout().setContentsMargins(9, 9, 9, 9)
            self.timer_pane.layout().setSpacing(20)
            self.setMinimumSize(680, 420)
            self.apply_maximum_to_screen()
            if mode_changed:
                self.resize(*self.compact_size)
        else:
            self.container_layout.setContentsMargins(14, 12, 14, 14)
            self.main_layout.setContentsMargins(8, 6, 8, 8)
            self.main_layout.setSpacing(30)
            self.timer_pane.layout().setContentsMargins(9, 9, 9, 9)
            self.timer_pane.layout().setSpacing(20)
            self.setMinimumSize(780, 460)
            self.apply_maximum_to_screen()
            if mode_changed:
                self.resize(*self.normal_size)
        self.update_responsive_ui()

    def apply_maximum_to_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.setMaximumSize(16777215, 16777215)
            return
        available = screen.availableGeometry()
        self.setMaximumSize(available.width(), available.height())

    def move_focus_to_top_right(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        margin = 14
        target_x = available.x() + available.width() - self.width() - margin
        target_y = available.y() + margin
        self.move(target_x, target_y)

    def update_responsive_ui(self):
        if not hasattr(self, "timer_pane") or not hasattr(self, "timer_label"):
            return

        if self.is_focus_mode:
            # Keep focus-mode compact and clean.
            self.timer_label.setFont(QFont("Inter", 54, QFont.Weight.Bold))
            return

        timer_width = max(300, self.timer_pane.width())
        timer_height = max(220, self.timer_pane.height())

        # Scale timer text with available space.
        if self.is_clock_mode:
            timer_font_size = max(48, min(112, int(min(timer_width * 0.20, timer_height * 0.46))))
        else:
            timer_font_size = max(52, min(132, int(min(timer_width * 0.22, timer_height * 0.50))))
        self.timer_label.setFont(QFont("Inter", timer_font_size, QFont.Weight.Bold))

        button_height = max(40, min(56, int(timer_height * 0.11)))
        self.start_btn.setMinimumHeight(button_height)
        self.reset_btn.setMinimumHeight(button_height)
        for btn in self.preset_buttons:
            btn.setMinimumHeight(max(34, int(button_height * 0.82)))

        todo_font_size = max(10, min(14, int(self.todo_pane.width() / 34)))
        for i in range(self.tasks_layout.count()):
            widget = self.tasks_layout.itemAt(i).widget()
            if isinstance(widget, TaskItem):
                widget.label.setFont(QFont("Inter", todo_font_size))

        # Right pane width is controlled by layout stretch factors.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_window_mask()
        try:
            self.update_responsive_ui()
        except Exception:
            # Never crash on resize during early widget initialization.
            pass

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Fallback icon
        px = QPixmap(64, 64)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(255, 255, 255, 200)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(10, 10, 44, 44)
        p.end()
        self.tray_icon.setIcon(QIcon(px))
        
        tray_menu = QMenu()
        show_action = QAction("Open", self)
        show_action.triggered.connect(self.restore_window)
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.restore_window()

    def restore_window(self):
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def minimize_to_tray(self):
        # Avoid frameless/minimized visual artifacts by hiding directly.
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.hide()

    def toggle_always_on_top(self):
        if self.is_focus_mode:
            return
        self.apply_always_on_top(self.pin_btn.isChecked())

    def apply_always_on_top(self, enabled):
        was_visible = self.isVisible()
        if was_visible:
            self.hide()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if was_visible:
            self.show()
        self.pin_btn.setChecked(enabled)
        is_checked = self.pin_btn.isChecked()
        self.pin_btn.setStyleSheet(self.header_button_style(is_checked))
        if was_visible:
            self.raise_()
            self.activateWindow()

    def toggle_compact(self):
        if self.is_clock_mode or self.is_focus_mode:
            return
        self.is_compact = not self.is_compact
        self.compact_btn.setChecked(self.is_compact)
        self.compact_btn.setStyleSheet(self.header_button_style(self.is_compact))
        self.apply_layout_mode()

    def toggle_clock_mode(self):
        if self.is_focus_mode:
            return
        self.is_clock_mode = not self.is_clock_mode
        self.clock_btn.setChecked(self.is_clock_mode)
        self.clock_btn.setStyleSheet(self.header_button_style(self.is_clock_mode))
        self.apply_layout_mode()

    def toggle_focus_mode(self):
        if not self.is_focus_mode:
            self.focus_restore_pin_state = self.pin_btn.isChecked()
            self.is_focus_mode = True
            self.focus_drag_start_global = None
            self.focus_drag_window_start = None
            self.drag_pos = None
            self.focus_btn.setChecked(True)
            self.is_clock_mode = False
            self.clock_btn.setChecked(False)
            self.clock_btn.setStyleSheet(self.header_button_style(False))
            self.apply_always_on_top(True)
            self.focus_btn.setStyleSheet(self.header_button_style(True))
            self.apply_layout_mode()
            return

        self.is_focus_mode = False
        self.focus_drag_start_global = None
        self.focus_drag_window_start = None
        self.drag_pos = None
        self.focus_btn.setChecked(False)
        self.focus_btn.setStyleSheet(self.header_button_style(False))
        self.apply_layout_mode()
        self.apply_always_on_top(self.focus_restore_pin_state)

    def header_mouse_press_event(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        QFrame.mousePressEvent(self.header_bar, event)

    def header_mouse_move_event(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
            return
        QFrame.mouseMoveEvent(self.header_bar, event)

    def play_sound(self):
        source_path = self.get_alarm_audio_path()
        if source_path is None:
            return
        self.stop_alarm_sound()
        self.alarm_player.setSource(QUrl.fromLocalFile(source_path))
        self.alarm_player.play()
        self.alarm_active = True
        self.alarm_loop_timer.start(self.alarm_clip_duration_ms)

    def loop_alarm_clip(self):
        if not self.alarm_active:
            return
        self.alarm_player.setPosition(0)
        self.alarm_player.play()
        self.alarm_loop_timer.start(self.alarm_clip_duration_ms)

    def stop_alarm_sound(self):
        self.alarm_active = False
        self.alarm_loop_timer.stop()
        self.alarm_player.stop()

    def get_alarm_audio_path(self):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        bundled_path = os.path.join(getattr(sys, "_MEIPASS", app_dir), "Lofi.mp3")
        local_path = os.path.join(app_dir, "Lofi.mp3")
        user_download_path = os.path.join(os.path.expanduser("~"), "Downloads", "Lofi.mp3")
        explicit_download_path = r"C:\Users\Flavi\Downloads\Lofi.mp3"

        for candidate in (bundled_path, local_path, explicit_download_path, user_download_path):
            if os.path.exists(candidate):
                return candidate
        return None

    def on_alarm_error(self, error, error_string):
        self.stop_alarm_sound()

    def add_task(self):
        text = self.task_input.text().strip()
        if text:
            self.add_task_item(text=text, checked=False)
            self.task_input.clear()
            self.save_tasks()

    def add_task_item(self, text, checked=False):
        item = TaskItem(text=text, checked=checked)
        item.deleteRequested.connect(self.remove_task)
        item.changed.connect(self.save_tasks)
        self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, item)
        return item

    def remove_task(self, item):
        self.tasks_layout.removeWidget(item)
        item.deleteLater()
        self.save_tasks()

    def get_tasks_file_path(self):
        appdata = os.getenv("APPDATA")
        if appdata:
            base_dir = os.path.join(appdata, "PomodoroTimer")
        else:
            base_dir = os.path.join(os.path.expanduser("~"), ".pomodoro_timer")
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "tasks.json")

    def save_tasks(self):
        tasks_data = []
        for i in range(self.tasks_layout.count()):
            widget = self.tasks_layout.itemAt(i).widget()
            if isinstance(widget, TaskItem):
                tasks_data.append(widget.to_dict())

        try:
            with open(self.get_tasks_file_path(), "w", encoding="utf-8") as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_tasks(self):
        file_path = self.get_tasks_file_path()
        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tasks_data = json.load(f)
        except Exception:
            return

        if not isinstance(tasks_data, list):
            return

        for task in tasks_data:
            if not isinstance(task, dict):
                continue
            text = str(task.get("text", "")).strip()
            checked = bool(task.get("checked", False))
            if text:
                self.add_task_item(text=text, checked=checked)

    def set_timer(self, mins):
        self.stop_alarm_sound()
        self.remaining_seconds = mins * 60
        self.update_label()
        if self.timer.isActive():
            self.timer.stop()
            self.start_btn.setText("START")

    def toggle_timer(self):
        self.stop_alarm_sound()
        if self.timer.isActive():
            self.timer.stop()
            self.start_btn.setText("START")
        else:
            if self.remaining_seconds <= 0: return
            self.timer.start(1000)
            self.start_btn.setText("PAUSE")

    def reset_timer(self):
        self.stop_alarm_sound()
        self.timer.stop()
        self.remaining_seconds = 25 * 60
        self.update_label()
        self.start_btn.setText("START")

    def update_timer(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.update_label()
        else:
            self.timer.stop()
            self.start_btn.setText("START")
            self.play_sound()
            self.tray_icon.showMessage("Timer Finished", "Time to take a break!", QSystemTrayIcon.MessageIcon.Information)

    def update_label(self):
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        self.timer_label.setText(f"{mins:02d}:{secs:02d}")

    def on_timer_clicked(self, event):
        if self.is_focus_mode:
            if event.button() == Qt.MouseButton.LeftButton:
                self.focus_drag_start_global = event.globalPosition().toPoint()
                self.focus_drag_window_start = self.pos()
                event.accept()
            return
        mins, ok = QInputDialog.getInt(self, "Set Timer", "Enter minutes:", self.remaining_seconds // 60, 1, 999)
        if ok:
            self.set_timer(mins)

    def on_timer_mouse_move(self, event):
        if self.is_focus_mode:
            if (
                event.buttons() & Qt.MouseButton.LeftButton
                and self.focus_drag_start_global is not None
                and self.focus_drag_window_start is not None
            ):
                delta = event.globalPosition().toPoint() - self.focus_drag_start_global
                self.move(self.focus_drag_window_start + delta)
                event.accept()
            return
        QLabel.mouseMoveEvent(self.timer_label, event)

    def on_timer_mouse_release(self, event):
        if self.is_focus_mode:
            self.focus_drag_start_global = None
            self.focus_drag_window_start = None
            self.drag_pos = None
            event.accept()
            return
        QLabel.mouseReleaseEvent(self.timer_label, event)

    def on_timer_double_clicked(self, event):
        if self.is_focus_mode:
            self.toggle_focus_mode()
            return
        QLabel.mouseDoubleClickEvent(self.timer_label, event)

    def mousePressEvent(self, event):
        if not self.is_focus_mode:
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.is_focus_mode:
            super().mouseMoveEvent(event)
            return
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        super().mouseReleaseEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PomodoroTimer()
    window.show()
    sys.exit(app.exec())
