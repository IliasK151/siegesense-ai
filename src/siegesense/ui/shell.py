"""Initial desktop shell with explicit demo-mode presentation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap
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
from siegesense.services.export_service import (
    render_session_csv,
    render_session_json,
    render_session_summary,
)
from siegesense.services.session_service import SessionService
from siegesense.services.settings_service import SettingsService
from siegesense.vision.annotations import ALLOWED_LABELS, AnnotationStore, load_manifest
from siegesense.vision.evaluation import summarize_aim_frames, write_evaluation_report
from siegesense.vision.frame_sampling import sample_video_frames
from siegesense.vision.sequence_analysis import summarize_annotated_sequences

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
        elif name == "Clip Annotation":
            self._build_annotation_lab(page_layout)
        elif name == "AI Coach":
            self._build_ai_coach(page_layout)
        elif name in {"Aim Lab", "Movement"}:
            self._build_category_review(page_layout, name)
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
        """Build transparent, rules-based review prompts from saved manual notes."""
        page_layout.addWidget(
            panel(
                "Coaching status",
                "This is an evidence-linked review assistant, not a trained AI model or automatic gameplay detector. "
                "It only summarises the notes you have saved locally.",
            )
        )
        refresh = QPushButton("Refresh coaching summary")
        refresh.clicked.connect(self._refresh_ai_coach)
        page_layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignLeft)
        self.coach_summary_panel = QFrame()
        self.coach_summary_panel.setObjectName("Panel")
        coach_layout = QVBoxLayout(self.coach_summary_panel)
        coach_layout.setContentsMargins(18, 16, 18, 18)
        coach_layout.setSpacing(10)
        coach_layout.addWidget(QLabel("Review prompts"))
        self.coach_prompt_list = QListWidget()
        self.coach_prompt_list.setMinimumHeight(180)
        coach_layout.addWidget(self.coach_prompt_list)
        coach_layout.addWidget(QLabel("Recent evidence"))
        self.coach_evidence_list = QListWidget()
        self.coach_evidence_list.setMinimumHeight(180)
        coach_layout.addWidget(self.coach_evidence_list)
        page_layout.addWidget(self.coach_summary_panel, 1)
        self._refresh_ai_coach()

    def _refresh_ai_coach(self) -> None:
        if not hasattr(self, "coach_prompt_list"):
            return
        self.coach_prompt_list.clear()
        self.coach_evidence_list.clear()
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
            return
        if not records:
            self.coach_prompt_list.addItem(
                "Start with one recorded match and add a few timestamped notes in Session Review."
            )
            self.coach_evidence_list.addItem("No real-session observations are available yet.")
            return

        counts: dict[str, int] = {}
        for _session, observation in records:
            counts[observation.kind.value] = counts.get(observation.kind.value, 0) + 1
        prompts = {
            "aim": "Aim: revisit the logged moments and separate initial placement, first-shot timing, and target-transition control before changing sensitivity.",
            "movement": "Movement: replay the logged moments and check whether movement timing, exposure, or crosshair placement was the issue.",
            "positioning": "Positioning: review available cover, escape options, and the angle you chose before the engagement.",
            "decision": "Decision-making: note the information available at the time and compare it with the decision you made.",
            "other": "Other: clarify the observation into one specific behaviour you can check in another review.",
        }
        for category, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
            self.coach_prompt_list.addItem(f"{category.title()} · {count} note(s) — {prompts[category]}")
        self.coach_prompt_list.addItem(
            "These prompts are transparent rules based on note categories, not proof of a weakness or an automatic diagnosis."
        )
        records.sort(key=lambda pair: (pair[0].started_at, pair[1].timestamp_ms), reverse=True)
        for session, observation in records[:10]:
            seconds = observation.timestamp_ms // 1000
            timestamp = f"{seconds // 60:02d}:{seconds % 60:02d}"
            tags = f" · Tags: {', '.join(observation.tags)}" if observation.tags else ""
            self.coach_evidence_list.addItem(
                f"{session.title} · {timestamp} · {observation.kind.value.title()} · {observation.text}{tags}"
            )

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
        self.observation_tags_input.setPlaceholderText("Optional comma-separated tags, e.g. overshoot, acog, close-range")
        self.observation_filter_input = QLineEdit()
        self.observation_filter_input.setPlaceholderText("Filter notes by text or tag…")
        self.observation_filter_input.textChanged.connect(self._refresh_observations)
        observation_form.addRow("Category", self.observation_kind)
        observation_form.addRow("Tags", self.observation_tags_input)
        observation_form.addRow("Observation", self.observation_text)
        review_layout.addLayout(observation_form)
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
        source_layout.addWidget(QLabel("Sample a local recording"))
        self.annotation_video_input = QLineEdit()
        self.annotation_video_input.setPlaceholderText("Choose a gameplay recording")
        video_row = QHBoxLayout()
        video_row.addWidget(self.annotation_video_input, 1)
        browse_video = QPushButton("Browse video…")
        browse_video.clicked.connect(self._browse_annotation_video)
        video_row.addWidget(browse_video)
        source_layout.addLayout(video_row)

        self.annotation_output_input = QLineEdit()
        self.annotation_output_input.setPlaceholderText("Choose an empty output folder for sampled frames")
        output_row = QHBoxLayout()
        output_row.addWidget(self.annotation_output_input, 1)
        browse_output = QPushButton("Output folder…")
        browse_output.clicked.connect(self._browse_annotation_output)
        output_row.addWidget(browse_output)
        source_layout.addLayout(output_row)

        sampling_row = QHBoxLayout()
        sampling_row.addWidget(QLabel("Sampling interval (ms)"))
        self.annotation_interval_spin = QSpinBox()
        self.annotation_interval_spin.setRange(50, 10000)
        self.annotation_interval_spin.setSingleStep(50)
        self.annotation_interval_spin.setValue(100)
        self.annotation_interval_spin.setToolTip(
            "Shorter intervals create more images. This is for manual review, not precise flick timing."
        )
        sampling_row.addWidget(self.annotation_interval_spin)
        sample_button = QPushButton("Sample frames")
        sample_button.clicked.connect(self._sample_annotation_video)
        sampling_row.addWidget(sample_button)
        sampling_row.addStretch(1)
        source_layout.addLayout(sampling_row)

        source_layout.addWidget(QLabel("Or open an existing sampled-video manifest"))
        source_row = QHBoxLayout()
        self.annotation_manifest_input = QLineEdit()
        self.annotation_manifest_input.setPlaceholderText("Choose sampling_manifest.json")
        source_row.addWidget(self.annotation_manifest_input, 1)
        browse_manifest = QPushButton("Browse…")
        browse_manifest.clicked.connect(self._browse_annotation_manifest)
        source_row.addWidget(browse_manifest)
        source_layout.addLayout(source_row)
        load_manifest_button = QPushButton("Load frames")
        load_manifest_button.clicked.connect(self._load_annotation_manifest)
        source_layout.addWidget(load_manifest_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.annotation_status = QLabel(
            "Annotations are manual labels stored locally. No video or frames are uploaded."
        )
        self.annotation_status.setObjectName("Muted")
        self.annotation_status.setWordWrap(True)
        source_layout.addWidget(self.annotation_status)
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
        self.annotation_frame_preview = QLabel("Load a manifest to preview sampled frames.")
        self.annotation_frame_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.annotation_frame_preview.setMinimumSize(280, 180)
        self.annotation_frame_preview.setObjectName("FramePreview")
        self.annotation_frame_preview.setWordWrap(True)
        detail_layout.addWidget(self.annotation_frame_preview, 1)
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
        self.annotation_annotator_input = QLineEdit("Player")
        self.annotation_note_input = QLineEdit()
        self.annotation_note_input.setPlaceholderText("Optional context for this frame")
        annotation_form.addRow("Manual label", self.annotation_label_combo)
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

    def _browse_annotation_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select gameplay recording",
            "",
            "Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*)",
        )
        if path:
            self.annotation_video_input.setText(path)
            if not self.annotation_output_input.text().strip():
                source = Path(path)
                self.annotation_output_input.setText(str(source.parent / f"{source.stem}_frames"))

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
            self.annotation_frame_list.clear()
            self.annotation_history_list.clear()
            self._refresh_annotation_summary()
            self.annotation_frame_preview.setText("Could not load this manifest.")
            self.annotation_status.setText(f"Manifest not loaded: {error}")
            return

        self.annotation_frame_list.clear()
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
            self.annotation_frame_preview.setPixmap(QPixmap())
            self.annotation_frame_preview.setText(
                "Frame image is missing. Re-run sampling or check the output folder."
            )
            return
        pixmap = QPixmap(str(frame_path))
        if pixmap.isNull():
            self.annotation_frame_preview.setPixmap(QPixmap())
            self.annotation_frame_preview.setText("This image could not be decoded.")
            return
        self.annotation_frame_preview.setText("")
        self.annotation_frame_preview.setPixmap(
            pixmap.scaled(
                self.annotation_frame_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

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
                f"longest observed sampled span: {longest_text}"
            )
        self.annotation_summary_label.setText(
            f"Manual frame labels · on target: {summary.crosshair_on_target_frames} · "
            f"off target: {summary.crosshair_off_target_frames} · "
            f"selected-frame on-target share: {share_text} · "
            f"transitions: {summary.target_transition_frames} · "
            f"ambiguous: {summary.ambiguous_frames} · unusable: {summary.unusable_frames}. "
            f"{sequence_text}. "
            "Observed sampled spans are not precise event durations. Descriptive only; "
            "not aim accuracy or representative gameplay performance."
        )

    def _refresh_annotation_history(self) -> None:
        self.annotation_history_list.clear()
        if self._annotation_store is None:
            return
        for annotation in self._annotation_store.annotations:
            note = f" — {annotation.note}" if annotation.note else ""
            item = QListWidgetItem(
                f"{annotation.timestamp_ms / 1000:.2f}s  ·  "
                f"{annotation.label.replace('_', ' ')}{note}"
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
        self.annotation_status.setText(
            f"Editing label for {annotation.timestamp_ms / 1000:.2f}s. "
            "Change the fields above and select Update selected annotation."
        )

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
                    baseline_snapshot.values.get(key) != test_snapshot.values.get(key)
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
            if baseline.values.get(key) != test.values.get(key)
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
