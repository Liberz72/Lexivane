"""Render reproducible UI screenshots with isolated example data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtTest import QTest
from lexicards.storage import Store
from lexicards.ui import MainWindow, ImportDialog, CardsDialog
from lexicards.widgets import NameDialog, ConfirmDialog, DataDialog
from lexicards.theme import APPEARANCES


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'smoke-results' / ('ui-review-' + (sys.argv[1] if len(sys.argv) > 1 else '100'))
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle('Fusion')
    app.setWindowIcon(QIcon(str(root / 'assets' / 'app.ico')))
    store = Store(output / 'preview.sqlite3')
    if not store.decks():
        for name in ('科研英语', '无人飞行器专业词汇', '日常表达'):
            deck = store.create_deck(name)
            store.add_cards(deck, [('轨迹规划', 'trajectory planning'), ('鲁棒控制', 'robust control'), ('自主导航', 'autonomous navigation')])
    window = MainWindow(store)
    window.refresh(store.decks()[0]['id'])
    window.learning.start(shuffle=False)
    window.render()

    def capture(widget, name):
        widget.show()
        widget.activateWindow()
        app.processEvents()
        QTest.qWait(200)
        assert widget.grab().save(str(output / (name + '.png')))

    capture(window, 'main-light')
    word_rect = QRect(window.word.mapTo(window.card, QPoint()), window.word.size())
    assert window.card.rect().contains(word_rect), 'Word outside card'
    assert window.word.height() >= window.word.fontMetrics().height(), 'Word vertically clipped'
    window.resize(920, 640)
    capture(window, 'main-compact')
    assert window.yes.isVisible() and window.no.isVisible()
    window.resize(1180, 800)
    data_dialog = DataDialog(window, store.path)
    capture(data_dialog, 'data-and-backup')
    data_dialog.close()
    window.answer(False)
    window.answer(True)
    window.answer(True)
    assert window.learning.state['pass_number'] == 2
    capture(window, 'consolidation')
    window.answer(True)
    assert window.learning.current() is None
    capture(window, 'mastered')
    window.restart()
    dialog = NameDialog(window)
    capture(dialog, 'new-deck')
    assert dialog.width() >= 440
    dialog.close()
    dialog = ImportDialog(store, window.deck_id, window)
    dialog.text.setPlainText('无人机 Unmanned Aerial Vehicle\ntelemetry 遥测\n跑run')
    dialog.parse()
    capture(dialog, 'import')
    dialog.preview.setCurrentCell(2, 1)
    dialog.preview.editItem(dialog.preview.item(2, 1))
    app.processEvents()
    editor = dialog.preview.findChild(QLineEdit, 'cellEditor')
    editor.setText('跑步')
    editor.deselect()
    capture(dialog, 'import-editing')
    QTest.keyClick(editor, Qt.Key.Key_Return)
    dialog.preview.setCurrentCell(2, 0)
    dialog.preview.editItem(dialog.preview.item(2, 0))
    app.processEvents()
    source_editor = next(e for e in dialog.preview.findChildren(QLineEdit, 'cellEditor') if e.isVisible())
    source_editor.setSelection(1, 3)
    assert source_editor.isReadOnly()
    capture(dialog, 'source-copy-selection')
    dialog.close()
    dialog = CardsDialog(store, window.deck_id, window)
    capture(dialog, 'cards')
    dialog.close()
    dialog = ConfirmDialog(window, '删除词库', '确定删除「无人飞行器专业词汇」吗？\n\n词库中的词条和学习记录将一并删除。\n此操作无法撤销，建议先备份。', '删除词库')
    capture(dialog, 'delete-deck')
    dialog.close()
    for i, (name, label) in enumerate(APPEARANCES):
        window.theme.setCurrentIndex(i)
        capture(window, 'appearance-' + name)
    window.close()
    store.close()
    print('Visual checks passed:', output)


if __name__ == '__main__':
    main()
