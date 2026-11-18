from src.gesture_assistant.domain.enums import QualityStatus
from src.gesture_assistant.ui import tokens as t

MAIN_WINDOW_TITLE = "GestureAssistant"
STATUS_TEXTS = {
    QualityStatus.VALID: "Śledzenie",
    QualityStatus.NO_PERSON: "Brak osoby",
    QualityStatus.LOW_VISIBILITY: "Słaba widoczność",
    QualityStatus.OUT_OF_FRAME: "Osoba poza kadrem",
    QualityStatus.MULTIPLE_PEOPLE: "Wiele osób w kadrze",
    QualityStatus.WRONG_VIEW: "Nieprawidłowy widok",
    QualityStatus.CAMERA_ERROR: "Błąd kamery",
}
BACKGROUND_COLOR = t.BACKGROUND
FOREGROUND_COLOR = t.TEXT
ACCENT_COLOR = t.ACCENT
ERROR_COLOR = t.ERROR
NO_PREVIEW_TEXT = "Podgląd nieaktywny · uruchom kamerę"
MISSING_MODEL_TEXT = "Brak modelu MediaPipe.\nPobierz model zgodnie z instrukcją w README."


def get_stylesheet() -> str:
    return f"""
    QMainWindow, QWidget#Workspace, QWidget#TrainingInspector, QScrollArea {{
        background: {t.BACKGROUND};
    }}
    QLabel, QCheckBox, QGroupBox {{ color: {t.TEXT}; }}
    QLabel[role="title"] {{ font-size: 26px; font-weight: 700; }}
        QLabel[role="brand"] {{
        color: {t.ACCENT};
        font-size: 20px;
        font-weight: 700;
    }}
    QLabel[role="secondary"] {{ color: {t.SECONDARY}; }}
    QLabel[role="error"] {{ color: {t.ERROR}; }}
    QLabel[role="status"] {{ background: {t.RAISED}; color: {t.ACCENT};
        padding: 8px; border-radius: 8px; }}
    QFrame[role="card"], QGroupBox {{ background: {t.SURFACE};
        border: 1px solid {t.BORDER}; border-radius: {t.RADIUS}px; }}
    QGroupBox {{ margin-top: 16px; padding: 12px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 12px; }}
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QListWidget {{
        background: {t.RAISED}; color: {t.TEXT}; border: 2px solid {t.BORDER};
        border-radius: 10px; padding: 6px 10px; }}
    QPushButton[nav="true"] {{ text-align: left; padding: 10px 12px; }}
    QPushButton[nav="true"]:checked {{ background: {t.RAISED}; color: {t.MAGENTA};
        border-color: {t.MAGENTA}; }}
    QPushButton[primary="true"] {{ background: {t.ACCENT}; color: {t.ON_ACCENT}; }}
    QPushButton[controlActive="true"] {{
        background: {t.ACCENT}; color: {t.ON_ACCENT}; border-color: {t.ACCENT};
    }}
    QPushButton:hover {{ border-color: {t.SECONDARY}; }}
    QPushButton:pressed {{ border-color: {t.ACCENT}; }}
    QPushButton:disabled, QPushButton[primary="true"]:disabled {{
        background: {t.SURFACE}; color: {t.SECONDARY}; border-color: {t.BORDER}; }}
    QPushButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QLineEdit:focus, QListWidget:focus, QCheckBox:focus {{ border: 2px solid {t.MAGENTA}; }}
    QListWidget::item:selected {{ background: {t.ACCENT}; color: {t.ON_ACCENT}; }}
    QComboBox QAbstractItemView {{ background: {t.RAISED}; color: {t.TEXT};
        selection-background-color: {t.ACCENT}; selection-color: {t.ON_ACCENT}; }}
    QTabWidget#SettingsTabs::pane {{ border: 1px solid {t.BORDER}; background: {t.SURFACE}; }}
    QTabWidget#SettingsTabs QTabBar::tab {{ background: {t.RAISED}; color: {t.SECONDARY};
        margin-right: 4px; padding: 9px 12px; border-bottom: 2px solid transparent; }}
    QTabWidget#SettingsTabs QTabBar::tab:selected {{ color: {t.TEXT};
        background: {t.SURFACE}; border-bottom-color: {t.ACCENT}; }}
    QTabWidget#SettingsTabs QTabBar::tab:focus {{ border-bottom-color: {t.MAGENTA}; }}
    QScrollArea {{ border: 0; }}
    """
