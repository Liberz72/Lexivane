"""Small reusable presentation components; no storage or learning rules."""
from PySide6.QtCore import Qt, QSize, Signal, QUrl
from PySide6.QtGui import QPainter, QPalette, QKeySequence, QIcon, QPixmap, QPen, QColor, QPainterPath, QDesktopServices
from PySide6.QtWidgets import (QWidget, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QApplication, QTableWidget, QStyledItemDelegate, QComboBox,
    QStylePainter, QStyleOptionComboBox, QStyle)
from pathlib import Path


def caption(text, name='muted'):
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def line_icon(kind, color):
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    path = QPainterPath()
    if kind == 'check':
        path.moveTo(4, 10)
        path.lineTo(8, 14)
        path.lineTo(16, 6)
    else:
        path.moveTo(4, 8)
        path.cubicTo(6, 2, 16, 3, 17, 9)
        path.cubicTo(19, 16, 10, 20, 5, 15)
        path.moveTo(4, 3)
        path.lineTo(4, 8)
        path.lineTo(9, 8)
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


class FlipCard(QFrame):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class CellEditorDelegate(QStyledItemDelegate):
    def __init__(self, parent, source_column=None):
        super().__init__(parent)
        self.source_column = source_column

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setObjectName('cellEditor')
        if index.column() == self.source_column:
            editor.setReadOnly(True)
            editor.setToolTip('拖选原始文本中的词汇，按 Ctrl+C 复制')
        editor.setFrame(False)
        editor.setTextMargins(0, 0, 0, 0)
        return editor

    def setModelData(self, editor, model, index):
        if index.column() != self.source_column:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        # Use the whole row height; standalone-field padding must not crop text.
        editor.setGeometry(option.rect.adjusted(3, 3, -3, -3))


class VocabularyTable(QTableWidget):
    def __init__(self, rows, columns, source_column=None):
        super().__init__(rows, columns)
        self.source_column = source_column
        self.setItemDelegate(CellEditorDelegate(self, source_column))

    def copy_source(self):
        item = self.currentItem()
        if item and self.currentColumn() == self.source_column:
            QApplication.clipboard().setText(item.text())

    def paste_selection(self):
        row, column = self.currentRow(), self.currentColumn()
        if row < 0 or column < 0:
            return
        for dr, line in enumerate(QApplication.clipboard().text().splitlines()):
            for dc, value in enumerate(line.split('\t')):
                item = self.item(row+dr, column+dc)
                if item and column+dc != self.source_column and item.flags() & Qt.ItemFlag.ItemIsEditable:
                    item.setText(value)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_source()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.paste_selection()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid() and index.column() == self.source_column:
            self.setCurrentIndex(index)
            self.edit(index)
        else:
            event.accept()


class CenteredComboBox(QComboBox):
    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.setPen(self.palette().color(QPalette.ColorRole.ButtonText))
        painter.drawText(self.rect().adjusted(30, 0, -30, 0), Qt.AlignmentFlag.AlignCenter, self.currentText())


