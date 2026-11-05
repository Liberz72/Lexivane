"""Shared visual language for the main window and all child dialogs."""
from pathlib import Path
from PySide6.QtGui import QColor, QPalette

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
APPEARANCES = [('lavender', '柔雾紫'), ('paper', '纸页白'), ('sage', '浅茶绿'),
               ('sky', '晴空蓝'), ('rose', '樱花粉'), ('peach', '杏子橙'), ('slate', '雾石灰')]


def apply_theme(window, appearance='lavender'):
    colors = dict(bg='#F6F7FB', sidebar='#FFFFFF', surface='#FFFFFF', text='#252638',
                  muted='#858699', line='#E7E8F0', hover='#F0F0F9', selected='#EEEDFB',
                  accent='#7160D5', accent_hover='#6150C4', soft='#F4F2FF', field='#FAFAFD',
                  disabled='#B0B1C0', inverse='#FFFFFF')
    if appearance == 'paper':
        colors.update(bg='#F7F6F3', text='#35343C', muted='#817E87', line='#E9E6E1',
                      hover='#F1EEEA', selected='#EFEBF4', accent='#857298', accent_hover='#746185',
                      soft='#F4EFF8', field='#FCFBF9')
    elif appearance == 'sage':
        colors.update(bg='#F4F8F6', text='#2D3A35', muted='#7B8C83', line='#E0EAE4',
                      hover='#EDF3EF', selected='#E5F0E9', accent='#638975', accent_hover='#527A64',
                      soft='#ECF5EF', field='#F9FCFA')
    elif appearance == 'sky':
        colors.update(bg='#F3F7FC', text='#2D3B50', muted='#7B8BA3', line='#DFE7F1',
                      hover='#EDF2F9', selected='#E4EDF9', accent='#6389B9', accent_hover='#5077A6',
                      soft='#EBF2FC', field='#F8FAFE')
    elif appearance == 'rose':
        colors.update(bg='#FCF5F7', text='#47323F', muted='#9A7F8D', line='#F0E1E7',
                      hover='#F8EDF2', selected='#F6E6EE', accent='#B57896', accent_hover='#A26684',
                      soft='#FBEFF5', field='#FEFAFC')
    elif appearance == 'peach':
        colors.update(bg='#FCF7F2', text='#4B3A30', muted='#9B897B', line='#EFE4D9',
                      hover='#F8EFE5', selected='#F6E9DA', accent='#B88A62', accent_hover='#A37650',
                      soft='#FBF1E7', field='#FEFCF9')
    elif appearance == 'slate':
        colors.update(bg='#F5F6F8', text='#303743', muted='#808995', line='#E2E5EA',
                      hover='#EDF0F4', selected='#E7EBF1', accent='#78879D', accent_hover='#65758C',
                      soft='#EEF1F6', field='#FAFBFC')
    c = colors
    palette = window.palette()
    for role, key in [(QPalette.ColorRole.Window, 'bg'), (QPalette.ColorRole.WindowText, 'text'),
                      (QPalette.ColorRole.Base, 'surface'), (QPalette.ColorRole.AlternateBase, 'field'),
                      (QPalette.ColorRole.Text, 'text'), (QPalette.ColorRole.Button, 'surface'),
                      (QPalette.ColorRole.ButtonText, 'text'), (QPalette.ColorRole.Highlight, 'accent'),
                      (QPalette.ColorRole.HighlightedText, 'inverse'), (QPalette.ColorRole.ToolTipBase, 'surface'),
                      (QPalette.ColorRole.ToolTipText, 'text')]:
        palette.setColor(role, QColor(c[key]))
    window.setPalette(palette)
    arrow = (ASSETS / 'chevron-light.svg').as_posix()
    check = (ASSETS / 'check-light.svg').as_posix()
    window.setStyleSheet(f'''
    QWidget {{color:{c['text']};font-family:"Segoe UI","Microsoft YaHei UI";font-size:13px;}}
    QMainWindow,QDialog {{background:{c['bg']};}}
    QLabel {{background:transparent;border:0;}}
    QFrame#sidebar {{background:{c['sidebar']};border:0;border-right:1px solid {c['line']};}}
    QLabel#brand {{font-family:Georgia;font-size:28px;font-weight:700;letter-spacing:-1px;}}
    QLabel#brandMark {{background:transparent;}}
    QLabel#bodyText {{font-size:14px;}}
    QLabel#eyebrow {{color:{c['muted']};font-size:11px;letter-spacing:2px;}}
    QLabel#heading {{font-size:27px;font-weight:600;}}
    QLabel#dialogHeading {{font-size:22px;font-weight:600;}}
    QLabel#muted,QLabel#cardHint {{color:{c['muted']};font-size:12px;}}
    QLabel#deckCount,QLabel#countBadge {{color:{c['muted']};background:{c['hover']};border-radius:8px;padding:3px 8px;font-size:11px;}}
    QLabel#deckName {{font-size:14px;font-weight:500;}}
    QLabel#sideLabel {{color:{c['accent']};background:{c['soft']};border-radius:9px;padding:6px 12px;font-size:12px;}}
    QLabel#word {{font-size:40px;font-weight:500;}}
    QPushButton {{background:{c['surface']};border:1px solid {c['line']};border-radius:10px;padding:10px 16px;font-weight:500;}}
    QPushButton:hover {{background:{c['hover']};border-color:{c['line']};}}
    QPushButton:pressed {{background:{c['selected']};}}
    QPushButton:focus {{border-color:{c['accent']};}}
    QPushButton:disabled {{color:{c['disabled']};background:{c['field']};border-color:{c['line']};}}
    QPushButton#primary {{background:{c['accent']};color:{c['inverse']};border:1px solid {c['accent']};}}
    QPushButton#primary:hover {{background:{c['accent_hover']};border-color:{c['accent_hover']};}}
    QPushButton#primary:disabled {{background:{c['hover']};color:{c['disabled']};border-color:{c['line']};}}
    QPushButton#soft {{background:{c['soft']};color:{c['accent']};border:1px solid {c['soft']};}}
    QPushButton#soft:hover {{background:{c['selected']};}}
    QPushButton#quiet {{background:transparent;border:1px solid transparent;color:{c['muted']};}}
    QPushButton#quiet:hover {{background:{c['hover']};color:{c['text']};}}
    QPushButton#danger {{background:#BB5369;color:white;border:1px solid #BB5369;}}
    QPushButton#danger:hover {{background:#A9455A;border-color:#A9455A;}}
    QPushButton#answerNo {{font-size:15px;}}
    QPushButton#primary[answer="true"] {{font-size:15px;}}
    QFrame#card {{background:{c['surface']};border:1px solid {c['line']};border-radius:22px;color:{c['text']};}}
    QFrame#options {{background:{c['surface']};border:1px solid {c['line']};border-radius:12px;}}
    QComboBox {{background:{c['surface']};border:1px solid {c['line']};border-radius:9px;padding:9px 34px 9px 12px;min-height:18px;}}
    QComboBox:hover,QComboBox:focus {{border-color:{c['accent']};}}
    QComboBox#appearance {{padding:9px 30px;}}
    QComboBox::drop-down {{subcontrol-origin:padding;subcontrol-position:top right;width:30px;border:0;}}
    QComboBox::down-arrow {{image:url("{arrow}");width:12px;height:12px;}}
    QComboBox QAbstractItemView {{background:{c['surface']};border:1px solid {c['line']};padding:6px;selection-background-color:{c['selected']};selection-color:{c['text']};outline:0;}}
    QComboBox QAbstractItemView::item {{min-height:30px;}}
    QCheckBox {{spacing:8px;}}
    QCheckBox::indicator {{width:16px;height:16px;border:1px solid {c['line']};border-radius:5px;background:{c['surface']};}}
    QCheckBox::indicator:hover {{border-color:{c['accent']};}}
    QCheckBox::indicator:checked {{background:{c['accent']};border-color:{c['accent']};image:url("{check}");}}
    QListWidget {{background:transparent;border:0;outline:0;padding:0;}}
    QListWidget::item {{border-radius:10px;margin:3px 0;}}
    QListWidget::item:selected {{background:{c['selected']};}}
    QListWidget::item:hover:!selected {{background:{c['field']};}}
    QLineEdit,QPlainTextEdit {{background:{c['surface']};border:1px solid {c['line']};border-radius:10px;padding:12px;selection-background-color:{c['accent']};selection-color:{c['inverse']};}}
    QLineEdit:focus,QPlainTextEdit:focus {{border:1px solid {c['accent']};}}
    QTableWidget QLineEdit#cellEditor {{background:{c['surface']};color:{c['text']};padding:0 8px;min-height:0;min-width:0;border:1px solid {c['accent']};border-radius:6px;selection-background-color:{c['accent']};selection-color:{c['inverse']};}}
    QTableWidget {{background:{c['surface']};alternate-background-color:{c['field']};border:1px solid {c['line']};border-radius:10px;gridline-color:{c['line']};selection-background-color:{c['selected']};selection-color:{c['text']};outline:0;}}
    QTableWidget::item {{padding:8px;border:0;}}
    QHeaderView::section {{background:{c['field']};color:{c['muted']};padding:12px 8px;border:0;border-bottom:1px solid {c['line']};font-size:12px;}}
    QProgressBar {{background:{c['line']};border:0;border-radius:3px;}}
    QProgressBar::chunk {{background:{c['accent']};border-radius:3px;}}
    QMenu {{background:{c['surface']};border:1px solid {c['line']};border-radius:8px;padding:6px;}}
    QMenu::item {{padding:9px 24px;border-radius:5px;}} QMenu::item:selected {{background:{c['selected']};}}
    QToolTip {{background:{c['surface']};color:{c['text']};border:1px solid {c['line']};padding:8px;}}
    QMessageBox QLabel#qt_msgbox_label {{min-width:300px;font-size:14px;}}
    QScrollBar:vertical {{background:transparent;width:8px;margin:4px 1px;}}
    QScrollBar::handle:vertical {{background:{c['line']};border-radius:3px;min-height:28px;}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
    QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:transparent;}}
    ''')
    return colors

