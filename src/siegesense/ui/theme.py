"""Shared visual tokens and stylesheet for the desktop workspace."""

APP_STYLESHEET = """
* {
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QWidget {
    background: #F7F8FA;
    color: #20232B;
}
QMainWindow { background: #F7F8FA; }
QFrame#Sidebar {
    background: #FFFFFF;
    border-right: 1px solid #E6E8EE;
}
QLabel#BrandMark {
    background: #6D5CE8;
    color: #FFFFFF;
    border-radius: 10px;
    font-size: 17px;
    font-weight: 800;
    min-width: 38px;
    max-width: 38px;
    min-height: 38px;
    max-height: 38px;
}
QLabel#BrandName { font-size: 15px; font-weight: 750; color: #20232B; }
QLabel#BrandSubtitle { font-size: 10px; color: #777D8A; }
QPushButton#NavButton {
    text-align: left;
    padding: 11px 12px;
    border: none;
    border-radius: 9px;
    color: #606675;
    background: transparent;
    font-weight: 600;
}
QPushButton#NavButton:hover { background: #F1F0FF; color: #4F40C9; }
QPushButton#NavButton[active="true"] {
    background: #EFEDFF;
    color: #5142CB;
    font-weight: 700;
}
QPushButton#CollapseButton {
    background: #FFFFFF;
    color: #777D8A;
    border: 1px solid #E6E8EE;
    border-radius: 8px;
    padding: 7px;
}
QLabel#PageEyebrow {
    color: #6D5CE8;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#PageTitle { font-size: 26px; font-weight: 750; color: #20232B; }
QLabel#PageDescription { color: #707686; font-size: 13px; }
QFrame#Panel, QFrame#MetricCard {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 14px;
}
QFrame#VideoDropZone {
    background: #FCFCFF;
    border: 2px dashed #CFCBFB;
    border-radius: 14px;
}
QFrame#VideoDropZone QLabel { background: transparent; }
QFrame#VideoDropZone:hover {
    background: #F7F6FF;
    border-color: #8B7FF0;
}
QLabel#PanelTitle { font-size: 14px; font-weight: 750; }
QLabel#MetricLabel { color: #737989; font-size: 11px; font-weight: 650; }
QLabel#MetricValue { color: #20232B; font-size: 25px; font-weight: 750; }
QLabel#MetricHint { color: #858A97; font-size: 11px; }
QLabel#Pill {
    background: #F1F0FF;
    color: #5949D0;
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 10px;
    font-weight: 750;
}
QLabel#StatusPill {
    background: #FFF4D8;
    color: #89631A;
    border-radius: 8px;
    padding: 6px 9px;
    font-size: 10px;
    font-weight: 750;
}
QLabel#Muted { color: #7C8290; }
QLabel#FramePreview {
    background: #F0F1F5;
    color: #7C8290;
    border: 1px dashed #D5D8E2;
    border-radius: 10px;
    padding: 10px;
}
QLabel#EmptyIcon {
    background: #F1F0FF;
    color: #6D5CE8;
    border-radius: 12px;
    font-size: 20px;
    font-weight: 800;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
}
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QPushButton#PrimaryButton {
    background: #6D5CE8;
    color: #FFFFFF;
    border: none;
    border-radius: 9px;
    padding: 10px 14px;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover { background: #5C4BD4; }
QPushButton#SecondaryButton {
    background: #FFFFFF;
    color: #353947;
    border: 1px solid #E1E4EC;
    border-radius: 9px;
    padding: 9px 13px;
    font-weight: 650;
}
QPushButton#SecondaryButton:hover { background: #F7F7FC; }
QFrame#Divider { background: #E8EAF0; max-height: 1px; }
"""