class ConfirmDialog(QDialog):
    def __init__(self, parent, title, message, confirm_text='确认删除', danger=True):
        super().__init__(parent)
        self.setWindowTitle(title + ' · Lexivane')
        self.setMinimumWidth(460)
        self.resize(480, 280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(16)
        layout.addWidget(caption(title, 'dialogHeading'))
        self.message = caption(message, 'bodyText')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        layout.addStretch()
        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch()
        self.cancel_button = QPushButton('取消')
        self.cancel_button.setDefault(True)
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        self.confirm_button = QPushButton(confirm_text)
        self.confirm_button.setObjectName('danger' if danger else 'primary')
        self.confirm_button.setMinimumWidth(110)
        self.confirm_button.clicked.connect(self.accept)
        actions.addWidget(self.confirm_button)
        layout.addLayout(actions)
        self.cancel_button.setFocus()

    @classmethod
    def ask(cls, parent, title, message, confirm_text='确认删除', danger=True):
        return cls(parent, title, message, confirm_text, danger).exec() == QDialog.DialogCode.Accepted


class DataDialog(QDialog):
    BACKUP = 10
    RESTORE = 11

    def __init__(self, parent, database_path):
        super().__init__(parent)
        self.database_path = Path(database_path).resolve()
        self.setWindowTitle('数据与备份 · Lexivane')
        self.setMinimumWidth(560)
        self.resize(620, 410)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)
        layout.addWidget(caption('数据与备份', 'dialogHeading'))
        layout.addWidget(caption('词库、单词与学习进度都保存在本机。'))
        layout.addSpacing(4)
        layout.addWidget(caption('当前数据库文件', 'deckName'))
        self.path_field = QLineEdit(str(self.database_path))
        self.path_field.setReadOnly(True)
        self.path_field.setCursorPosition(0)
        self.path_field.setToolTip(str(self.database_path))
        layout.addWidget(self.path_field)
        open_row = QHBoxLayout()
        self.open_button = QPushButton('打开所在文件夹')
        self.open_button.clicked.connect(self.open_folder)
        open_row.addWidget(self.open_button)
        open_row.addStretch()
        layout.addLayout(open_row)
        detail = caption('更新或移动 exe 不会删除这里的数据。此目录独立于软件的临时解压目录。')
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addSpacing(6)
        layout.addWidget(caption('为词库保留一份独立备份', 'deckName'))
        detail = caption('完整备份包含全部词库、学习记录和巩固进度。建议保存在另一个文件夹或磁盘，避免和原数据一起误删。')
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addStretch()
        actions = QHBoxLayout()
        actions.setSpacing(10)
        close_button = QPushButton('关闭')
        close_button.clicked.connect(self.reject)
        actions.addWidget(close_button)
        actions.addStretch()
        self.restore_button = QPushButton('从备份恢复')
        self.restore_button.clicked.connect(lambda: self.done(self.RESTORE))
        actions.addWidget(self.restore_button)
        self.backup_button = QPushButton('导出完整备份')
        self.backup_button.setObjectName('primary')
        self.backup_button.clicked.connect(lambda: self.done(self.BACKUP))
        actions.addWidget(self.backup_button)
        layout.addLayout(actions)

    def open_folder(self):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.database_path.parent))):
            self.open_button.setText('无法打开，请复制上方路径')


class ElidedLabel(QLabel):
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.contentsRect().width())
        painter.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)


class DeckRow(QWidget):
    def __init__(self, name, count):
        super().__init__()
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 12, 12)
        layout.setSpacing(8)
        self.label = ElidedLabel(name)
        self.label.setObjectName('deckName')
        self.label.setMinimumWidth(0)
        layout.addWidget(self.label, 1)
        layout.addWidget(caption(str(count), 'deckCount'))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def sizeHint(self):
        return QSize(180, 54)


class NameDialog(QDialog):
    def __init__(self, parent, title='新建词库', text=''):
        super().__init__(parent)
        self.setWindowTitle(title + ' · Lexivane')
        self.setMinimumSize(440, 260)
        self.resize(460, 280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)
        layout.addWidget(caption(title, 'dialogHeading'))
        layout.addWidget(caption('为这一组词汇取一个容易找到的名字。'))
        layout.addSpacing(8)
        layout.addWidget(caption('词库名称'))
        self.input = QLineEdit(text)
        self.input.setPlaceholderText('例如：科研英语、日常表达')
        self.input.setMaxLength(100)
        self.input.setMinimumHeight(24)
        self.input.selectAll()
        layout.addWidget(self.input)
        layout.addStretch()
        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch()
        self.cancel_button = QPushButton('取消')
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        self.save_button = QPushButton('保存名称' if text else '创建词库')
        self.save_button.setObjectName('primary')
        self.save_button.setMinimumWidth(110)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.accept)
        self.input.textChanged.connect(lambda value: self.save_button.setEnabled(bool(value.strip())))
        self.save_button.setEnabled(bool(text.strip()))
        self.input.returnPressed.connect(lambda: self.accept() if self.input.text().strip() else None)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.input.setFocus()

    @classmethod
    def ask(cls, parent, title='新建词库', text=''):
        dialog = cls(parent, title, text)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.input.text().strip(), accepted
