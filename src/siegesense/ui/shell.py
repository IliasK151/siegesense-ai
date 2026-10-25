"""Initial desktop shell with explicit demo-mode presentation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from siegesense.services.session_service import SessionService

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

NAV_ITEMS = [
    ("Overview", "⌂", "Your performance workspace"),
    ("Aim Lab", "◎", "Aim observations and measurable practice"),
    ("Movement", "↗", "Review movement and positioning"),
    ("Settings Lab", "⚙", "Run deliberate settings experiments"),
    ("Session Review", "▣", "Review recorded footage and observations"),
    ("AI Coach", "✳", "Evidence-linked coaching, when available"),
    ("Preferences & Privacy", "☷", "Capture, data, and application preferences"),
]


def panel(title: str, body: str, *, object_name: str = "Panel") -> QFrame:
    """Create a reusable, accessible content panel."""
    frame = QFrame()
    frame.setObjectName(object_name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 18)
    layout.setSpacing(10)

    heading = QLabel(title)
    heading.setObjectName("PanelTitle")
    description = QLabel(body)
    description.setObjectName("Muted")
    description.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(description)
    return frame


def metric_card(label: str, value: str, hint: str) -> QFrame:
    card = QFrame()
    card.setObjectName("MetricCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 15, 16, 15)
    layout.setSpacing(7)

    label_widget = QLabel(label.upper())
    label_widget.setObjectName("MetricLabel")
    value_widget = QLabel(value)
    value_widget.setObjectName("MetricValue")
    hint_widget = QLabel(hint)
    hint_widget.setObjectName("MetricHint")
    hint_widget.setWordWrap(True)

    layout.addWidget(label_widget)
    layout.addWidget(value_widget)
    layout.addWidget(hint_widget)
    layout.addStretch(1)
    card.setMinimumWidth(150)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return card


class MainWindow(QMainWindow):
    """Main application window and navigation host."""

    def __init__(self, session_service: SessionService | None = None) -> None:
        super().__init__()
        self.session_service = session_service
        self.setWindowTitle("SiegeSense AI")
        self.resize(1320, 850)
        self.setMinimumSize(960, 640)
        self._collapsed = False
        self._nav_buttons: dict[str, QPushButton] = {}

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(238)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 14)
        sidebar_layout.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_mark = QLabel("S")
        brand_mark.setObjectName("BrandMark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand_name = QLabel("SiegeSense")
        brand_name.setObjectName("BrandName")
        brand_subtitle = QLabel("PERFORMANCE LAB")
        brand_subtitle.setObjectName("BrandSubtitle")
        brand_text.addWidget(brand_name)
        brand_text.addWidget(brand_subtitle)
        brand_row.addWidget(brand_mark)
        brand_row.addLayout(brand_text, 1)
        sidebar_layout.addLayout(brand_row)

        sidebar_layout.addSpacing(22)
        section_label = QLabel("WORKSPACE")
        section_label.setObjectName("BrandSubtitle")
        sidebar_layout.addWidget(section_label)

        for name, glyph, tooltip in NAV_ITEMS:
            button = QPushButton(f"{glyph}   {name}")
            button.setObjectName("NavButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(tooltip)
            button.setMinimumHeight(42)
            button.setProperty("active", name == "Overview")
            button.clicked.connect(lambda checked=False, page=name: self.show_page(page))
            sidebar_layout.addWidget(button)
            self._nav_buttons[name] = button

        sidebar_layout.addStretch(1)
        privacy_note = QLabel("LOCAL-FIRST BY DESIGN")
        privacy_note.setObjectName("BrandSubtitle")
        sidebar_layout.addWidget(privacy_note)

        self.collapse_button = QPushButton("‹   Collapse sidebar")
        self.collapse_button.setObjectName("CollapseButton")
        self.collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_button.clicked.connect(self.toggle_sidebar)
        sidebar_layout.addWidget(self.collapse_button)

        content_column = QVBoxLayout()
        content_column.setContentsMargins(28, 22, 28, 24)
        content_column.setSpacing(18)

        topbar = QHBoxLayout()
        topbar.setSpacing(10)
        self.breadcrumb = QLabel("Workspace  /  Overview")
        self.breadcrumb.setObjectName("Muted")
        topbar.addWidget(self.breadcrumb)
        topbar.addStretch(1)
        demo_badge = QLabel("DEMO MODE · NO REAL PERFORMANCE DATA")
        demo_badge.setObjectName("StatusPill")
        topbar.addWidget(demo_badge)
        content_column.addLayout(topbar)

        self.page_stack = QStackedWidget()
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        for name, _, description in NAV_ITEMS:
            self.page_stack.addWidget(self._build_page(name, description))
        content_column.addWidget(self.page_stack, 1)

        root_layout.addWidget(self.sidebar)
        content_host = QWidget()
        content_host.setLayout(content_column)
        root_layout.addWidget(content_host, 1)
        self.setCentralWidget(root)

    def _build_page(self, name: str, description: str) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(18)

        eyebrow = QLabel("SIEGESENSE AI  /  WORKSPACE")
        eyebrow.setObjectName("PageEyebrow")
        title = QLabel(name)
        title.setObjectName("PageTitle")
        subtitle = QLabel(description)
        subtitle.setObjectName("PageDescription")
        subtitle.setWordWrap(True)
        page_layout.addWidget(eyebrow)
        page_layout.addWidget(title)
        page_layout.addWidget(subtitle)

        if name == "Overview":
            metrics = QHBoxLayout()
            metrics.setSpacing(12)
            metrics.addWidget(metric_card("Sessions reviewed", "—", "No real sessions recorded"))
            metrics.addWidget(metric_card("Observations", "—", "No observations recorded"))
            metrics.addWidget(metric_card("Active experiments", "—", "No settings experiments"))
            metrics.addWidget(metric_card("Trend confidence", "—", "Requires validated data"))
            page_layout.addLayout(metrics)

            body_row = QHBoxLayout()
            body_row.setSpacing(14)
            trend_panel = panel(
                "Performance over time",
                "Your trend chart will appear after real sessions are reviewed. "
                "Demo examples are intentionally not plotted as personal progress.",
            )
            trend_panel.setMinimumHeight(210)
            priorities_panel = panel(
                "Coaching priorities",
                "No priorities yet. Add a session and timestamped observations to build "
                "an evidence-backed review.",
            )
            priorities_panel.setMinimumWidth(250)
            body_row.addWidget(trend_panel, 2)
            body_row.addWidget(priorities_panel, 1)
            page_layout.addLayout(body_row)

            page_layout.addWidget(
                panel(
                    "Start with a real session",
                    "Choose a recorded match, add observations at meaningful timestamps, "
                    "then test one settings variable at a time. This early shell does not "
                    "yet analyse gameplay automatically.",
                )
            )
        else:
            empty = QFrame()
            empty.setObjectName("Panel")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(24, 24, 24, 24)
            empty_layout.setSpacing(12)
            icon = QLabel(NAV_ITEMS[[item[0] for item in NAV_ITEMS].index(name)][1])
            icon.setObjectName("EmptyIcon")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            heading = QLabel(f"{name} workspace")
            heading.setObjectName("PanelTitle")
            message = QLabel(
                "This workspace is scaffolded, but its feature workflow has not been "
                "implemented yet. We will add it through a tracked issue and a reviewed change."
            )
            message.setObjectName("Muted")
            message.setWordWrap(True)
            empty_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignLeft)
            empty_layout.addWidget(heading)
            empty_layout.addWidget(message)
            empty_layout.addStretch(1)
            page_layout.addWidget(empty, 1)

        page_layout.addStretch(1)
        return page

    def show_page(self, name: str) -> None:
        """Select a page and keep the active navigation state in sync."""
        index = [item[0] for item in NAV_ITEMS].index(name)
        self.page_stack.setCurrentIndex(index)
        self.breadcrumb.setText(f"Workspace  /  {name}")
        for item_name, button in self._nav_buttons.items():
            button.setProperty("active", item_name == name)
            button.style().unpolish(button)
            button.style().polish(button)

    def toggle_sidebar(self) -> None:
        """Collapse navigation while retaining readable tooltips."""
        self._collapsed = not self._collapsed
        self.sidebar.setFixedWidth(76 if self._collapsed else 238)
        self.collapse_button.setText("›" if self._collapsed else "‹   Collapse sidebar")
        for name, glyph, tooltip in NAV_ITEMS:
            button = self._nav_buttons[name]
            button.setText(glyph if self._collapsed else f"{glyph}   {name}")
            button.setToolTip(f"{name} — {tooltip}" if self._collapsed else tooltip)
        self.collapse_button.setToolTip(
            "Expand navigation" if self._collapsed else "Collapse navigation"
        )
