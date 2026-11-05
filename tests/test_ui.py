import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QLineEdit, QLabel, QStyle, QStyleOptionFrame, QFileDialog
from PySide6.QtGui import QDesktopServices
from lexicards.storage import Store
from lexicards.ui import MainWindow, ImportDialog, CardsDialog
from lexicards.widgets import NameDialog, ConfirmDialog, DataDialog
from lexicards.theme import APPEARANCES


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.s = Store(Path(self.tmp.name) / 'test.db')
        self.d = self.s.create_deck('专业词汇')
        self.s.add_cards(self.d, [('飞行控制器', 'Flight Controller'), ('遥测', 'telemetry')])
        self.w = MainWindow(self.s)
        self.w.show()
        self.w.activateWindow()
        self.app.processEvents()

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()
        self.s.close()
        self.tmp.cleanup()

    def test_flip_answer_and_theme(self):
        self.assertFalse(self.w.learning.flipped)
        self.assertTrue(self.w.yes.isEnabled())
        QTest.mouseClick(self.w.yes, Qt.MouseButton.LeftButton)
        self.assertEqual(self.w.learning.state['index'], 1)
        self.assertTrue(self.w.yes.isEnabled())
        QTest.keyClick(self.w, Qt.Key.Key_Space)
        self.assertTrue(self.w.learning.flipped)
        QTest.keyClick(self.w, Qt.Key.Key_Right)
        self.assertEqual(self.w.learning.state['index'], 2)
        self.assertFalse(self.w.no.isEnabled())
        self.w.theme.setCurrentIndex(1)
        self.assertEqual(self.s.setting('appearance'), 'paper')
        self.assertEqual(self.w.no.text(), '再学')
        self.assertEqual(self.w.yes.text(), '已会')
        self.assertFalse(self.w.no.icon().isNull())

    def test_table_editor_text_and_copy_paste(self):
        dialog = ImportDialog(self.s, self.d, self.w)
        dialog.text.setPlainText('sky天\n跑run')
        dialog.parse()
        dialog.show()
        self.app.processEvents()
        table = dialog.preview
        table.setCurrentCell(0, 0)
        QTest.keyClick(table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.app.clipboard().text(), 'sky天')
        table.editItem(table.item(0, 0))
        self.app.processEvents()
        source_editor = table.findChild(QLineEdit, 'cellEditor')
        self.assertTrue(source_editor.isReadOnly())
        source_editor.setSelection(0, 3)
        QTest.keyClick(source_editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.app.clipboard().text(), 'sky')
        QTest.keyClicks(source_editor, 'overwrite')
        self.assertEqual(source_editor.text(), 'sky天')
        QTest.keyClick(source_editor, Qt.Key.Key_Return)
        self.app.sendPostedEvents(None, 0)
        self.app.processEvents()
        table.setCurrentCell(1, 1)
        table.editItem(table.item(1, 1))
        self.app.processEvents()
        editor = next(e for e in table.findChildren(QLineEdit, 'cellEditor') if e.isVisible())
        self.assertIsNotNone(editor)
        editor.setText('跑步')
        option = QStyleOptionFrame()
        editor.initStyleOption(option)
        text_rect = editor.style().subElementRect(QStyle.SubElement.SE_LineEditContents, option, editor)
        self.assertGreaterEqual(text_rect.height(), editor.fontMetrics().height())
        QTest.keyClick(editor, Qt.Key.Key_Return)
        table.setCurrentCell(1, 2)
        self.app.clipboard().setText('run')
        QTest.keyClick(table, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(table.item(1, 1).text(), '跑步')
        self.assertEqual(table.item(1, 2).text(), 'run')
        self.assertEqual(table.item(1, 3).text(), '可导入')
        table.setCurrentCell(0, 0)
        self.app.clipboard().setText('不可改写原始文本')
        table.paste_selection()
        self.assertEqual(table.item(0, 0).text(), 'sky天')
        dialog.close()
        dialog.deleteLater()

    def test_normal_ui_has_no_text_copy(self):
        word = self.w.word
        self.assertEqual(word.textInteractionFlags(), Qt.TextInteractionFlag.NoTextInteraction)
        self.assertEqual(self.w.title.textInteractionFlags(), Qt.TextInteractionFlag.NoTextInteraction)
        self.app.clipboard().setText('unchanged')
        QTest.keyClick(self.w, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.app.clipboard().text(), 'unchanged')
        QTest.mouseClick(word, Qt.MouseButton.LeftButton)
        self.assertTrue(self.w.learning.flipped, 'A click on the word must flip exactly once')
        dialog = CardsDialog(self.s, self.d, self.w)
        dialog.table.setCurrentCell(0, 0)
        QTest.keyClick(dialog.table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.app.clipboard().text(), 'unchanged')
        dialog.deleteLater()

    def test_delete_dialog_cancel_and_confirm(self):
        def cancel():
            dialog = self.app.activeModalWidget()
            self.assertIsInstance(dialog, ConfirmDialog)
            self.assertGreaterEqual(dialog.width(), 460)
            self.assertTrue(dialog.message.wordWrap())
            QTest.mouseClick(dialog.cancel_button, Qt.MouseButton.LeftButton)
        QTimer.singleShot(40, cancel)
        self.w.delete_deck()
        self.assertEqual(len(self.s.decks()), 1)
        def confirm():
            dialog = self.app.activeModalWidget()
            QTest.mouseClick(dialog.confirm_button, Qt.MouseButton.LeftButton)
        QTimer.singleShot(40, confirm)
        self.w.delete_deck()
        self.assertEqual(len(self.s.decks()), 0)
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM cards').fetchone()[0], 0)

    def test_legacy_dark_setting_does_not_enable_dark_mode(self):
        self.s.set_setting('dark', '1')
        self.w.close()
        self.w.deleteLater()
        self.w = MainWindow(self.s)
        self.assertEqual([self.w.theme.itemText(i) for i in range(self.w.theme.count())], [name for key, name in APPEARANCES])
        self.assertEqual(self.w.theme.count(), 7)
        for i in range(self.w.theme.count()):
            self.w.theme.setCurrentIndex(i)
            self.assertGreater(self.w.palette().color(self.w.backgroundRole()).lightness(), 220)

    def test_preview_correction_dedup_and_commit(self):
        dialog = ImportDialog(self.s, self.d, self.w)
        dialog.text.setPlainText('遥测 telemetry\n轨迹规划 trajectory planning\n需要人工修改')
        dialog.parse()
        self.assertEqual(dialog.preview.item(0, 3).text(), '重复')
        self.assertEqual(dialog.preview.item(2, 3).text(), '待修正')
        dialog.preview.item(2, 1).setText('自动驾驶')
        dialog.preview.item(2, 2).setText('autopilot')
        self.assertEqual(dialog.preview.item(2, 3).text(), '可导入')
        with patch.object(QMessageBox, 'information'):
            dialog.commit()
        self.assertEqual(len(self.s.cards(self.d)), 4)
        dialog.deleteLater()

    def test_manage_edit(self):
        dialog = CardsDialog(self.s, self.d, self.w)
        ident = dialog.rows[0]['id']
        dialog.table.setCurrentCell(0, 0)
        dialog.table.item(0, 0).setText('控制器')
        dialog.save()
        row = self.s.db.execute('SELECT chinese FROM cards WHERE id=?', (ident,)).fetchone()
        self.assertEqual(row[0], '控制器')
        dialog.deleteLater()

    def test_data_dialog_shows_actual_database_and_opens_folder(self):
        dialog = DataDialog(self.w, self.s.path)
        self.assertEqual(dialog.path_field.text(), str(self.s.path.resolve()))
        self.assertTrue(dialog.path_field.isReadOnly())
        with patch.object(QDesktopServices, 'openUrl', return_value=True) as open_url:
            QTest.mouseClick(dialog.open_button, Qt.MouseButton.LeftButton)
            self.assertEqual(open_url.call_args.args[0].toLocalFile(), str(self.s.path.parent.resolve()).replace('\\', '/'))
        dialog.deleteLater()

    def test_data_dialog_can_export_complete_backup_and_route_restore(self):
        import json
        backup = Path(self.tmp.name) / 'Lexivane-backup.json'
        QTimer.singleShot(50, lambda: self.app.activeModalWidget().backup_button.click())
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(backup), 'JSON (*.json)')), \
             patch.object(QMessageBox, 'information'):
            self.w.data_settings()
        data = json.loads(backup.read_text(encoding='utf-8'))
        self.s.validate_backup(data)
        self.assertEqual((len(data['decks']), len(data['cards'])), (1, 2))
        self.assertTrue(data['sessions'])
        QTimer.singleShot(50, lambda: self.app.activeModalWidget().restore_button.click())
        with patch.object(self.w, 'restore') as restore:
            self.w.data_settings()
            restore.assert_called_once()

    def test_missed_words_continue_automatically_and_full_restart(self):
        missed = self.w.learning.current()['id']
        self.w.answer(False)
        self.w.answer(True)
        self.assertEqual(self.w.learning.state['pass_number'], 2)
        self.assertEqual(self.w.learning.current()['id'], missed)
        self.assertIn('巩固', self.w.side_label.text())
        self.assertTrue(self.w.yes.isEnabled())
        self.assertEqual(self.w.progress.value(), 1)
        self.w.answer(True)
        self.assertIsNone(self.w.learning.current())
        self.assertIn('已掌握', self.w.word.text())
        self.assertFalse(self.w.no.isEnabled())
        self.w.restart()
        self.assertEqual(len(self.w.learning.state['queue']), 2)
        self.assertEqual(self.w.learning.state['mastered'], 0)

    def test_restart_during_consolidation_can_cancel_or_reset(self):
        self.w.answer(False)
        self.w.answer(True)
        previous = dict(self.w.learning.state)
        with patch.object(ConfirmDialog, 'ask', return_value=False) as confirm:
            self.w.restart()
            confirm.assert_called_once()
        self.assertEqual(self.w.learning.state, previous)
        with patch.object(ConfirmDialog, 'ask', return_value=True):
            self.w.restart()
        self.assertEqual((self.w.learning.state['pass_number'], len(self.w.learning.state['queue'])), (1, 2))
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0], 2)

    def test_new_deck_dialog_has_space_and_saves(self):
        def fill_dialog():
            dialog = self.app.activeModalWidget()
            self.assertIsInstance(dialog, NameDialog)
            self.assertGreaterEqual(dialog.width(), 440)
            self.assertIn('新建词库', dialog.windowTitle())
            self.assertEqual(dialog.cancel_button.text(), '取消')
            dialog.input.setText('新的研究词库')
            QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
        QTimer.singleShot(50, fill_dialog)
        self.w.new_deck()
        self.assertEqual(self.w.title.text(), '新的研究词库')
        self.assertEqual(len(self.s.decks()), 2)
