"""Initial desktop shell with explicit demo-mode presentation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
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
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from siegesense.domain.models import ObservationKind
from siegesense.services.session_service import SessionService
from siegesense.services.settings_service import SettingsService

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

    def __init__(
        self,
        session_service: SessionService | None = None,
        settings_service: SettingsService | None = None,
    ) -> None:
        super().__init__()
        self.session_service = session_service
        self.settings_service = settings_service
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
        elif name == "Overview":
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
        return page

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
        observation_form.addRow("Timestamp", self.observation_timestamp)
        observation_form.addRow("Category", self.observation_kind)
        observation_form.addRow("Observation", self.observation_text)
        review_layout.addLayout(observation_form)
        add_note = QPushButton("Add observation")
        add_note.clicked.connect(self._add_review_observation)
        review_layout.addWidget(add_note, 0, Qt.AlignmentFlag.AlignLeft)
        self.observation_list = QListWidget()
        self.observation_list.setMinimumHeight(150)
        review_layout.addWidget(self.observation_list)
        self.review_status = QLabel("Observations are saved locally. Demo records are excluded.")
        self.review_status.setObjectName("Muted")
        review_layout.addWidget(self.review_status)
        page_layout.addWidget(review_panel, 1)
        self._refresh_review_sessions()

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
        self.settings_spinboxes: dict[str, QSpinBox] = {}
        for key, label, minimum, maximum, value in (
            ("horizontal", "Horizontal sensitivity", 1, 100, 6),
            ("vertical", "Vertical sensitivity", 1, 100, 6),
            ("ads_1x", "1.0× ADS", 1, 200, 40),
            ("ads_2_5x", "2.5× ADS", 1, 200, 44),
            ("ads_3_5x", "3.5× ADS", 1, 200, 40),
            ("ads_8x", "8.0× ADS", 1, 200, 36),
        ):
            control = QSpinBox()
            control.setRange(minimum, maximum)
            control.setValue(value)
            self.settings_spinboxes[key] = control
            form.addRow(label, control)
        layout.addLayout(form)
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
        create_experiment = QPushButton("Record experiment")
        create_experiment.clicked.connect(self._create_settings_experiment)
        experiment_layout.addWidget(create_experiment, 0, Qt.AlignmentFlag.AlignLeft)
        self.settings_experiment_list = QListWidget()
        self.settings_experiment_list.setMinimumHeight(100)
        experiment_layout.addWidget(self.settings_experiment_list)
        self.settings_status = QLabel("Settings are stored locally. The app never applies changes to the game.")
        self.settings_status.setObjectName("Muted")
        experiment_layout.addWidget(self.settings_status)
        page_layout.addWidget(experiment_panel, 1)
        self._refresh_settings_data()

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
            self.settings_experiment_list.addItem(
                f"{experiment.title}  ·  {experiment.status.title()}  ·  {baseline} → {test}"
            )
        if not experiments:
            self.settings_experiment_list.addItem("No experiments recorded yet.")

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
        if not observations:
            self.observation_list.addItem("No observations yet. Add the first timestamped note above.")
            return
        for item in observations:
            seconds = item.timestamp_ms // 1000
            timestamp = f"{seconds // 60:02d}:{seconds % 60:02d}"
            entry = QListWidgetItem(f"{timestamp}  ·  {item.kind.value.title()}  ·  {item.text}")
            entry.setData(Qt.ItemDataRole.UserRole, item.id)
            self.observation_list.addItem(entry)

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
            self.session_service.add_observation(
                session_id, self.observation_timestamp.value() * 1000, text, kind=kind
            )
        except (OSError, ValueError, RuntimeError) as error:
            QMessageBox.warning(self, "Could not save observation", f"Your observation was not saved.\n\n{error}")
            return
        self.observation_text.clear()
        self._refresh_observations()
        self.review_status.setText("Observation saved locally.")
        self._refresh_overview()

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
