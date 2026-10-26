"""Initial desktop shell with explicit demo-mode presentation."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from statistics import median

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from siegesense.domain.models import ObservationKind
from siegesense.services.coaching_service import COACHING_TAG_GUIDE, build_coaching_insights
from siegesense.services.export_service import (
    render_session_csv,
    render_session_json,
    render_session_summary,
)
from siegesense.services.game_settings_import_service import read_game_settings_ini
from siegesense.services.session_service import SessionService
from siegesense.services.settings_service import SettingsService
from siegesense.ui.point_picker import PointPickerLabel
from siegesense.vision.aim_transition_analysis import (
    summarize_aim_transitions,
    write_aim_transition_report,
)
from siegesense.vision.annotations import ALLOWED_LABELS, AnnotationStore, load_manifest
from siegesense.vision.evaluation import summarize_aim_frames, write_evaluation_report
from siegesense.vision.frame_sampling import sample_video_frames
from siegesense.vision.motion_analysis import analyze_manifest_motion, write_motion_report
from siegesense.vision.sequence_analysis import summarize_annotated_sequences
from siegesense.vision.spatial_analysis import summarize_spatial_error, write_spatial_report

NAV_ITEMS = [
    ("Overview", "⌂", "Your performance workspace"),
    ("Aim Lab", "◎", "Aim observations and measurable practice"),
    ("Movement", "↗", "Review movement and positioning"),
    ("Settings Lab", "⚙", "Run deliberate settings experiments"),
    ("Session Review", "▣", "Review recorded footage and observations"),
    ("Clip Annotation", "✎", "Label sampled frames for future model validation"),
    ("AI Coach", "✳", "Evidence-linked coaching, when available"),
    ("Preferences & Privacy", "☷", "Capture, data, and application preferences"),
]


SUPPORTED_VIDEO_SUFFIXES = frozenset({".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"})


class VideoDropZone(QFrame):
    """Large, simple drop target for starting a local recording review."""

    video_dropped = Signal(str)
    browse_requested = Signal()

    def __init__(self, prompt: str = "Drop a gameplay video here", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoDropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(148)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(8)
        title = QLabel(prompt)
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("MP4, MKV, MOV, AVI or WEBM · video stays on this PC")
        subtitle.setObjectName("Muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        button = QPushButton("Choose a video")
        button.setObjectName("PrimaryButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self.browse_requested.emit)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    @staticmethod
    def _first_local_video(event) -> str | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            candidate = Path(url.toLocalFile())
            if candidate.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES:
                return str(candidate)
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt event name
        if self._first_local_video(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt event name
        if self._first_local_video(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt event name
        path = self._first_local_video(event)
        if path:
            self.video_dropped.emit(path)
            event.acceptProposedAction()
        else:
            event.ignore()


class VideoSamplingWorker(QThread):
    """Sample a dropped recording in the background so the UI remains responsive."""

    succeeded = Signal(object, str)
    failed = Signal(str)

    def __init__(self, source: str, output_dir: str, interval_ms: int) -> None:
        super().__init__()
        self.source = source
        self.output_dir = output_dir
        self.interval_ms = interval_ms

    def run(self) -> None:
        try:
            report = sample_video_frames(
                self.source,
                self.output_dir,
                interval_ms=self.interval_ms,
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.succeeded.emit(report, self.output_dir)


def _median_coherent_ratio(pairs: tuple) -> float:
    """Return the median descriptive coherence ratio for analyzed frame pairs."""
    return median(pair.coherent_feature_ratio for pair in pairs)


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

    def __init__(
        self,
        session_service: SessionService | None = None,
        settings_service: SettingsService | None = None,
        database_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.session_service = session_service
        self.settings_service = settings_service
        self.database_path = Path(database_path) if database_path is not None else None
        self.setWindowTitle("SiegeSense AI")
        self.resize(1320, 850)
        self.setMinimumSize(960, 640)
        self._collapsed = False
        self._nav_buttons: dict[str, QPushButton] = {}
        self._sampling_worker: VideoSamplingWorker | None = None

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
        self.data_mode_badge = QLabel("LOCAL DATA · DEMO RECORDS HIDDEN")
        self.data_mode_badge.setObjectName("StatusPill")
        topbar.addWidget(self.data_mode_badge)
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
        self._refresh_overview()

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

        if name == "Session Review":
            self._build_session_review(page_layout)
        elif name == "Settings Lab":
            self._build_settings_lab(page_layout)
        elif name == "Clip Annotation":
            self._build_annotation_lab(page_layout)
        elif name == "AI Coach":
            self._build_ai_coach(page_layout)
        elif name == "Preferences & Privacy":
            self._build_preferences(page_layout)
        elif name in {"Aim Lab", "Movement"}:
            self._build_category_review(page_layout, name)
        elif name == "Overview":
            overview_review_panel = QFrame()
            overview_review_panel.setObjectName("Panel")
            overview_review_layout = QVBoxLayout(overview_review_panel)
            overview_review_layout.setContentsMargins(18, 16, 18, 18)
            overview_review_layout.setSpacing(10)
            overview_review_title = QLabel("Start a recording review")
            overview_review_title.setObjectName("PanelTitle")
            overview_review_layout.addWidget(overview_review_title)
            self.overview_video_drop_zone = VideoDropZone()
            self.overview_video_drop_zone.video_dropped.connect(self._start_video_review)
            self.overview_video_drop_zone.browse_requested.connect(self._browse_annotation_video)
            overview_review_layout.addWidget(self.overview_video_drop_zone)
            self.overview_review_status = QLabel(
                "Drop one video to create a review automatically. Frames and notes stay local."
            )
            self.overview_review_status.setObjectName("Muted")
            self.overview_review_status.setWordWrap(True)
            overview_review_layout.addWidget(self.overview_review_status)
            page_layout.addWidget(overview_review_panel)

            metrics = QHBoxLayout()
            metrics.setSpacing(12)
            self._overview_metric_values: dict[str, QLabel] = {}
            metric_specs = (
                ("sessions", "Sessions", "Real sessions saved locally"),
                ("observations", "Observations", "Timestamped notes from reviews"),
                ("experiments", "Active experiments", "Planned or running tests"),
                ("recordings", "Recorded videos", "Sessions linked to local footage"),
            )
            for key, label, hint in metric_specs:
                card = metric_card(label, "0", hint)
                value_label = card.findChild(QLabel, "MetricValue")
                if value_label is not None:
                    self._overview_metric_values[key] = value_label
                metrics.addWidget(card)
            page_layout.addLayout(metrics)

            quick_actions_panel = QFrame()
            quick_actions_panel.setObjectName("Panel")
            quick_actions_layout = QVBoxLayout(quick_actions_panel)
            quick_actions_layout.setContentsMargins(18, 16, 18, 18)
            quick_actions_layout.setSpacing(10)
            quick_actions_title = QLabel("Start here")
            quick_actions_title.setObjectName("PanelTitle")
            quick_actions_layout.addWidget(quick_actions_title)
            quick_actions_hint = QLabel(
                "Use one short review loop: attach a recording, mark what you observe, then test one change at a time."
            )
            quick_actions_hint.setObjectName("Muted")
            quick_actions_hint.setWordWrap(True)
            quick_actions_layout.addWidget(quick_actions_hint)
            quick_actions_row = QHBoxLayout()
            quick_actions_row.setSpacing(8)
            self.overview_action_buttons: dict[str, QPushButton] = {}
            for label, destination in (
                ("Review a recording", "Session Review"),
                ("Analyze a clip", "Clip Annotation"),
                ("Test a setting", "Settings Lab"),
                ("View coaching", "AI Coach"),
            ):
                action = QPushButton(label)
                action.setObjectName(
                    "PrimaryButton" if destination == "Session Review" else "SecondaryButton"
                )
                action.setCursor(Qt.CursorShape.PointingHandCursor)
                action.clicked.connect(
                    lambda checked=False, target=destination: self.show_page(target)
                )
                quick_actions_row.addWidget(action)
                self.overview_action_buttons[destination] = action
            quick_actions_layout.addLayout(quick_actions_row)
            page_layout.addWidget(quick_actions_panel)

            body_row = QHBoxLayout()
            body_row.setSpacing(14)
            self.overview_activity_panel = QFrame()
            self.overview_activity_panel.setObjectName("Panel")
            activity_layout = QVBoxLayout(self.overview_activity_panel)
            activity_layout.setContentsMargins(18, 16, 18, 18)
            activity_layout.setSpacing(10)
            activity_layout.addWidget(QLabel("Recent review activity"))
            self.overview_activity_list = QListWidget()
            self.overview_activity_list.setMinimumHeight(210)
            activity_layout.addWidget(self.overview_activity_list)
            self.overview_activity_note = QLabel(
                "Activity is based on your saved local sessions and manual observations, not automated gameplay analysis."
            )
            self.overview_activity_note.setObjectName("Muted")
            self.overview_activity_note.setWordWrap(True)
            activity_layout.addWidget(self.overview_activity_note)

            priorities_panel = QFrame()
            priorities_panel.setObjectName("Panel")
            priorities_layout = QVBoxLayout(priorities_panel)
            priorities_layout.setContentsMargins(18, 16, 18, 18)
            priorities_layout.setSpacing(10)
            priorities_layout.addWidget(QLabel("Review focus"))
            self.overview_priority_list = QListWidget()
            self.overview_priority_list.setMinimumHeight(210)
            priorities_layout.addWidget(self.overview_priority_list)
            body_row.addWidget(self.overview_activity_panel, 2)
            body_row.addWidget(priorities_panel, 1)
            page_layout.addLayout(body_row)

            page_layout.addWidget(
                panel(
                    "Recommended workflow",
                    "Review a recorded match, log timestamped observations, and change one settings variable at a time. "
                    "Counts and review-focus summaries reflect saved notes only; they are not AI diagnoses or proof of improvement.",
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
        # Keep every workspace usable on smaller Windows displays; long review and
        # annotation pages must not silently clip their lower controls.
        scroll_area = QScrollArea()
        scroll_area.setObjectName("WorkspaceScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(page)
        return scroll_area

    def _build_preferences(self, page_layout: QVBoxLayout) -> None:
        """Show where local data lives and expose simple privacy/data controls."""
        page_layout.addWidget(
            panel(
                "Local data",
                "Sessions, notes, settings snapshots, and experiments are stored in a local SQLite database. "
                "Gameplay video files are referenced by path; they are not uploaded by this app.",
            )
        )

        storage_panel = QFrame()
        storage_panel.setObjectName("Panel")
        storage_layout = QVBoxLayout(storage_panel)
        storage_layout.setContentsMargins(18, 16, 18, 18)
        storage_layout.setSpacing(10)
        storage_heading = QLabel("Database location")
        storage_heading.setObjectName("PanelTitle")
        storage_layout.addWidget(storage_heading)
        self.storage_path_label = QLabel("Checking local database location…")
        self.storage_path_label.setWordWrap(True)
        self.storage_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        storage_layout.addWidget(self.storage_path_label)
        self.storage_status_label = QLabel("")
        self.storage_status_label.setObjectName("Muted")
        self.storage_status_label.setWordWrap(True)
        storage_layout.addWidget(self.storage_status_label)
        actions = QHBoxLayout()
        self.open_data_folder_button = QPushButton("Open data folder")
        self.open_data_folder_button.setObjectName("SecondaryButton")
        self.open_data_folder_button.clicked.connect(self._open_local_data_folder)
        actions.addWidget(self.open_data_folder_button)
        self.export_backup_button = QPushButton("Export database backup…")
        self.export_backup_button.setObjectName("PrimaryButton")
        self.export_backup_button.clicked.connect(self._export_database_backup)
        actions.addWidget(self.export_backup_button)
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("SecondaryButton")
        refresh_button.clicked.connect(self._refresh_storage_info)
        actions.addWidget(refresh_button)
        actions.addStretch(1)
        storage_layout.addLayout(actions)
        page_layout.addWidget(storage_panel)

        page_layout.addWidget(
            panel(
                "Privacy and fair play",
                "The preview works from recordings you select and notes you create. It does not inject into Siege, "
                "read protected game memory, automate mouse or keyboard input, or silently change game settings. "
                "Reports are written only when you choose an export location. Keep recordings and exported reports "
                "private if they reveal personal information.",
            )
        )
        page_layout.addWidget(
            panel(
                "What is not available yet",
                "Automatic reticle/opponent detection, live-match analysis, validated overshoot classification, "
                "and proven sensitivity recommendations are not implemented yet. Coaching prompts are based on "
                "explicit tags you add during review and should be treated as practice hypotheses.",
            )
        )
        self._refresh_storage_info()

    def _refresh_storage_info(self) -> None:
        """Refresh the visible local storage path, size, and action availability."""
        if not hasattr(self, "storage_path_label"):
            return
        path = self.database_path
        if path is None:
            self.storage_path_label.setText("Storage path was not supplied by the application.")
            self.storage_status_label.setText(
                "This window was opened without a persistent database path, as in some UI tests."
            )
            self.open_data_folder_button.setEnabled(False)
            self.export_backup_button.setEnabled(False)
            return
        if str(path) == ":memory:":
            self.storage_path_label.setText("In-memory database (temporary)")
            self.storage_status_label.setText(
                "This temporary database disappears when the application closes."
            )
            self.open_data_folder_button.setEnabled(False)
            self.export_backup_button.setEnabled(False)
            return

        location = path.expanduser()
        self.storage_path_label.setText(str(location))
        self.open_data_folder_button.setEnabled(location.parent.is_dir())
        self.export_backup_button.setEnabled(location.is_file())
        if not location.is_file():
            self.storage_status_label.setText(
                "The database file has not been created at this location yet."
            )
            return
        try:
            size_kb = max(1, (location.stat().st_size + 1023) // 1024)
            modified = location.stat().st_mtime
            from datetime import datetime

            modified_text = datetime.fromtimestamp(modified).strftime("%Y-%m-%d %H:%M")
            self.storage_status_label.setText(
                f"Existing local database · {size_kb:,} KB · modified {modified_text}"
            )
        except OSError as error:
            self.storage_status_label.setText(f"Could not inspect the database file: {error}")

    def _open_local_data_folder(self) -> None:
        """Open the directory containing the local database in the platform file manager."""
        path = self.database_path
        if path is None or str(path) == ":memory:":
            self.storage_status_label.setText("A persistent local data folder is not available.")
            return
        folder = path.expanduser().parent
        if not folder.is_dir():
            self.storage_status_label.setText(f"Data folder does not exist: {folder}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve()))):
            self.storage_status_label.setText(
                "Windows could not open the data folder. You can copy the path shown above into File Explorer."
            )

    def _export_database_backup(self) -> None:
        """Create a consistent SQLite backup without copying a live database file."""
        path = self.database_path
        if path is None or str(path) == ":memory:":
            QMessageBox.information(
                self, "Backup unavailable", "A persistent local database is not available in this window."
            )
            return
        source_path = path.expanduser().resolve()
        if not source_path.is_file():
            QMessageBox.information(self, "Database not found", "The local database file does not exist yet.")
            return
        target, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export local database backup",
            str(source_path.with_name("siegesense-backup.sqlite3")),
            "SQLite database (*.sqlite3 *.db)",
        )
        if not target:
            return
        target_path = Path(target).expanduser().resolve()
        if not target_path.suffix:
            target_path = target_path.with_suffix(".sqlite3")
        if target_path == source_path:
            QMessageBox.warning(
                self, "Choose a different file", "The backup must not overwrite the active database."
            )
            return
        source_connection: sqlite3.Connection | None = None
        backup_connection: sqlite3.Connection | None = None
        try:
            source_connection = sqlite3.connect(str(source_path))
            backup_connection = sqlite3.connect(str(target_path))
            source_connection.backup(backup_connection)
        except (OSError, sqlite3.Error) as error:
            QMessageBox.warning(
                self, "Backup failed", f"No backup was created successfully.\n\n{error}"
            )
            return
        finally:
            if backup_connection is not None:
                backup_connection.close()
            if source_connection is not None:
                source_connection.close()
        self.storage_status_label.setText(f"Local database backup exported to {target_path}")

    def _build_category_review(self, page_layout: QVBoxLayout, page_name: str) -> None:
        """Show evidence from manually tagged observations for a single category."""
        category = "aim" if page_name == "Aim Lab" else "movement"
        description = (
            "Review notes tagged as aim. These are manual observations, not automated aim tracking."
            if category == "aim"
            else "Review notes tagged as movement. These are manual observations, not automated movement tracking."
        )
        page_layout.addWidget(panel("What this page measures", description))
        if not hasattr(self, "_category_observation_lists"):
            self._category_observation_lists: dict[str, QListWidget] = {}
            self._category_filter_inputs: dict[str, QLineEdit] = {}
        category_filter = QLineEdit()
        category_filter.setPlaceholderText("Filter by note text or tag…")
        category_filter.textChanged.connect(lambda _text: self._refresh_category_review(category))
        self._category_filter_inputs[category] = category_filter
        page_layout.addWidget(category_filter)
        observation_list = QListWidget()
        observation_list.setMinimumHeight(240)
        self._category_observation_lists[category] = observation_list
        page_layout.addWidget(observation_list, 1)
        refresh = QPushButton("Refresh from saved sessions")
        refresh.clicked.connect(lambda: self._refresh_category_review(category))
        page_layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignLeft)
        self._refresh_category_review(category)

    def _refresh_category_review(self, category: str) -> None:
        observation_list = getattr(self, "_category_observation_lists", {}).get(category)
        if observation_list is None:
            return
        observation_list.clear()
        try:
            sessions = self.session_service.list_sessions() if self.session_service else []
            records = [
                (session, observation)
                for session in sessions
                for observation in (
                    self.session_service.list_observations(session.id)
                    if self.session_service is not None
                    else []
                )
                if observation.kind.value == category
            ]
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            observation_list.addItem(f"Could not load saved observations: {error}")
            return
        records.sort(key=lambda pair: (pair[0].started_at, pair[1].timestamp_ms), reverse=True)
        query = self._category_filter_inputs[category].text().strip().casefold()
        visible = [
            (session, observation)
            for session, observation in records
            if not query
            or query in observation.text.casefold()
            or any(query in tag.casefold() for tag in observation.tags)
        ]
        if not visible:
            message = (
                f"No {category} observations yet. Add one in Session Review to build a useful review history."
                if not records
                else "No observations match this filter."
            )
            observation_list.addItem(message)
            return
        observation_list.addItem(f"{len(visible)} manually logged {category} observation(s)")
        for session, observation in visible:
            seconds = observation.timestamp_ms // 1000
            timestamp = f"{seconds // 60:02d}:{seconds % 60:02d}"
            tags = f"  ·  #{', #'.join(observation.tags)}" if observation.tags else ""
            observation_list.addItem(
                f"{session.title}  ·  {timestamp}  ·  {observation.text}{tags}"
            )

    def _build_ai_coach(self, page_layout: QVBoxLayout) -> None:
        """Build a transparent review assistant from user-supplied evidence."""
        page_layout.addWidget(
            panel(
                "Evidence-linked coach preview",
                "Suggestions are generated from explicit manual tags and saved review notes. This is not a trained "
                "AI model or automatic gameplay detector; the app will not invent a diagnosis when the evidence is missing.",
            )
        )
        refresh = QPushButton("Refresh coaching summary")
        refresh.setObjectName("PrimaryButton")
        refresh.clicked.connect(self._refresh_ai_coach)
        page_layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignLeft)

        self.coach_summary_panel = QFrame()
        self.coach_summary_panel.setObjectName("Panel")
        coach_layout = QVBoxLayout(self.coach_summary_panel)
        coach_layout.setContentsMargins(18, 16, 18, 18)
        coach_layout.setSpacing(10)

        coach_layout.addWidget(QLabel("Review categories"))
        self.coach_prompt_list = QListWidget()
        self.coach_prompt_list.setMinimumHeight(100)
        coach_layout.addWidget(self.coach_prompt_list)

        coach_layout.addWidget(QLabel("Tagged patterns to verify"))
        self.coach_pattern_list = QListWidget()
        self.coach_pattern_list.setMinimumHeight(125)
        self.coach_pattern_list.currentItemChanged.connect(self._show_selected_coaching_insight)
        coach_layout.addWidget(self.coach_pattern_list)
        self.coach_pattern_detail = QLabel(
            "Select a tagged pattern to see its evidence and one focused practice block."
        )
        self.coach_pattern_detail.setObjectName("Muted")
        self.coach_pattern_detail.setWordWrap(True)
        coach_layout.addWidget(self.coach_pattern_detail)
        self.coach_plan_experiment_button = QPushButton(
            "Prepare a controlled settings experiment"
        )
        self.coach_plan_experiment_button.setObjectName("SecondaryButton")
        self.coach_plan_experiment_button.setEnabled(False)
        self.coach_plan_experiment_button.setToolTip(
            "Enabled only for repeated sensitivity-related tags across multiple sessions. "
            "This prepares a test hypothesis; it does not recommend or apply a settings value."
        )
        self.coach_plan_experiment_button.clicked.connect(
            self._prepare_settings_experiment_from_coach
        )
        coach_layout.addWidget(
            self.coach_plan_experiment_button, 0, Qt.AlignmentFlag.AlignLeft
        )

        coach_layout.addWidget(QLabel("Recent evidence"))
        self.coach_evidence_list = QListWidget()
        self.coach_evidence_list.setMinimumHeight(130)
        coach_layout.addWidget(self.coach_evidence_list)
        page_layout.addWidget(self.coach_summary_panel, 1)
        self._coaching_insights_by_key = {}
        self._refresh_ai_coach()

    def _refresh_ai_coach(self) -> None:
        """Regenerate cautious practice prompts and show the notes behind each one."""
        if not hasattr(self, "coach_prompt_list"):
            return
        self.coach_prompt_list.clear()
        self.coach_pattern_list.clear()
        self.coach_evidence_list.clear()
        self.coach_plan_experiment_button.setEnabled(False)
        self._coaching_insights_by_key = {}
        try:
            sessions = self.session_service.list_sessions() if self.session_service else []
            records = [
                (session, observation)
                for session in sessions
                for observation in (
                    self.session_service.list_observations(session.id)
                    if self.session_service is not None
                    else []
                )
            ]
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            self.coach_prompt_list.addItem(f"Local review data is unavailable: {error}")
            self.coach_pattern_list.addItem("Coaching patterns are unavailable until local data can be read.")
            self.coach_evidence_list.addItem("No evidence could be loaded.")
            self.coach_pattern_detail.setText("Resolve the storage error before using these prompts.")
            return
        if not records:
            self.coach_prompt_list.addItem(
                "Start with one recorded match and add a few timestamped notes in Session Review."
            )
            self.coach_pattern_list.addItem(
                "No tagged patterns yet. Begin by tagging an observed moment in Session Review."
            )
            self.coach_evidence_list.addItem("No real-session observations are available yet.")
            self.coach_pattern_detail.setText(
                "Suggested tags: " + ", ".join(COACHING_TAG_GUIDE)
                + ". Only tag what you can actually see."
            )
            return

        counts: dict[str, int] = {}
        for _session, observation in records:
            counts[observation.kind.value] = counts.get(observation.kind.value, 0) + 1
        prompts = {
            "aim": "Aim: separate pre-aim placement, initial endpoint, correction, and shot timing before changing sensitivity.",
            "movement": "Movement: review peeking, exposure, and path choice; do not confuse screen motion with mouse input.",
            "positioning": "Positioning: check cover, escape options, and the angle selected before the engagement.",
            "decision": "Decision-making: compare the choice with the information available at that moment, not only the outcome.",
            "other": "Other: refine the note into one specific behaviour you can check in another review.",
        }
        for category, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
            self.coach_prompt_list.addItem(
                f"{category.title()} · {count} note(s) — {prompts[category]}"
            )
        self.coach_prompt_list.addItem(
            "These are review priorities, not proof of a weakness or an automatic diagnosis."
        )

        insights = build_coaching_insights(records)
        if not insights:
            self.coach_pattern_list.addItem(
                "No explicit coaching tags yet. In Session Review, try: "
                + ", ".join(COACHING_TAG_GUIDE)
                + "."
            )
            self.coach_pattern_detail.setText(
                "Scope tags such as acog and close-range remain useful context, but they do not create a coaching claim by themselves."
            )
        else:
            self._coaching_insights_by_key = {insight.key: insight for insight in insights}
            for insight in insights:
                item = QListWidgetItem(
                    f"{insight.title} · {insight.observation_count} tagged note(s) · "
                    f"{insight.session_count} session(s) · {insight.evidence_level}"
                )
                item.setData(Qt.ItemDataRole.UserRole, insight.key)
                self.coach_pattern_list.addItem(item)
            self.coach_pattern_list.setCurrentRow(0)

        records.sort(key=lambda pair: (pair[0].started_at, pair[1].timestamp_ms), reverse=True)
        for session, observation in records[:10]:
            seconds = observation.timestamp_ms // 1000
            timestamp = f"{seconds // 60:02d}:{seconds % 60:02d}"
            tags = f" · Tags: {', '.join(observation.tags)}" if observation.tags else ""
            self.coach_evidence_list.addItem(
                f"{session.title} · {timestamp} · {observation.kind.value.title()} · {observation.text}{tags}"
            )

    def _show_selected_coaching_insight(
        self, item: QListWidgetItem | None, _previous: QListWidgetItem | None = None
    ) -> None:
        """Display the supporting notes and one next drill for the selected tagged pattern."""
        if not hasattr(self, "coach_pattern_detail"):
            return
        key = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        insight = self._coaching_insights_by_key.get(key) if key else None
        if insight is None:
            self.coach_plan_experiment_button.setEnabled(False)
            return
        self.coach_plan_experiment_button.setEnabled(
            insight.evidence_level == "Recurring across sessions"
            and insight.key in {"overflick", "underflick", "correction"}
        )
        evidence_lines: list[str] = []
        for session, observation in insight.evidence[:3]:
            seconds = observation.timestamp_ms // 1000
            timestamp = f"{seconds // 60:02d}:{seconds % 60:02d}"
            evidence_lines.append(
                f"{session.title} at {timestamp}: {observation.text}"
            )
        evidence_text = "\n".join(evidence_lines)
        self.coach_pattern_detail.setText(
            f"{insight.evidence_level}\n{insight.summary}\n\n"
            f"Next practice block\n{insight.drill}\n\n"
            f"Source notes\n{evidence_text}\n\n"
            "Do not change sensitivity based on this prompt alone. Compare similar situations and "
            "record the result before deciding whether to run a settings experiment."
        )

    def _prepare_settings_experiment_from_coach(self) -> None:
        """Transfer recurring manually tagged aim evidence into an editable experiment draft."""
        item = self.coach_pattern_list.currentItem()
        key = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        insight = self._coaching_insights_by_key.get(key) if key else None
        if (
            insight is None
            or insight.evidence_level != "Recurring across sessions"
            or insight.key not in {"overflick", "underflick", "correction"}
        ):
            return

        tags = {
            " ".join(tag.casefold().replace("_", " ").replace("-", " ").split())
            for _session, observation in insight.evidence
            for tag in observation.tags
        }
        variable = (
            "2.5x ADS sensitivity"
            if any("acog" in tag or "2.5x" in tag for tag in tags)
            else "horizontal sensitivity"
        )
        self.experiment_title_input.setText(f"Coach follow-up: {insight.title}")
        self.experiment_hypothesis_input.setText(
            f"After reviewing {insight.observation_count} manually tagged instances across "
            f"{insight.session_count} sessions, compare similar drills with one small change "
            f"to {variable}; keep every other setting fixed. This is a test hypothesis, not "
            "a recommendation that the setting is wrong."
        )
        self.experiment_variable_input.setText(variable)
        self.show_page("Settings Lab")
        self.settings_status.setText(
            f"Experiment draft prepared from {insight.title}. Verify the displayed fields "
            "against your actual in-game settings, save that as the baseline, change only "
            "the chosen variable for a test snapshot, then compare the snapshots before "
            "recording a result."
        )
        self.experiment_title_input.setFocus()

    def _refresh_overview(self) -> None:
        """Refresh overview counts and review focus from real local records only."""
        if not hasattr(self, "_overview_metric_values"):
            return
        try:
            sessions = self.session_service.list_sessions() if self.session_service else []
            experiments = self.settings_service.list_experiments() if self.settings_service else []
            observations_by_session = {
                session.id: self.session_service.list_observations(session.id)
                for session in sessions
            } if self.session_service else {}
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            for value in self._overview_metric_values.values():
                value.setText("—")
            self.overview_activity_list.clear()
            self.overview_activity_list.addItem(f"Local data could not be loaded: {error}")
            self.overview_priority_list.clear()
            self.overview_priority_list.addItem("Review focus unavailable until storage is accessible.")
            return

        observation_count = sum(len(items) for items in observations_by_session.values())
        active_experiments = sum(item.status in {"planned", "running"} for item in experiments)
        counts = {
            "sessions": len(sessions),
            "observations": observation_count,
            "experiments": active_experiments,
            "recordings": sum(bool(session.media_path) for session in sessions),
        }
        for key, value in counts.items():
            if key in self._overview_metric_values:
                self._overview_metric_values[key].setText(str(value))

        self.overview_activity_list.clear()
        if not sessions:
            self.overview_activity_list.addItem("No sessions saved yet. Start in Session Review.")
        else:
            for session in sessions[:6]:
                note_count = len(observations_by_session.get(session.id, []))
                recording_label = "video linked" if session.media_path else "notes only"
                self.overview_activity_list.addItem(
                    f"{session.title}  ·  {note_count} observations  ·  {recording_label}"
                )

        self.overview_priority_list.clear()
        category_counts: dict[str, int] = {}
        for items in observations_by_session.values():
            for observation in items:
                category_counts[observation.kind.value] = category_counts.get(observation.kind.value, 0) + 1
        if not category_counts:
            self.overview_priority_list.addItem(
                "No review focus yet. Add timestamped observations in Session Review."
            )
        else:
            ordered = sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
            for category, count in ordered:
                noun = "observation" if count == 1 else "observations"
                self.overview_priority_list.addItem(
                    f"{category.title()}  ·  {count} {noun} logged"
                )
            self.overview_priority_list.addItem(
                "These are your most frequently logged categories, not an automated assessment of mistakes."
            )

    def _build_session_review(self, page_layout: QVBoxLayout) -> None:
        """Build the first functional session and timestamped-observation workflow."""
        create_panel = QFrame()
        create_panel.setObjectName("Panel")
        create_layout = QVBoxLayout(create_panel)
        create_layout.setContentsMargins(18, 16, 18, 18)
        create_layout.setSpacing(12)
        create_layout.addWidget(QLabel("Create a review session"))

        form = QFormLayout()
        self.session_title_input = QLineEdit()
        self.session_title_input.setPlaceholderText("e.g. Ranked — Oregon — Match 1")
        self.session_media_input = QLineEdit()
        self.session_media_input.setPlaceholderText("Optional local video file")
        media_row = QHBoxLayout()
        media_row.addWidget(self.session_media_input, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_session_media)
        media_row.addWidget(browse)
        media_host = QWidget()
        media_host.setLayout(media_row)
        form.addRow("Session name", self.session_title_input)
        form.addRow("Recording", media_host)
        create_layout.addLayout(form)
        create_button = QPushButton("Create session")
        create_button.clicked.connect(self._create_review_session)
        create_layout.addWidget(create_button, 0, Qt.AlignmentFlag.AlignLeft)
        page_layout.addWidget(create_panel)

        media_panel = QFrame()
        media_panel.setObjectName("Panel")
        media_layout = QVBoxLayout(media_panel)
        media_layout.setContentsMargins(18, 16, 18, 18)
        media_layout.setSpacing(10)
        media_layout.addWidget(QLabel("Recorded match playback"))
        self.review_video_widget = QVideoWidget()
        self.review_video_widget.setMinimumHeight(180)
        self.review_video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        media_layout.addWidget(self.review_video_widget, 1)
        self.review_media_player = QMediaPlayer(self)
        self.review_audio_output = QAudioOutput(self)
        self.review_media_player.setAudioOutput(self.review_audio_output)
        self.review_media_player.setVideoOutput(self.review_video_widget)
        controls = QHBoxLayout()
        self.review_play_button = QPushButton("Play")
        self.review_play_button.clicked.connect(self._toggle_review_playback)
        controls.addWidget(self.review_play_button)
        self.review_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.review_seek_slider.setRange(0, 0)
        self.review_seek_slider.sliderMoved.connect(self.review_media_player.setPosition)
        controls.addWidget(self.review_seek_slider, 1)
        self.review_media_time = QLabel("00:00 / 00:00")
        controls.addWidget(self.review_media_time)
        media_layout.addLayout(controls)
        self.review_media_status = QLabel("Select a session with a local recording to play it here.")
        self.review_media_status.setObjectName("Muted")
        self.review_media_status.setWordWrap(True)
        media_layout.addWidget(self.review_media_status)
        self.review_media_player.positionChanged.connect(self._update_media_position)
        self.review_media_player.durationChanged.connect(self._update_media_duration)
        self.review_media_player.playbackStateChanged.connect(self._update_play_button)
        self.review_media_player.errorOccurred.connect(self._on_media_error)
        page_layout.addWidget(media_panel, 1)

        review_panel = QFrame()
        review_panel.setObjectName("Panel")
        review_layout = QVBoxLayout(review_panel)
        review_layout.setContentsMargins(18, 16, 18, 18)
        review_layout.setSpacing(12)
        review_layout.addWidget(QLabel("Timestamped observations"))
        self.review_session_combo = QComboBox()
        self.review_session_combo.currentIndexChanged.connect(self._on_review_session_changed)
        review_layout.addWidget(self.review_session_combo)
        observation_form = QFormLayout()
        self.observation_timestamp = QSpinBox()
        self.observation_timestamp.setRange(0, 86_400)
        self.observation_timestamp.setSuffix(" s")
        self.observation_kind = QComboBox()
        self.observation_kind.addItem("Aim", "aim")
        self.observation_kind.addItem("Movement", "movement")
        self.observation_kind.addItem("Positioning", "positioning")
        self.observation_kind.addItem("Decision", "decision")
        self.observation_kind.addItem("Other", "other")
        self.observation_text = QLineEdit()
        self.observation_text.setPlaceholderText("What happened, and what should be reviewed?")
        timestamp_row = QHBoxLayout()
        timestamp_row.addWidget(self.observation_timestamp, 1)
        use_playback_time = QPushButton("Use playback time")
        use_playback_time.clicked.connect(self._set_observation_timestamp_from_video)
        timestamp_row.addWidget(use_playback_time)
        timestamp_host = QWidget()
        timestamp_host.setLayout(timestamp_row)
        observation_form.addRow("Timestamp", timestamp_host)
        self.observation_tags_input = QLineEdit()
        self.observation_tags_input.setPlaceholderText(
            "Coaching tags + context: overflick, underflick, target-switch, acog, close-range"
        )
        self.observation_filter_input = QLineEdit()
        self.observation_filter_input.setPlaceholderText("Filter notes by text or tag…")
        self.observation_filter_input.textChanged.connect(self._refresh_observations)
        observation_form.addRow("Category", self.observation_kind)
        observation_form.addRow("Tags", self.observation_tags_input)
        observation_form.addRow("Observation", self.observation_text)
        review_layout.addLayout(observation_form)
        quick_tag_row = QHBoxLayout()
        quick_tag_row.addWidget(QLabel("Add a coaching tag:"))
        self.coaching_tag_combo = QComboBox()
        for tag in COACHING_TAG_GUIDE:
            self.coaching_tag_combo.addItem(tag.replace("-", " ").title(), tag)
        quick_tag_row.addWidget(self.coaching_tag_combo, 1)
        self.add_coaching_tag_button = QPushButton("Add tag")
        self.add_coaching_tag_button.setObjectName("SecondaryButton")
        self.add_coaching_tag_button.clicked.connect(self._append_selected_coaching_tag)
        quick_tag_row.addWidget(self.add_coaching_tag_button)
        review_layout.addLayout(quick_tag_row)
        review_layout.addWidget(self.observation_filter_input)
        add_note = QPushButton("Add observation")
        add_note.clicked.connect(self._add_review_observation)
        review_layout.addWidget(add_note, 0, Qt.AlignmentFlag.AlignLeft)
        self.observation_list = QListWidget()
        self.observation_list.setMinimumHeight(150)
        self.observation_list.itemDoubleClicked.connect(self._seek_to_selected_observation)
        review_layout.addWidget(self.observation_list)
        self.open_annotation_button = QPushButton("Open linked annotation frame")
        self.open_annotation_button.clicked.connect(self._open_linked_annotation_frame)
        review_layout.addWidget(self.open_annotation_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.review_status = QLabel("Observations are saved locally. Demo records are excluded.")
        self.review_status.setObjectName("Muted")
        review_layout.addWidget(self.review_status)
        export_button = QPushButton("Export session summary…")
        export_button.clicked.connect(self._export_session_summary)
        review_layout.addWidget(export_button, 0, Qt.AlignmentFlag.AlignLeft)
        page_layout.addWidget(review_panel, 1)
        self._refresh_review_sessions()

    def _build_annotation_lab(self, page_layout: QVBoxLayout) -> None:
        """Build a local-only frame annotation workflow for sampled recordings."""
        source_panel = QFrame()
        source_panel.setObjectName("Panel")
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(18, 16, 18, 18)
        source_layout.setSpacing(10)
        source_heading = QLabel("Start a recording review")
        source_heading.setObjectName("PanelTitle")
        source_layout.addWidget(source_heading)
        self.annotation_drop_zone = VideoDropZone()
        self.annotation_drop_zone.video_dropped.connect(self._start_video_review)
        self.annotation_drop_zone.browse_requested.connect(self._browse_annotation_video)
        source_layout.addWidget(self.annotation_drop_zone)

        self.annotation_sampling_progress = QProgressBar()
        self.annotation_sampling_progress.setRange(0, 0)
        self.annotation_sampling_progress.setTextVisible(False)
        self.annotation_sampling_progress.setMaximumHeight(8)
        self.annotation_sampling_progress.hide()
        source_layout.addWidget(self.annotation_sampling_progress)

        self.annotation_status = QLabel(
            "Drop one saved video. SiegeSense will sample frames and open the review automatically. "
            "Frame labels remain manual."
        )
        self.annotation_status.setObjectName("Muted")
        self.annotation_status.setWordWrap(True)
        source_layout.addWidget(self.annotation_status)

        self.annotation_advanced_toggle = QPushButton("Advanced options  ▸")
        self.annotation_advanced_toggle.setObjectName("SecondaryButton")
        self.annotation_advanced_toggle.setCheckable(True)
        self.annotation_advanced_toggle.toggled.connect(self._toggle_annotation_advanced)
        source_layout.addWidget(self.annotation_advanced_toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.annotation_advanced_panel = QFrame()
        advanced_layout = QVBoxLayout(self.annotation_advanced_panel)
        advanced_layout.setContentsMargins(0, 10, 0, 0)
        advanced_layout.setSpacing(8)
        video_row = QHBoxLayout()
        self.annotation_video_input = QLineEdit()
        self.annotation_video_input.setPlaceholderText("Selected video path")
        video_row.addWidget(self.annotation_video_input, 1)
        self.annotation_browse_video_button = QPushButton("Browse…")
        self.annotation_browse_video_button.clicked.connect(self._browse_annotation_video)
        video_row.addWidget(self.annotation_browse_video_button)
        advanced_layout.addLayout(video_row)

        output_row = QHBoxLayout()
        self.annotation_output_input = QLineEdit()
        self.annotation_output_input.setPlaceholderText("Output folder (auto-selected by default)")
        output_row.addWidget(self.annotation_output_input, 1)
        browse_output = QPushButton("Output folder…")
        browse_output.clicked.connect(self._browse_annotation_output)
        output_row.addWidget(browse_output)
        advanced_layout.addLayout(output_row)

        sampling_row = QHBoxLayout()
        sampling_row.addWidget(QLabel("Sampling interval (ms)"))
        self.annotation_interval_spin = QSpinBox()
        self.annotation_interval_spin.setRange(100, 10000)
        self.annotation_interval_spin.setSingleStep(100)
        self.annotation_interval_spin.setValue(500)
        self.annotation_interval_spin.setToolTip(
            "Default is 500 ms (about 2 frames/second) to keep reviews lighter. "
            "This is for manual review, not precise event timing."
        )
        sampling_row.addWidget(self.annotation_interval_spin)
        self.annotation_sample_button = QPushButton("Sample frames manually")
        self.annotation_sample_button.clicked.connect(self._sample_annotation_video)
        sampling_row.addWidget(self.annotation_sample_button)
        sampling_row.addStretch(1)
        advanced_layout.addLayout(sampling_row)

        advanced_layout.addWidget(QLabel("Open an existing sampled-video review"))
        source_row = QHBoxLayout()
        self.annotation_manifest_input = QLineEdit()
        self.annotation_manifest_input.setPlaceholderText("Choose sampling_manifest.json")
        source_row.addWidget(self.annotation_manifest_input, 1)
        browse_manifest = QPushButton("Browse…")
        browse_manifest.clicked.connect(self._browse_annotation_manifest)
        source_row.addWidget(browse_manifest)
        advanced_layout.addLayout(source_row)
        load_manifest_button = QPushButton("Load existing review")
        load_manifest_button.clicked.connect(self._load_annotation_manifest)
        advanced_layout.addWidget(load_manifest_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.annotation_advanced_panel.setVisible(False)
        source_layout.addWidget(self.annotation_advanced_panel)
        page_layout.addWidget(source_panel)

        review_row = QHBoxLayout()
        review_row.setSpacing(14)
        frames_panel = QFrame()
        frames_panel.setObjectName("Panel")
        frames_layout = QVBoxLayout(frames_panel)
        frames_layout.setContentsMargins(14, 14, 14, 14)
        frames_layout.addWidget(QLabel("Sampled frames"))
        self.annotation_frame_list = QListWidget()
        self.annotation_frame_list.currentItemChanged.connect(self._on_annotation_frame_selected)
        frames_layout.addWidget(self.annotation_frame_list, 1)
        review_row.addWidget(frames_panel, 1)

        detail_panel = QFrame()
        detail_panel.setObjectName("Panel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(10)
        detail_layout.addWidget(QLabel("Frame preview"))
        self.annotation_frame_preview = PointPickerLabel("Load a manifest to preview sampled frames.")
        self.annotation_frame_preview.setMinimumSize(280, 180)
        self.annotation_frame_preview.setObjectName("FramePreview")
        self.annotation_frame_preview.setWordWrap(True)
        self.annotation_frame_preview.point_marked.connect(self._on_annotation_point_marked)
        detail_layout.addWidget(self.annotation_frame_preview, 1)
        point_tools = QHBoxLayout()
        self.annotation_mark_reticle_button = QPushButton("Mark reticle")
        self.annotation_mark_reticle_button.setToolTip(
            "Then click the visible center of the reticle in the full frame."
        )
        self.annotation_mark_reticle_button.clicked.connect(
            lambda: self._start_annotation_point_mark("reticle")
        )
        self.annotation_mark_target_button = QPushButton("Mark target")
        self.annotation_mark_target_button.setToolTip(
            "Then click the chosen visual reference point on the visible opponent."
        )
        self.annotation_mark_target_button.clicked.connect(
            lambda: self._start_annotation_point_mark("target")
        )
        self.annotation_clear_points_button = QPushButton("Clear points")
        self.annotation_clear_points_button.clicked.connect(self._clear_annotation_points)
        point_tools.addWidget(self.annotation_mark_reticle_button)
        point_tools.addWidget(self.annotation_mark_target_button)
        point_tools.addWidget(self.annotation_clear_points_button)
        point_tools.addStretch(1)
        detail_layout.addLayout(point_tools)
        self.annotation_point_status = QLabel(
            "Optional spatial review: mark the reticle and a visible target on this frame."
        )
        self.annotation_point_status.setObjectName("Muted")
        self.annotation_point_status.setWordWrap(True)
        detail_layout.addWidget(self.annotation_point_status)
        frame_navigation = QHBoxLayout()
        self.annotation_frame_counter = QLabel("Frame 0 of 0")
        self.annotation_frame_counter.setObjectName("Muted")
        self.annotation_previous_button = QPushButton("← Previous")
        self.annotation_previous_button.clicked.connect(
            lambda: self._step_annotation_frame(-1)
        )
        self.annotation_next_button = QPushButton("Next →")
        self.annotation_next_button.clicked.connect(
            lambda: self._step_annotation_frame(1)
        )
        frame_navigation.addWidget(self.annotation_frame_counter, 1)
        frame_navigation.addWidget(self.annotation_previous_button)
        frame_navigation.addWidget(self.annotation_next_button)
        detail_layout.addLayout(frame_navigation)
        self.annotation_frame_metadata = QLabel("No frame selected")
        self.annotation_frame_metadata.setObjectName("Muted")
        self.annotation_frame_metadata.setWordWrap(True)
        detail_layout.addWidget(self.annotation_frame_metadata)
        annotation_form = QFormLayout()
        self.annotation_label_combo = QComboBox()
        label_titles = {
            "target_transition": "Target transition",
            "crosshair_on_target": "Crosshair on target",
            "crosshair_off_target": "Crosshair off target",
            "movement_start": "Movement start",
            "movement_stop": "Movement stop",
            "ambiguous": "Ambiguous",
            "unusable_frame": "Unusable frame",
        }
        for value in sorted(ALLOWED_LABELS):
            self.annotation_label_combo.addItem(label_titles[value], value)
        self.annotation_target_track_input = QLineEdit()
        self.annotation_target_track_input.setPlaceholderText(
            "Optional · same ID for the same target in this sequence"
        )
        self.annotation_target_track_input.setToolTip(
            "Manual grouping only. Reuse this ID for the same visible target across "
            "adjacent sampled frames; change it when the target or encounter changes."
        )
        self.annotation_annotator_input = QLineEdit("Player")
        self.annotation_note_input = QLineEdit()
        self.annotation_note_input.setPlaceholderText("Optional context for this frame")
        annotation_form.addRow("Manual label", self.annotation_label_combo)
        annotation_form.addRow("Target / sequence ID", self.annotation_target_track_input)
        annotation_form.addRow("Annotator", self.annotation_annotator_input)
        annotation_form.addRow("Note", self.annotation_note_input)
        detail_layout.addLayout(annotation_form)
        save_annotation_button = QPushButton("Save annotation")
        save_annotation_button.clicked.connect(self._save_frame_annotation)
        detail_layout.addWidget(save_annotation_button, 0, Qt.AlignmentFlag.AlignLeft)
        review_row.addWidget(detail_panel, 2)
        page_layout.addLayout(review_row, 2)

        history_panel = QFrame()
        history_panel.setObjectName("Panel")
        history_layout = QVBoxLayout(history_panel)
        history_layout.setContentsMargins(18, 14, 18, 14)
        history_layout.addWidget(QLabel("Saved annotations"))
        self.annotation_summary_label = QLabel(
            "Aim summary appears after you save manual labels. It describes selected frames, not aim accuracy."
        )
        self.annotation_summary_label.setObjectName("Muted")
        self.annotation_summary_label.setWordWrap(True)
        history_layout.addWidget(self.annotation_summary_label)
        export_report_button = QPushButton("Export local evaluation report…")
        export_report_button.clicked.connect(self._export_annotation_report)
        history_layout.addWidget(export_report_button, 0, Qt.AlignmentFlag.AlignLeft)
        spatial_report_button = QPushButton("Export manual spatial-offset report…")
        spatial_report_button.setToolTip(
            "Export offsets calculated only from manually marked reticle and target points."
        )
        spatial_report_button.clicked.connect(self._export_spatial_report)
        history_layout.addWidget(spatial_report_button, 0, Qt.AlignmentFlag.AlignLeft)
        transition_report_button = QPushButton("Export manual aim-transition report…")
        transition_report_button.setToolTip(
            "Count target-relative offset sign changes across manually tracked adjacent frames. "
            "This does not diagnose overshoot or change settings."
        )
        transition_report_button.clicked.connect(self._export_aim_transition_report)
        history_layout.addWidget(transition_report_button, 0, Qt.AlignmentFlag.AlignLeft)
        motion_report_button = QPushButton("Analyze screen-space motion…")
        motion_report_button.setToolTip(
            "Estimate visible feature movement between adjacent sampled frames; this is not mouse input or an aim score."
        )
        motion_report_button.clicked.connect(self._analyze_annotation_motion)
        history_layout.addWidget(motion_report_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.annotation_history_list = QListWidget()
        self.annotation_history_list.setMaximumHeight(150)
        self.annotation_history_list.currentItemChanged.connect(self._on_annotation_history_selected)
        history_layout.addWidget(self.annotation_history_list)
        edit_annotation_button = QPushButton("Update selected annotation")
        edit_annotation_button.clicked.connect(self._update_selected_annotation)
        history_layout.addWidget(edit_annotation_button, 0, Qt.AlignmentFlag.AlignLeft)
        delete_annotation_button = QPushButton("Delete selected annotation")
        delete_annotation_button.clicked.connect(self._delete_selected_annotation)
        history_layout.addWidget(delete_annotation_button, 0, Qt.AlignmentFlag.AlignLeft)
        history_layout.addWidget(QLabel("Link selected annotation to a Session Review"))
        self.annotation_session_combo = QComboBox()
        self.annotation_session_combo.setPlaceholderText("Choose a real review session")
        history_layout.addWidget(self.annotation_session_combo)
        link_annotation_button = QPushButton("Add annotation to selected session")
        link_annotation_button.clicked.connect(self._link_annotation_to_session)
        history_layout.addWidget(link_annotation_button, 0, Qt.AlignmentFlag.AlignLeft)
        page_layout.addWidget(history_panel)
        self._annotation_store: AnnotationStore | None = None
        self._annotation_manifest: dict | None = None
        self._annotation_manifest_path: Path | None = None
        self._refresh_annotation_sessions()

    def _analyze_annotation_motion(self) -> None:
        """Estimate visual feature motion locally and export a transparent JSON report."""
        manifest_path = self._annotation_manifest_path
        if manifest_path is None or not manifest_path.is_file():
            self.annotation_status.setText("Load a valid sampling manifest before analyzing motion.")
            return
        target, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export screen-space motion report",
            "screen-motion-report.json",
            "JSON report (*.json)",
        )
        if not target:
            return
        if not Path(target).suffix:
            target = f"{target}.json"
        try:
            report = analyze_manifest_motion(manifest_path)
            output = write_motion_report(report, target)
        except Exception as error:
            # OpenCV can raise its own exception type for damaged or unsupported images.
            self.annotation_status.setText(f"Screen-space motion analysis failed: {error}")
            return
        pair_summary = (
            f"Analyzed {report.analyzed_pair_count}/{report.eligible_pair_count} eligible pairs; "
            f"subsampled: {report.subsampled_pair_count}; "
            f"unusable: {report.unusable_pair_count}; "
            f"timestamp-gap pairs excluded: {report.skipped_gap_pair_count}."
        )
        if report.median_motion_px_per_sample is None:
            motion_summary = f"No usable adjacent frame pairs were available. {pair_summary}"
        else:
            motion_summary = (
                f"Median visible-feature motion: {report.median_motion_px_per_sample:.2f} "
                f"resized px/sample; 90th percentile: {report.p90_motion_px_per_sample:.2f}. "
                f"Median per-pair coherent-feature ratio: "
                f"{_median_coherent_ratio(report.pairs):.0%}. {pair_summary}"
            )
        self.annotation_status.setText(
            f"Motion report saved to {output}. {motion_summary} "
            "This is screen-space visual motion, not mouse input, aim accuracy, or a skill score."
        )

    def _refresh_annotation_sessions(self) -> None:
        if not hasattr(self, "annotation_session_combo"):
            return
        current_id = self.annotation_session_combo.currentData()
        self.annotation_session_combo.blockSignals(True)
        self.annotation_session_combo.clear()
        try:
            sessions = self.session_service.list_sessions() if self.session_service else []
        except (OSError, RuntimeError, sqlite3.Error) as error:
            self.annotation_status.setText(f"Could not load review sessions: {error}")
            sessions = []
        for session in sessions:
            self.annotation_session_combo.addItem(session.title, session.id)
        index = self.annotation_session_combo.findData(current_id)
        if index >= 0:
            self.annotation_session_combo.setCurrentIndex(index)
        elif self.annotation_session_combo.count() > 0:
            self.annotation_session_combo.setCurrentIndex(0)
        self.annotation_session_combo.blockSignals(False)
        if not sessions:
            self.annotation_session_combo.setPlaceholderText("Create a session in Session Review first")

    def _link_annotation_to_session(self) -> None:
        if self._annotation_store is None:
            self.annotation_status.setText("Load a valid sampling manifest first.")
            return
        history_item = self.annotation_history_list.currentItem()
        if history_item is None:
            self.annotation_status.setText("Select a saved annotation to link.")
            return
        session_id = self.annotation_session_combo.currentData()
        if not session_id or self.session_service is None:
            self.annotation_status.setText("Create a real session in Session Review first.")
            return
        annotation_id = history_item.data(Qt.ItemDataRole.UserRole)
        annotation = next(
            (entry for entry in self._annotation_store.annotations if entry.annotation_id == annotation_id),
            None,
        )
        if annotation is None:
            self.annotation_status.setText("Selected annotation no longer exists.")
            self._refresh_annotation_history()
            return
        selected_session = next(
            (session for session in self.session_service.list_sessions() if session.id == session_id),
            None,
        )
        if selected_session is None:
            self.annotation_status.setText("Selected session is no longer available. Refresh the session list.")
            self._refresh_annotation_sessions()
            return
        source_path = (
            self._annotation_manifest.get("source_path")
            if self._annotation_manifest is not None
            else None
        )
        manifest_sha256 = (
            self._annotation_manifest.get("source_sha256")
            if self._annotation_manifest is not None
            else None
        )
        if selected_session.media_sha256 and manifest_sha256:
            if selected_session.media_sha256 != manifest_sha256:
                self.annotation_status.setText(
                    "The recording fingerprint does not match this session. "
                    "Choose a session linked to the exact same video file."
                )
                return
        elif selected_session.media_path and source_path:
            # Until both sides have a fingerprint, retain the conservative path check.
            selected_media = Path(selected_session.media_path).expanduser().resolve()
            annotation_media = Path(source_path).expanduser().resolve()
            if selected_media != annotation_media:
                self.annotation_status.setText(
                    "The sampled clip does not match this session's recording. "
                    "Choose a session created from the same source video."
                )
                return
        annotation_tag = f"annotation-id:{annotation.annotation_id}"
        try:
            existing_observations = self.session_service.list_observations(session_id)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            self.annotation_status.setText(f"Could not check existing session observations: {error}")
            return
        if any(annotation_tag in item.tags for item in existing_observations):
            self.annotation_status.setText("This annotation is already linked to the selected session.")
            return
        label = annotation.label.replace("_", " ")
        note = f" — {annotation.note}" if annotation.note else ""
        text = f"Clip annotation: {label}{note} [frame: {annotation.frame_filename}]"
        kind = (
            ObservationKind.MOVEMENT
            if annotation.label in {"movement_start", "movement_stop"}
            else ObservationKind.AIM
        )
        try:
            self.session_service.add_observation(
                session_id,
                annotation.timestamp_ms,
                text,
                kind=kind,
                tags=("clip-annotation", annotation.label, annotation_tag),
            )
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            self.annotation_status.setText(f"Could not link annotation: {error}")
            return
        self.annotation_status.setText(
            f"Added {label} at {annotation.timestamp_ms / 1000:.2f}s to Session Review."
        )
        self._refresh_review_sessions(select_id=session_id)
        self.show_page("Session Review")

    def _toggle_annotation_advanced(self, expanded: bool) -> None:
        self.annotation_advanced_panel.setVisible(expanded)
        self.annotation_advanced_toggle.setText(
            "Advanced options  ▾" if expanded else "Advanced options  ▸"
        )

    @staticmethod
    def _new_review_output_folder(source: Path) -> Path:
        base = source.parent / f"{source.stem}_siegesense_review"
        candidate = base
        suffix = 2
        while candidate.exists():
            candidate = source.parent / f"{source.stem}_siegesense_review_{suffix}"
            suffix += 1
        return candidate

    def _set_video_review_busy(self, busy: bool) -> None:
        if hasattr(self, "annotation_sampling_progress"):
            self.annotation_sampling_progress.setVisible(busy)
        for name in ("overview_video_drop_zone", "annotation_drop_zone"):
            zone = getattr(self, name, None)
            if zone is not None:
                zone.setEnabled(not busy)
        button = getattr(self, "annotation_sample_button", None)
        if button is not None:
            button.setEnabled(not busy)

    def _start_video_review(self, source_path: str) -> None:
        """Drop/browse flow: sample a local video asynchronously and open its frames."""
        current_worker = self._sampling_worker
        if current_worker is not None and current_worker.isRunning():
            self.annotation_status.setText("A review is already being prepared. Please let it finish first.")
            return

        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            self.annotation_status.setText("That video file could not be found. Choose it again.")
            return
        if source.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
            self.annotation_status.setText("Choose a video file such as MP4, MKV, MOV, AVI, or WEBM.")
            return

        output = self._new_review_output_folder(source)
        self.annotation_video_input.setText(str(source))
        self.annotation_output_input.setText(str(output))
        interval = self.annotation_interval_spin.value()
        message = (
            f"Preparing review for {source.name}. Sampling at {interval} ms intervals; "
            "large videos may take a little while. The app remains responsive."
        )
        self.annotation_status.setText(message)
        if hasattr(self, "overview_review_status"):
            self.overview_review_status.setText(message)
        self._set_video_review_busy(True)
        worker = VideoSamplingWorker(str(source), str(output), interval)
        worker.succeeded.connect(self._on_video_review_sampled)
        worker.failed.connect(self._on_video_review_failed)
        worker.finished.connect(self._video_review_worker_finished)
        self._sampling_worker = worker
        worker.start()

    def _on_video_review_sampled(self, report, output_dir: str) -> None:
        manifest_path = Path(output_dir) / "sampling_manifest.json"
        self.annotation_manifest_input.setText(str(manifest_path))
        self._load_annotation_manifest()
        if self._annotation_store is None:
            return
        self.show_page("Clip Annotation")
        message = (
            f"Review ready — {len(report.frames)} frames loaded. Start with the selected frame, "
            "then use Next to move through the recording. Labels are manual; no video was uploaded."
        )
        self.annotation_status.setText(message)
        if hasattr(self, "overview_review_status"):
            self.overview_review_status.setText(message)
        self.annotation_frame_preview.setFocus()

    def _on_video_review_failed(self, error: str) -> None:
        message = (
            f"Could not prepare that review: {error} "
            "Try another video file. The original recording was not changed."
        )
        self.annotation_status.setText(message)
        if hasattr(self, "overview_review_status"):
            self.overview_review_status.setText(message)

    def _video_review_worker_finished(self) -> None:
        worker = self._sampling_worker
        if worker is not None:
            self._sampling_worker = None
            worker.deleteLater()
        self._set_video_review_busy(False)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt event name
        worker = self._sampling_worker
        if worker is not None and worker.isRunning():
            self.annotation_status.setText("Finishing the current local sampling task before closing…")
            worker.wait()
        super().closeEvent(event)

    def _browse_annotation_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a video to review",
            "",
            "Video files (*.mp4 *.mkv *.mov *.avi *.webm *.m4v);;All files (*)",
        )
        if path:
            self._start_video_review(path)

    def _browse_annotation_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.annotation_output_input.setText(path)

    def _sample_annotation_video(self) -> None:
        source = self.annotation_video_input.text().strip()
        output = self.annotation_output_input.text().strip()
        if not source:
            self.annotation_status.setText("Choose a gameplay recording first.")
            return
        if not output:
            self.annotation_status.setText("Choose an output folder for sampled frames.")
            return
        try:
            report = sample_video_frames(
                source,
                output,
                interval_ms=self.annotation_interval_spin.value(),
            )
        except (OSError, ValueError, RuntimeError) as error:
            self.annotation_status.setText(f"Frame sampling failed: {error}")
            return
        manifest_path = Path(output).expanduser().resolve() / "sampling_manifest.json"
        self.annotation_manifest_input.setText(str(manifest_path))
        self._load_annotation_manifest()
        if self._annotation_store is not None:
            self.annotation_status.setText(
                f"Sampled {len(report.frames)} frame(s) at {report.interval_ms} ms intervals. "
                "Frames remain local. Labels are manual; this is not automatic aim detection."
            )

    def _browse_annotation_manifest(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select sampling manifest", "", "Sampling manifest (sampling_manifest.json);;JSON files (*.json)"
        )
        if path:
            self.annotation_manifest_input.setText(path)
            self._load_annotation_manifest()

    def _load_annotation_manifest(self) -> None:
        raw_path = self.annotation_manifest_input.text().strip()
        if not raw_path:
            self.annotation_status.setText("Choose a sampling_manifest.json file first.")
            return
        manifest_path = Path(raw_path).expanduser().resolve()
        try:
            manifest = load_manifest(manifest_path)
            frames = manifest["frames"]
            if not frames:
                raise ValueError("The selected manifest contains no sampled frames.")
            dataset_path = manifest_path.parent / "annotations.json"
            store = AnnotationStore(manifest_path, dataset_path)
            for frame in frames:
                filename = Path(frame["filename"])
                if filename.name != frame["filename"] or filename.is_absolute():
                    raise ValueError("Manifest contains a frame path outside the sampling folder.")
            self._annotation_manifest = manifest
            self._annotation_manifest_path = manifest_path
            self._annotation_store = store
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
            self._annotation_manifest = None
            self._annotation_store = None
            self._annotation_manifest_path = None
            self.annotation_target_track_input.clear()
            self.annotation_frame_list.clear()
            self.annotation_history_list.clear()
            self._refresh_annotation_summary()
            self.annotation_frame_preview.set_image_message("Could not load this manifest.")
            self.annotation_status.setText(f"Manifest not loaded: {error}")
            return

        self.annotation_frame_list.clear()
        # Prevent a target ID from a previous recording leaking into a new dataset.
        self.annotation_target_track_input.clear()
        self.annotation_frame_counter.setText(f"Frame 0 of {len(frames)}")
        self.annotation_previous_button.setEnabled(False)
        self.annotation_next_button.setEnabled(len(frames) > 1)
        for frame in frames:
            timestamp = frame["timestamp_ms"]
            filename = frame["filename"]
            item = QListWidgetItem(f"{timestamp / 1000:.2f}s  ·  {filename}")
            item.setData(Qt.ItemDataRole.UserRole, (timestamp, filename))
            self.annotation_frame_list.addItem(item)
        self._refresh_annotation_history()
        self._refresh_annotation_summary()
        self.annotation_status.setText(
            f"Loaded {len(frames)} frame(s). Labels are saved locally in {dataset_path.name}."
        )
        self.annotation_frame_list.setCurrentRow(0)

    def _step_annotation_frame(self, delta: int) -> None:
        count = self.annotation_frame_list.count()
        if count == 0:
            return
        next_row = max(0, min(count - 1, self.annotation_frame_list.currentRow() + delta))
        self.annotation_frame_list.setCurrentRow(next_row)

    def _on_annotation_frame_selected(self, item: QListWidgetItem | None, _previous=None) -> None:
        if item is None or self._annotation_manifest_path is None:
            return
        row = self.annotation_frame_list.row(item)
        count = self.annotation_frame_list.count()
        self.annotation_frame_counter.setText(f"Frame {row + 1} of {count}")
        self.annotation_previous_button.setEnabled(row > 0)
        self.annotation_next_button.setEnabled(row < count - 1)
        timestamp_ms, filename = item.data(Qt.ItemDataRole.UserRole)
        frame_path = self._annotation_manifest_path.parent / filename
        self.annotation_frame_metadata.setText(
            f"Timestamp: {timestamp_ms} ms  ·  File: {filename}"
        )
        if not frame_path.is_file():
            self.annotation_frame_preview.set_image_message(
                "Frame image is missing. Re-run sampling or check the output folder."
            )
            self.annotation_frame_preview.clear_points()
            self._update_annotation_point_status()
            return
        pixmap = QPixmap(str(frame_path))
        if pixmap.isNull():
            self.annotation_frame_preview.set_image_message("This image could not be decoded.")
            self.annotation_frame_preview.clear_points()
            self._update_annotation_point_status()
            return
        self.annotation_frame_preview.set_source_pixmap(pixmap)
        self._restore_annotation_frame_points(timestamp_ms, filename)

    def resizeEvent(self, event) -> None:
        """Keep the selected frame preview fitted when the window is resized."""
        super().resizeEvent(event)
        item = getattr(self, "annotation_frame_list", None)
        if item is not None and item.currentItem() is not None:
            self._on_annotation_frame_selected(item.currentItem())

    def _save_frame_annotation(self) -> None:
        if self._annotation_store is None:
            self.annotation_status.setText("Load a valid sampling manifest before annotating frames.")
            return
        item = self.annotation_frame_list.currentItem()
        if item is None:
            self.annotation_status.setText("Select a sampled frame first.")
            return
        timestamp_ms, filename = item.data(Qt.ItemDataRole.UserRole)
        try:
            annotation = self._annotation_store.add(
                timestamp_ms,
                filename,
                self.annotation_label_combo.currentData(),
                annotator=self.annotation_annotator_input.text(),
                note=self.annotation_note_input.text(),
                target_track_id=self.annotation_target_track_input.text(),
                **self.annotation_frame_preview.point_coordinates(),
            )
        except (OSError, ValueError, RuntimeError) as error:
            self.annotation_status.setText(f"Annotation not saved: {error}")
            return
        self.annotation_note_input.clear()
        self._refresh_annotation_history()
        self._refresh_annotation_summary()
        self.annotation_status.setText(
            f"Saved {annotation.label.replace('_', ' ')} at {annotation.timestamp_ms} ms."
        )

    def _export_spatial_report(self) -> None:
        """Export the current dataset's manually marked reticle/target offsets."""
        store = self._annotation_store
        if store is None or not store.dataset_path.is_file():
            self.annotation_status.setText(
                "Load and save a local annotation dataset before exporting spatial offsets."
            )
            return
        default_path = store.dataset_path.parent / "spatial-offset-report.json"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export manual spatial-offset report",
            str(default_path),
            "JSON report (*.json)",
        )
        if not output_path:
            return
        if not Path(output_path).suffix:
            output_path = f"{output_path}.json"
        try:
            written = write_spatial_report(store.dataset_path, output_path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.annotation_status.setText(f"Spatial report export failed: {error}")
            return
        self.annotation_status.setText(
            f"Manual spatial-offset report exported to {written}. "
            "Only manually marked point pairs are included; this is not aim accuracy."
        )

    def _export_aim_transition_report(self) -> None:
        """Export sign changes from manually marked points on identified targets."""
        store = self._annotation_store
        if store is None or not store.dataset_path.is_file():
            self.annotation_status.setText(
                "Load and save a local annotation dataset before exporting aim transitions."
            )
            return
        default_path = store.dataset_path.parent / "aim-transition-report.json"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export manual aim-transition report",
            str(default_path),
            "JSON report (*.json)",
        )
        if not output_path:
            return
        if not Path(output_path).suffix:
            output_path = f"{output_path}.json"
        try:
            written = write_aim_transition_report(store.dataset_path, output_path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.annotation_status.setText(f"Aim-transition report export failed: {error}")
            return
        self.annotation_status.setText(
            f"Manual aim-transition report exported to {written}. It counts target-relative "
            "offset sign changes only; it does not diagnose overshoot or recommend sensitivity."
        )

    def _export_annotation_report(self) -> None:
        """Export a local coverage report for the currently loaded annotation dataset."""
        store = self._annotation_store
        if store is None or not store.dataset_path.is_file():
            self.annotation_status.setText(
                "Save at least one annotation before exporting an evaluation report."
            )
            return
        default_path = store.dataset_path.parent / "evaluation-report.json"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export local evaluation report",
            str(default_path),
            "JSON report (*.json)",
        )
        if not output_path:
            return
        try:
            written = write_evaluation_report(
                output_path,
                [(store.dataset_path.stem, store.dataset_path)],
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.annotation_status.setText(f"Report export failed: {error}")
            return
        self.annotation_status.setText(
            f"Local evaluation report exported to {written}. "
            "It summarizes human labels and does not measure model performance."
        )

    def _refresh_annotation_summary(self) -> None:
        """Show a cautious summary of manually labelled aim frames."""
        store = self._annotation_store
        if store is None or not store.dataset_path.is_file():
            self.annotation_summary_label.setText(
                "No saved labels yet. This summary describes selected frames, not aim accuracy."
            )
            return
        try:
            summary = summarize_aim_frames(store.dataset_path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.annotation_summary_label.setText(f"Aim summary unavailable: {error}")
            return
        share = summary.on_target_share_of_labelled_frames
        share_text = "n/a" if share is None else f"{share:.0%}"
        try:
            sequence = summarize_annotated_sequences(store.dataset_path)
        except (OSError, ValueError, KeyError, TypeError):
            sequence = None
        if sequence is None or sequence.sampling_interval_ms is None:
            sequence_text = "sampled run timing unavailable"
        else:
            longest = sequence.off_target_runs.longest_observed_span_ms
            longest_text = "n/a" if longest is None else f"{longest} ms"
            sequence_text = (
                f"consecutive off-target runs: {sequence.off_target_runs.run_count}, "
                f"longest observed sampled span: {longest_text}, "
                f"adjacent off→on labels: {sequence.off_to_on_transitions}, "
                f"adjacent on→off labels: {sequence.on_to_off_transitions}"
            )
        try:
            spatial = summarize_spatial_error(store.dataset_path)
        except (OSError, ValueError, KeyError, TypeError):
            spatial = None
        if spatial is None or spatial.annotated_point_count == 0:
            spatial_text = "manual reticle/target point pairs: 0"
        else:
            spatial_text = (
                f"manual reticle/target point pairs: {spatial.annotated_point_count}, "
                f"median target-minus-reticle offset: "
                f"{spatial.median_horizontal_offset_pct:+.2f}% frame width horizontally, "
                f"{spatial.median_vertical_offset_pct:+.2f}% frame height vertically, "
                f"{spatial.median_distance_pct_frame_diagonal:.2f}% frame diagonal"
            )
        try:
            transition = summarize_aim_transitions(store.dataset_path)
        except (OSError, ValueError, KeyError, TypeError):
            transition = None
        if transition is None:
            transition_text = "manual target-relative transition counts unavailable"
        elif transition.sampling_interval_ms is None:
            transition_text = (
                "manual target-relative transition counts unavailable without a known sample interval"
            )
        else:
            transition_text = (
                f"manual target-relative offset sign changes: horizontal "
                f"{transition.horizontal_sign_change_count}, vertical "
                f"{transition.vertical_sign_change_count}; eligible same-target pairs: "
                f"{transition.eligible_adjacent_pair_count}"
            )
        self.annotation_summary_label.setText(
            f"Manual frame labels · on target: {summary.crosshair_on_target_frames} · "
            f"off target: {summary.crosshair_off_target_frames} · "
            f"selected-frame on-target share: {share_text} · "
            f"transitions: {summary.target_transition_frames} · "
            f"ambiguous: {summary.ambiguous_frames} · unusable: {summary.unusable_frames}. "
            f"{sequence_text}. {spatial_text}. {transition_text}. "
            "Observed sampled spans are not precise event durations. Spatial offsets use manually "
            "marked points and are geometric measurements, not hit accuracy. Descriptive only; "
            "not aim accuracy or representative gameplay performance."
        )

    def _refresh_annotation_history(self) -> None:
        self.annotation_history_list.clear()
        if self._annotation_store is None:
            return
        for annotation in self._annotation_store.annotations:
            note = f" — {annotation.note}" if annotation.note else ""
            track = f" · target {annotation.target_track_id}" if annotation.target_track_id else ""
            item = QListWidgetItem(
                f"{annotation.timestamp_ms / 1000:.2f}s  ·  "
                f"{annotation.label.replace('_', ' ')}{track}{note}"
            )
            item.setData(Qt.ItemDataRole.UserRole, annotation.annotation_id)
            self.annotation_history_list.addItem(item)

    def _on_annotation_history_selected(self, item: QListWidgetItem | None, _previous=None) -> None:
        if item is None or self._annotation_store is None:
            return
        annotation_id = item.data(Qt.ItemDataRole.UserRole)
        annotation = next(
            (entry for entry in self._annotation_store.annotations if entry.annotation_id == annotation_id),
            None,
        )
        if annotation is None:
            return
        self.annotation_annotator_input.setText(annotation.annotator)
        self.annotation_target_track_input.setText(annotation.target_track_id or "")
        self.annotation_note_input.setText(annotation.note)
        label_index = self.annotation_label_combo.findData(annotation.label)
        if label_index >= 0:
            self.annotation_label_combo.setCurrentIndex(label_index)
        for index in range(self.annotation_frame_list.count()):
            frame_item = self.annotation_frame_list.item(index)
            if frame_item.data(Qt.ItemDataRole.UserRole) == (
                annotation.timestamp_ms,
                annotation.frame_filename,
            ):
                self.annotation_frame_list.setCurrentRow(index)
                break
        self._set_annotation_spatial_points(annotation)
        self.annotation_status.setText(
            f"Editing label for {annotation.timestamp_ms / 1000:.2f}s. "
            "Change the fields above and select Update selected annotation."
        )

    def _start_annotation_point_mark(self, mode: str) -> None:
        if self._annotation_store is None or self.annotation_frame_list.currentItem() is None:
            self.annotation_status.setText("Load a manifest and select a readable frame first.")
            return
        try:
            self.annotation_frame_preview.set_marking_mode(mode)
        except ValueError as error:
            self.annotation_status.setText(str(error))
            return
        point_name = "reticle center" if mode == "reticle" else "chosen visible target reference point"
        self.annotation_status.setText(
            f"Click the {point_name} inside the image. Letterboxed margins are not part of the frame."
        )

    def _on_annotation_point_marked(self, mode: str, x: float, y: float) -> None:
        point_name = "Reticle" if mode == "reticle" else "Target"
        self._update_annotation_point_status()
        self.annotation_status.setText(
            f"{point_name} point marked at x={x:.1%}, y={y:.1%} of the full source frame. "
            "Save a new annotation or update the selected one to persist the mark."
        )

    def _clear_annotation_points(self) -> None:
        self.annotation_frame_preview.clear_points()
        self._update_annotation_point_status()
        self.annotation_status.setText(
            "Point marks cleared from the current edit. Save or update the annotation to persist the change."
        )

    def _set_annotation_spatial_points(self, annotation) -> None:
        reticle = (
            (annotation.reticle_x, annotation.reticle_y)
            if annotation.reticle_x is not None and annotation.reticle_y is not None
            else None
        )
        target = (
            (annotation.target_x, annotation.target_y)
            if annotation.target_x is not None and annotation.target_y is not None
            else None
        )
        self.annotation_frame_preview.set_points(reticle, target)
        self._update_annotation_point_status()

    def _restore_annotation_frame_points(self, timestamp_ms: int, filename: str) -> None:
        store = self._annotation_store
        if store is None:
            self.annotation_frame_preview.clear_points()
            self._update_annotation_point_status()
            return
        spatial_annotations = [
            annotation for annotation in store.annotations
            if annotation.timestamp_ms == timestamp_ms
            and annotation.frame_filename == filename
            and (
                annotation.reticle_x is not None
                or annotation.target_x is not None
            )
        ]
        if spatial_annotations:
            self._set_annotation_spatial_points(spatial_annotations[-1])
        else:
            self.annotation_frame_preview.set_points(None, None)
            self._update_annotation_point_status()

    def _update_annotation_point_status(self) -> None:
        coordinates = self.annotation_frame_preview.point_coordinates()
        reticle = (
            "not marked" if coordinates["reticle_x"] is None
            else f"x={coordinates['reticle_x']:.1%}, y={coordinates['reticle_y']:.1%}"
        )
        target = (
            "not marked" if coordinates["target_x"] is None
            else f"x={coordinates['target_x']:.1%}, y={coordinates['target_y']:.1%}"
        )
        self.annotation_point_status.setText(f"Reticle: {reticle}  ·  Target: {target}")

    def _update_selected_annotation(self) -> None:
        if self._annotation_store is None:
            self.annotation_status.setText("Load a valid sampling manifest first.")
            return
        item = self.annotation_history_list.currentItem()
        if item is None:
            self.annotation_status.setText("Select a saved annotation to update.")
            return
        annotation_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            updated = self._annotation_store.update(
                annotation_id,
                label=self.annotation_label_combo.currentData(),
                annotator=self.annotation_annotator_input.text(),
                note=self.annotation_note_input.text(),
                **self.annotation_frame_preview.point_coordinates(),
            )
        except (OSError, ValueError, RuntimeError) as error:
            self.annotation_status.setText(f"Annotation not updated: {error}")
            return
        self._refresh_annotation_history()
        self._refresh_annotation_summary()
        for index in range(self.annotation_history_list.count()):
            history_item = self.annotation_history_list.item(index)
            if history_item.data(Qt.ItemDataRole.UserRole) == updated.annotation_id:
                self.annotation_history_list.setCurrentRow(index)
                break
        self.annotation_status.setText(
            f"Updated annotation at {updated.timestamp_ms / 1000:.2f}s."
        )

    def _delete_selected_annotation(self) -> None:
        if self._annotation_store is None:
            self.annotation_status.setText("Load a valid sampling manifest first.")
            return
        item = self.annotation_history_list.currentItem()
        if item is None:
            self.annotation_status.setText("Select a saved annotation to delete.")
            return
        annotation_id = item.data(Qt.ItemDataRole.UserRole)
        if not self._annotation_store.remove(annotation_id):
            self.annotation_status.setText("That annotation no longer exists.")
            self._refresh_annotation_history()
            return
        self._refresh_annotation_history()
        self._refresh_annotation_summary()
        self.annotation_status.setText("Annotation deleted from local storage.")

    def _build_settings_lab(self, page_layout: QVBoxLayout) -> None:
        """Build a settings snapshot and one-variable experiment workflow."""
        snapshot_panel = QFrame()
        snapshot_panel.setObjectName("Panel")
        layout = QVBoxLayout(snapshot_panel)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Record your current in-game settings"))
        form = QFormLayout()
        self.settings_label_input = QLineEdit("Baseline")
        form.addRow("Snapshot name", self.settings_label_input)
        self.settings_spinboxes: dict[str, QSpinBox | QDoubleSpinBox] = {}
        for key, label, minimum, maximum, value in (
            ("horizontal", "Horizontal sensitivity", 1, 100, 6),
            ("vertical", "Vertical sensitivity", 1, 100, 6),
            ("ads_1x", "1.0× ADS", 1, 200, 40),
            ("ads_2_5x", "2.5× ADS", 1, 200, 44),
            ("ads_3_5x", "3.5× ADS", 1, 200, 40),
            ("ads_8x", "8.0× ADS", 1, 200, 36),
            ("ads_global", "Global ADS sensitivity (INI)", 1, 200, 50),
        ):
            control = QSpinBox()
            control.setRange(minimum, maximum)
            control.setValue(value)
            self.settings_spinboxes[key] = control
            form.addRow(label, control)

        dpi_control = QSpinBox()
        dpi_control.setRange(100, 25600)
        dpi_control.setSingleStep(100)
        dpi_control.setValue(800)
        dpi_control.setToolTip(
            "Record the DPI profile actually active in your mouse software. SiegeSense does not change it."
        )
        self.settings_spinboxes["mouse_dpi"] = dpi_control
        form.addRow("Mouse DPI", dpi_control)

        multiplier_control = QDoubleSpinBox()
        multiplier_control.setDecimals(6)
        multiplier_control.setRange(0.000001, 1.0)
        multiplier_control.setSingleStep(0.001)
        multiplier_control.setValue(0.020000)
        multiplier_control.setToolTip(
            "Enter MouseSensitivityMultiplierUnit from the active Siege configuration."
        )
        self.settings_spinboxes["sensitivity_multiplier"] = multiplier_control
        form.addRow("Mouse sensitivity multiplier", multiplier_control)

        ads_multiplier_control = QDoubleSpinBox()
        ads_multiplier_control.setDecimals(6)
        ads_multiplier_control.setRange(0.000001, 1.0)
        ads_multiplier_control.setSingleStep(0.001)
        ads_multiplier_control.setValue(0.020000)
        ads_multiplier_control.setToolTip(
            "Enter ADSMouseMultiplierUnit from the active Siege configuration."
        )
        self.settings_spinboxes["ads_sensitivity_multiplier"] = ads_multiplier_control
        form.addRow("ADS sensitivity multiplier", ads_multiplier_control)
        layout.addLayout(form)

        import_row = QHBoxLayout()
        self.import_game_settings_button = QPushButton("Import GameSettings.ini…")
        self.import_game_settings_button.setObjectName("SecondaryButton")
        self.import_game_settings_button.setToolTip(
            "Read recognized settings from one file you select. The importer never writes the game file."
        )
        self.import_game_settings_button.clicked.connect(self._import_game_settings)
        import_row.addWidget(self.import_game_settings_button)
        import_row.addStretch(1)
        layout.addLayout(import_row)
        self.settings_import_status = QLabel(
            "Optional: import the active GameSettings.ini. Verify every field before saving a baseline."
        )
        self.settings_import_status.setObjectName("Muted")
        self.settings_import_status.setWordWrap(True)
        layout.addWidget(self.settings_import_status)

        save_button = QPushButton("Save settings snapshot")
        save_button.clicked.connect(self._save_settings_snapshot)
        layout.addWidget(save_button, 0, Qt.AlignmentFlag.AlignLeft)
        page_layout.addWidget(snapshot_panel)

        experiment_panel = QFrame()
        experiment_panel.setObjectName("Panel")
        experiment_layout = QVBoxLayout(experiment_panel)
        experiment_layout.setContentsMargins(18, 16, 18, 18)
        experiment_layout.setSpacing(12)
        experiment_layout.addWidget(QLabel("Compare settings deliberately"))
        experiment_form = QFormLayout()
        self.experiment_title_input = QLineEdit("Single-variable test")
        self.experiment_hypothesis_input = QLineEdit("A small change may reduce overshooting")
        self.experiment_variable_input = QLineEdit("horizontal sensitivity")
        self.experiment_baseline_combo = QComboBox()
        self.experiment_test_combo = QComboBox()
        experiment_form.addRow("Experiment", self.experiment_title_input)
        experiment_form.addRow("Hypothesis", self.experiment_hypothesis_input)
        experiment_form.addRow("Variable changed", self.experiment_variable_input)
        experiment_form.addRow("Baseline snapshot", self.experiment_baseline_combo)
        experiment_form.addRow("Test snapshot", self.experiment_test_combo)
        experiment_layout.addLayout(experiment_form)
        self.settings_comparison_label = QLabel(
            "Choose baseline and test snapshots to inspect the exact setting differences."
        )
        self.settings_comparison_label.setWordWrap(True)
        self.settings_comparison_label.setObjectName("Muted")
        compare_button = QPushButton("Compare selected snapshots")
        compare_button.clicked.connect(self._refresh_snapshot_comparison)
        self.experiment_baseline_combo.currentIndexChanged.connect(self._refresh_snapshot_comparison)
        self.experiment_test_combo.currentIndexChanged.connect(self._refresh_snapshot_comparison)
        experiment_layout.addWidget(compare_button, 0, Qt.AlignmentFlag.AlignLeft)
        experiment_layout.addWidget(self.settings_comparison_label)
        create_experiment = QPushButton("Record experiment")
        create_experiment.clicked.connect(self._create_settings_experiment)
        experiment_layout.addWidget(create_experiment, 0, Qt.AlignmentFlag.AlignLeft)
        self.settings_experiment_list = QListWidget()
        self.settings_experiment_list.setMinimumHeight(100)
        self.settings_experiment_list.currentItemChanged.connect(self._load_selected_experiment)
        experiment_layout.addWidget(self.settings_experiment_list)
        self.experiment_history_summary = QLabel(
            "Experiment history will summarise completed and inconclusive results here."
        )
        self.experiment_history_summary.setWordWrap(True)
        self.experiment_history_summary.setObjectName("Muted")
        experiment_layout.addWidget(self.experiment_history_summary)
        result_form = QFormLayout()
        self.experiment_status_combo = QComboBox()
        for status in ("planned", "running", "completed", "inconclusive", "cancelled"):
            self.experiment_status_combo.addItem(status.title(), status)
        self.experiment_outcome_input = QLineEdit()
        self.experiment_outcome_input.setPlaceholderText("Observed result, or why it was inconclusive")
        result_form.addRow("Experiment status", self.experiment_status_combo)
        result_form.addRow("Observed outcome", self.experiment_outcome_input)
        experiment_layout.addLayout(result_form)
        update_result = QPushButton("Save experiment result")
        update_result.clicked.connect(self._update_selected_experiment)
        experiment_layout.addWidget(update_result, 0, Qt.AlignmentFlag.AlignLeft)
        self.settings_status = QLabel("Settings are stored locally. The app never applies changes to the game.")
        self.settings_status.setObjectName("Muted")
        experiment_layout.addWidget(self.settings_status)
        page_layout.addWidget(experiment_panel, 1)
        self._refresh_settings_data()

    def _import_game_settings(self) -> None:
        """Read a user-selected GameSettings.ini into only explicitly mapped controls."""
        suggested_folder = (
            Path.home() / "Documents" / "My Games" / "Rainbow Six - Siege"
        )
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Import GameSettings.ini (read-only)",
            str(suggested_folder),
            "Game settings (GameSettings.ini);;INI files (*.ini);;All files (*)",
        )
        if not path:
            return
        try:
            imported = read_game_settings_ini(path)
        except (OSError, ValueError) as error:
            self.settings_import_status.setText(
                f"Import failed; no fields were changed. {error}"
            )
            return

        for key, value in imported.values.items():
            control = self.settings_spinboxes.get(key)
            if control is not None:
                control.setValue(value)

        mapped_labels = [
            f"{key.replace('_', ' ').title()}={value:g}"
            for key, value in imported.values.items()
        ]
        missing_labels = [
            key.replace("_", " ").title()
            for key in self.settings_spinboxes
            if key not in imported.values
        ]
        details = [
            f"Read {Path(imported.source_path).name} without writing to it.",
            "Imported: " + (", ".join(mapped_labels) if mapped_labels else "none"),
            "Left unchanged for manual verification: " + (", ".join(missing_labels) if missing_labels else "none"),
            "DPI is not stored in GameSettings.ini. Per-scope keys with names such as 2x/3x are not "
            "guessed as 2.5x/3.5x/8x values; verify those values in the current in-game UI.",
        ]
        if imported.additional_ads_keys:
            details.append(
                "Additional ADS keys found but not auto-mapped: "
                + ", ".join(imported.additional_ads_keys)
            )
        if imported.warnings:
            details.extend(imported.warnings)
        details.append("Review the populated fields, then save a baseline only after confirming them.")
        self.settings_import_status.setText("\n".join(details))

    def _save_settings_snapshot(self) -> None:
        if self.settings_service is None:
            QMessageBox.warning(self, "Storage unavailable", "Settings storage has not been configured.")
            return
        label = self.settings_label_input.text().strip()
        if not label:
            QMessageBox.information(self, "Snapshot name required", "Give this settings snapshot a name.")
            return
        values = {key: control.value() for key, control in self.settings_spinboxes.items()}
        try:
            snapshot = self.settings_service.save_snapshot(label, values)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Could not save settings", f"Your settings were not saved.\\n\\n{error}")
            return
        self._refresh_settings_data(select_snapshot_id=snapshot.id)
        self.settings_status.setText("Settings snapshot saved locally.")
        self._refresh_overview()

    def _refresh_settings_data(self, *, select_snapshot_id: str | None = None) -> None:
        if not hasattr(self, "experiment_baseline_combo"):
            return
        try:
            snapshots = self.settings_service.list_snapshots() if self.settings_service else []
            experiments = self.settings_service.list_experiments() if self.settings_service else []
        except (OSError, RuntimeError, sqlite3.Error) as error:
            self.settings_status.setText(f"Could not load settings history: {error}")
            return
        for combo in (self.experiment_baseline_combo, self.experiment_test_combo):
            current = select_snapshot_id or combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for snapshot in snapshots:
                combo.addItem(snapshot.label, snapshot.id)
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self.settings_experiment_list.clear()
        for experiment in experiments:
            baseline = next((s.label for s in snapshots if s.id == experiment.baseline_snapshot_id), "Missing baseline")
            test = next((s.label for s in snapshots if s.id == experiment.test_snapshot_id), "Not selected")
            baseline_snapshot = next(
                (snapshot for snapshot in snapshots if snapshot.id == experiment.baseline_snapshot_id),
                None,
            )
            test_snapshot = next(
                (snapshot for snapshot in snapshots if snapshot.id == experiment.test_snapshot_id),
                None,
            )
            if baseline_snapshot is not None and test_snapshot is not None:
                setting_keys = set(baseline_snapshot.values) | set(test_snapshot.values)
                difference_count = sum(
                    key not in baseline_snapshot.values
                    or key not in test_snapshot.values
                    or baseline_snapshot.values[key] != test_snapshot.values[key]
                    for key in setting_keys
                )
                comparison = f"{difference_count} setting change(s)"
            else:
                comparison = "comparison not configured"
            item = QListWidgetItem(
                f"{experiment.title}  ·  {experiment.status.title()}  ·  "
                f"{baseline} → {test}  ·  {comparison}"
            )
            item.setData(Qt.ItemDataRole.UserRole, experiment.id)
            self.settings_experiment_list.addItem(item)
        if not experiments:
            self.settings_experiment_list.addItem("No experiments recorded yet.")
            self.experiment_status_combo.setEnabled(False)
            self.experiment_outcome_input.setEnabled(False)
        else:
            self.experiment_status_combo.setEnabled(True)
            self.experiment_outcome_input.setEnabled(True)
            if self.settings_experiment_list.currentItem() is None:
                self.settings_experiment_list.setCurrentRow(0)
        if hasattr(self, "experiment_history_summary"):
            completed = [item for item in experiments if item.status == "completed"]
            inconclusive = [item for item in experiments if item.status == "inconclusive"]
            lines = [
                f"Experiment history: {len(completed)} completed · {len(inconclusive)} inconclusive",
                "Recorded outcomes are observations, not proof that a setting caused a performance change.",
            ]
            for item in sorted(completed + inconclusive, key=lambda entry: entry.created_at, reverse=True):
                outcome = (item.outcome or "No outcome recorded").strip()
                lines.append(f"• {item.title} ({item.status}): {outcome}")
            if not completed and not inconclusive:
                lines.append("Complete an experiment or mark it inconclusive to build a comparison history.")
            self.experiment_history_summary.setText("\\n".join(lines))

    def _refresh_snapshot_comparison(self, *_args: object) -> None:
        """Show exact differences between the selected local settings snapshots."""
        if not hasattr(self, "settings_comparison_label"):
            return
        baseline_id = self.experiment_baseline_combo.currentData()
        test_id = self.experiment_test_combo.currentData()
        if not baseline_id or not test_id:
            self.settings_comparison_label.setText(
                "Save at least two settings snapshots to compare a baseline with a test."
            )
            return
        try:
            snapshots = self.settings_service.list_snapshots() if self.settings_service else []
        except (OSError, RuntimeError, sqlite3.Error) as error:
            self.settings_comparison_label.setText(f"Could not load snapshots: {error}")
            return
        baseline = next((item for item in snapshots if item.id == baseline_id), None)
        test = next((item for item in snapshots if item.id == test_id), None)
        if baseline is None or test is None:
            self.settings_comparison_label.setText("One of the selected snapshots is no longer available.")
            return
        keys = sorted(set(baseline.values) | set(test.values))
        differences = [
            (key, baseline.values.get(key, "—"), test.values.get(key, "—"))
            for key in keys
            if key not in baseline.values
            or key not in test.values
            or baseline.values[key] != test.values[key]
        ]
        if not differences:
            self.settings_comparison_label.setText(
                f"No differences found between “{baseline.label}” and “{test.label}”."
            )
            return
        lines = [f"Comparison: {baseline.label} → {test.label}"]
        for key, before, after in differences:
            lines.append(f"• {key.replace('_', ' ').title()}: {before} → {after}")
        lines.append(f"{len(differences)} setting(s) differ. This is a configuration comparison, not proof of performance improvement.")
        self.settings_comparison_label.setText("\n".join(lines))

    def _load_selected_experiment(self, *_args: object) -> None:
        item = self.settings_experiment_list.currentItem()
        experiment_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not experiment_id or self.settings_service is None:
            return
        experiment = next(
            (entry for entry in self.settings_service.list_experiments() if entry.id == experiment_id),
            None,
        )
        if experiment is None:
            return
        index = self.experiment_status_combo.findData(experiment.status)
        if index >= 0:
            self.experiment_status_combo.setCurrentIndex(index)
        self.experiment_outcome_input.setText(experiment.outcome or "")

    def _update_selected_experiment(self) -> None:
        item = self.settings_experiment_list.currentItem()
        experiment_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not experiment_id or self.settings_service is None:
            QMessageBox.information(self, "Select an experiment", "Record an experiment before updating its result.")
            return
        outcome = self.experiment_outcome_input.text().strip()
        status = self.experiment_status_combo.currentData()
        if status in {"completed", "inconclusive"} and not outcome:
            QMessageBox.information(
                self,
                "Outcome required",
                "Add a short observed outcome before marking the experiment completed or inconclusive.",
            )
            self.experiment_outcome_input.setFocus()
            return
        try:
            experiment = self.settings_service.update_experiment(
                experiment_id, status=status, outcome=outcome
            )
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            QMessageBox.warning(
                self, "Could not update experiment", f"Your result was not saved.\\n\\n{error}"
            )
            return
        self._refresh_settings_data()
        self.settings_status.setText(f"Experiment result saved: {experiment.status.title()}.")
        self._refresh_overview()

    def _create_settings_experiment(self) -> None:
        if self.settings_service is None:
            QMessageBox.warning(self, "Storage unavailable", "Settings storage has not been configured.")
            return
        baseline_id = self.experiment_baseline_combo.currentData()
        test_id = self.experiment_test_combo.currentData()
        title = self.experiment_title_input.text().strip()
        hypothesis = self.experiment_hypothesis_input.text().strip()
        if not baseline_id:
            QMessageBox.information(self, "Baseline required", "Save a baseline snapshot first.")
            return
        if not title or not hypothesis:
            QMessageBox.information(self, "Experiment details required", "Enter an experiment title and hypothesis.")
            return
        try:
            experiment = self.settings_service.create_experiment(
                title, hypothesis, baseline_id,
                changed_variable=self.experiment_variable_input.text().strip(),
                test_snapshot_id=test_id,
            )
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Could not record experiment", f"Your experiment was not saved.\\n\\n{error}")
            return
        self._refresh_settings_data()
        self.settings_status.setText(f"Experiment recorded locally: {experiment.title}")
        self._refresh_overview()

    def _export_session_summary(self) -> None:
        """Export the selected session and its manual notes to a Markdown file."""
        session_id = self.review_session_combo.currentData() if hasattr(self, "review_session_combo") else None
        if not session_id or self.session_service is None:
            QMessageBox.information(self, "Select a session", "Create or select a session before exporting.")
            return
        try:
            sessions = self.session_service.list_sessions()
            session = next((item for item in sessions if item.id == session_id), None)
            if session is None:
                raise ValueError("The selected session is no longer available.")
            observations = self.session_service.list_observations(session.id)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Could not prepare export", f"No export was created.\\n\\n{error}")
            return
        target, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export session summary",
            "session-summary.md",
            "Markdown summary (*.md);;Structured JSON (*.json);;Observation CSV (*.csv)",
        )
        if not target:
            return
        suffix = Path(target).suffix.casefold()
        if not suffix:
            suffix = ".json" if "JSON" in selected_filter else ".csv" if "CSV" in selected_filter else ".md"
            target = f"{target}{suffix}"
        try:
            if suffix == ".json":
                content = render_session_json(session, observations)
            elif suffix == ".csv":
                content = render_session_csv(observations)
            else:
                content = render_session_summary(session, observations)
            Path(target).write_text(content, encoding="utf-8", newline="")
        except OSError as error:
            QMessageBox.warning(self, "Could not write export", f"The summary was not saved.\\n\\n{error}")
            return
        self.review_status.setText(f"Session summary exported to {target}")

    def _browse_session_media(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a gameplay recording", "", "Video files (*.mp4 *.mkv *.mov *.avi);;All files (*)"
        )
        if path:
            self.session_media_input.setText(path)

    def _create_review_session(self) -> None:
        if self.session_service is None:
            QMessageBox.warning(self, "Storage unavailable", "Session storage has not been configured.")
            return
        title = self.session_title_input.text().strip()
        if not title:
            QMessageBox.information(self, "Session name required", "Enter a name for this review session.")
            self.session_title_input.setFocus()
            return
        try:
            session = self.session_service.create_session(
                title, media_path=self.session_media_input.text().strip() or None
            )
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not save session", f"Your session was not saved.\n\n{error}")
            return
        self.session_title_input.clear()
        self.session_media_input.clear()
        self._refresh_review_sessions(select_id=session.id)
        self.review_status.setText("Session saved locally.")
        self._refresh_overview()

    def _refresh_review_sessions(self, *, select_id: str | None = None) -> None:
        if not hasattr(self, "review_session_combo"):
            return
        current_id = select_id or self.review_session_combo.currentData()
        self.review_session_combo.blockSignals(True)
        self.review_session_combo.clear()
        try:
            sessions = self.session_service.list_sessions() if self.session_service else []
        except (OSError, RuntimeError, sqlite3.Error) as error:
            sessions = []
            self.review_status.setText(f"Could not load sessions: {error}")
        for session in sessions:
            self.review_session_combo.addItem(session.title, session.id)
        index = self.review_session_combo.findData(current_id)
        if index >= 0:
            self.review_session_combo.setCurrentIndex(index)
        self.review_session_combo.blockSignals(False)
        self._refresh_observations()
        self._load_review_media()

    def _on_review_session_changed(self, *_args: object) -> None:
        self._refresh_observations()
        self._load_review_media()

    def _load_review_media(self) -> None:
        if not hasattr(self, "review_media_player"):
            return
        session_id = self.review_session_combo.currentData()
        try:
            sessions = self.session_service.list_sessions() if self.session_service else []
        except (OSError, RuntimeError, sqlite3.Error) as error:
            self.review_media_status.setText(f"Could not load session recording: {error}")
            return
        session = next((item for item in sessions if item.id == session_id), None)
        media_path = session.media_path if session is not None else None
        self.review_media_player.stop()
        if not media_path:
            self.review_media_player.setSource(QUrl())
            self.review_media_status.setText("This session has no recording path. You can still add timestamped observations.")
            return
        recording = Path(media_path).expanduser()
        if not recording.is_file():
            self.review_media_player.setSource(QUrl())
            self.review_media_status.setText(f"Recording file not found: {recording}. Select an existing recording when creating a session.")
            return
        self.review_media_player.setSource(QUrl.fromLocalFile(str(recording.resolve())))
        self.review_media_status.setText(f"Loaded local recording: {recording.name}")

    def _toggle_review_playback(self) -> None:
        if self.review_media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.review_media_player.pause()
            return
        if self.review_media_player.source().isEmpty():
            self.review_media_status.setText("Choose a session with an existing local video file first.")
            return
        self.review_media_player.play()

    def _update_media_position(self, position: int) -> None:
        if not self.review_seek_slider.isSliderDown():
            self.review_seek_slider.setValue(position)
        self._update_media_time(position, self.review_media_player.duration())

    def _update_media_duration(self, duration: int) -> None:
        self.review_seek_slider.setRange(0, max(0, duration))
        self._update_media_time(self.review_media_player.position(), duration)

    def _update_media_time(self, position: int, duration: int) -> None:
        def format_time(milliseconds: int) -> str:
            seconds = max(0, milliseconds // 1000)
            return f"{seconds // 60:02d}:{seconds % 60:02d}"

        self.review_media_time.setText(f"{format_time(position)} / {format_time(duration)}")

    def _update_play_button(self, state: QMediaPlayer.PlaybackState) -> None:
        self.review_play_button.setText("Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play")

    def _on_media_error(self, _error: QMediaPlayer.Error, error_string: str) -> None:
        if error_string:
            self.review_media_status.setText(f"Could not play this recording: {error_string}")

    def _refresh_observations(self, *_args: object) -> None:
        if not hasattr(self, "observation_list"):
            return
        self.observation_list.clear()
        session_id = self.review_session_combo.currentData()
        if not session_id or self.session_service is None:
            self.observation_list.addItem("No session yet — create one above to begin.")
            return
        try:
            observations = self.session_service.list_observations(session_id)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            self.observation_list.addItem(f"Could not load observations: {error}")
            return
        query = self.observation_filter_input.text().strip().casefold() if hasattr(self, "observation_filter_input") else ""
        visible = [
            item for item in observations
            if not query or query in item.text.casefold()
            or query in item.kind.value.casefold()
            or any(query in tag.casefold() for tag in item.tags)
        ]
        if not visible:
            message = "No observations yet. Add the first timestamped note above." if not observations else "No observations match this filter."
            self.observation_list.addItem(message)
            return
        for item in visible:
            seconds = item.timestamp_ms // 1000
            timestamp = f"{seconds // 60:02d}:{seconds % 60:02d}"
            tags = f"  ·  #{', #'.join(item.tags)}" if item.tags else ""
            entry = QListWidgetItem(f"{timestamp}  ·  {item.kind.value.title()}  ·  {item.text}{tags}")
            entry.setData(Qt.ItemDataRole.UserRole, item.id)
            self.observation_list.addItem(entry)

    def _set_observation_timestamp_from_video(self) -> None:
        """Copy the current playback position into the timestamp editor."""
        if not hasattr(self, "review_media_player"):
            return
        self.observation_timestamp.setValue(self.review_media_player.position() // 1000)

    def _open_linked_annotation_frame(self) -> None:
        """Open the sampled frame referenced by the selected clip annotation observation."""
        item = self.observation_list.currentItem()
        session_id = self.review_session_combo.currentData()
        observation_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not session_id or not observation_id or self.session_service is None:
            self.review_status.setText("Select a saved observation first.")
            return
        try:
            observations = self.session_service.list_observations(session_id)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            self.review_status.setText(f"Could not load the selected observation: {error}")
            return
        observation = next((entry for entry in observations if entry.id == observation_id), None)
        if observation is None:
            self.review_status.setText("The selected observation is no longer available.")
            self._refresh_observations()
            return
        annotation_id = next(
            (tag.removeprefix("annotation-id:") for tag in observation.tags
             if tag.startswith("annotation-id:")),
            None,
        )
        if not annotation_id:
            self.review_status.setText("This observation is not linked to a clip annotation.")
            return
        if self._annotation_store is None:
            self.review_status.setText(
                "Load the matching sampling manifest in Clip Annotation first, then retry."
            )
            self.show_page("Clip Annotation")
            return
        annotation = next(
            (entry for entry in self._annotation_store.annotations
             if entry.annotation_id == annotation_id),
            None,
        )
        if annotation is None:
            self.review_status.setText(
                "The linked annotation isn't in the currently loaded dataset. Load its matching manifest."
            )
            self.show_page("Clip Annotation")
            return
        target_row = next(
            (
                row for row in range(self.annotation_frame_list.count())
                if self.annotation_frame_list.item(row).data(Qt.ItemDataRole.UserRole)
                == (annotation.timestamp_ms, annotation.frame_filename)
            ),
            None,
        )
        if target_row is None:
            self.review_status.setText("The linked frame is not present in the currently loaded manifest.")
            self.show_page("Clip Annotation")
            return
        self.show_page("Clip Annotation")
        self.annotation_frame_list.setCurrentRow(target_row)
        self.annotation_status.setText(
            f"Opened linked annotation at {annotation.timestamp_ms / 1000:.2f}s: "
            f"{annotation.frame_filename}."
        )

    def _seek_to_selected_observation(self, item: QListWidgetItem) -> None:
        """Seek to the timestamp represented by a selected observation."""
        if not hasattr(self, "review_media_player"):
            return
        text = item.text()
        timestamp = text.split("  ·  ", maxsplit=1)[0]
        try:
            minutes, seconds = timestamp.split(":", maxsplit=1)
            milliseconds = (int(minutes) * 60 + int(seconds)) * 1000
        except (ValueError, TypeError):
            return
        if self.review_media_player.source().isEmpty():
            self.review_status.setText("This observation has a timestamp, but no local video is loaded.")
            return
        self.review_media_player.setPosition(milliseconds)
        self.review_media_player.pause()
        self.observation_timestamp.setValue(milliseconds // 1000)
        self.review_status.setText(f"Jumped to observation at {timestamp}.")

    def _append_selected_coaching_tag(self) -> None:
        """Append a supported coaching tag without duplicating an existing tag."""
        if not hasattr(self, "coaching_tag_combo") or not hasattr(self, "observation_tags_input"):
            return
        selected = self.coaching_tag_combo.currentData()
        if not selected:
            return
        tags = [
            tag.strip()
            for tag in self.observation_tags_input.text().split(",")
            if tag.strip()
        ]
        normalized_existing = {
            " ".join(tag.casefold().replace("_", " ").replace("-", " ").split())
            for tag in tags
        }
        normalized_selected = " ".join(
            str(selected).casefold().replace("_", " ").replace("-", " ").split()
        )
        if normalized_selected not in normalized_existing:
            tags.append(str(selected))
            self.observation_tags_input.setText(", ".join(tags))

    def _add_review_observation(self) -> None:
        if self.session_service is None:
            QMessageBox.warning(self, "Storage unavailable", "Session storage has not been configured.")
            return
        session_id = self.review_session_combo.currentData()
        text = self.observation_text.text().strip()
        if not session_id:
            QMessageBox.information(self, "Select a session", "Create or select a session first.")
            return
        if not text:
            QMessageBox.information(self, "Observation required", "Enter a short observation before saving.")
            self.observation_text.setFocus()
            return
        try:
            kind = ObservationKind(self.observation_kind.currentData())
            tags = tuple(dict.fromkeys(
                tag.strip().casefold()
                for tag in self.observation_tags_input.text().split(",")
                if tag.strip()
            ))
            self.session_service.add_observation(
                session_id, self.observation_timestamp.value() * 1000, text, kind=kind, tags=tags
            )
        except (OSError, ValueError, RuntimeError) as error:
            QMessageBox.warning(self, "Could not save observation", f"Your observation was not saved.\n\n{error}")
            return
        self.observation_text.clear()
        self.observation_tags_input.clear()
        self._refresh_observations()
        self.review_status.setText("Observation saved locally.")
        self._refresh_overview()

    def show_page(self, name: str) -> None:
        """Select a page and keep the active navigation state in sync."""
        if name == "Clip Annotation":
            self._refresh_annotation_sessions()
        elif name == "AI Coach":
            self._refresh_ai_coach()
        elif name == "Preferences & Privacy":
            self._refresh_storage_info()
        elif name == "Overview":
            self._refresh_overview()
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
