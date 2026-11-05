import os
import sys
import traceback
from pathlib import Path
from PySide6.QtCore import QLockFile, QTimer, QTranslator, QLibraryInfo
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from lexicards.storage import Store, atomic_json
from lexicards.ui import MainWindow


def data_dir(development=False):
    # Never use executable location or PyInstaller's extraction directory.
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / ('LexiCards-dev' if development else 'LexiCards')


def main():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Lexivane.Desktop')
    app = QApplication(sys.argv)
    app.setApplicationName('Lexivane')
    app.setOrganizationName('Lexivane')
    app.setStyle('Fusion')
    translator = QTranslator(app)
    if translator.load('qtbase_zh_CN', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    app.setFont(QFont('Microsoft YaHei UI', 10))
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / 'assets' / 'app.ico')))
    smoke = '--smoke-test' in sys.argv
    development = '--dev' in sys.argv and not getattr(sys, 'frozen', False)
    directory = Path(sys.argv[sys.argv.index('--smoke-test')+1]).resolve() if smoke else data_dir(development)
    directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(directory / 'app.lock'))
    if not lock.tryLock(100):
        QMessageBox.information(None, 'Lexivane', 'Lexivane 已在运行，请切换到现有窗口。')
        return 0

    def error_hook(kind, value, tb):
        detail = ''.join(traceback.format_exception(kind, value, tb))
        with (directory / 'error.log').open('a', encoding='utf-8') as f:
            f.write(detail + '\n')
        QMessageBox.critical(None, '操作未完成', f'{value}\n\n详细日志：{directory / "error.log"}')
    sys.excepthook = error_hook
    store = Store(directory / 'lexicards.sqlite3')
    window = MainWindow(store)
    if development:
        window.setWindowTitle('Lexivane · 开发预览')
        stop_path = os.environ.get('LEXICARDS_DEV_STOP_FILE')
        if stop_path:
            stop_timer = QTimer(app)
            stop_timer.timeout.connect(lambda: app.quit() if Path(stop_path).exists() else None)
            stop_timer.start(200)
    window.show()
    if smoke:
        def check():
            try:
                deck = next(iter(store.decks()), None)
                ident = deck['id'] if deck else store.create_deck('打包验证')
                store.add_cards(ident, [('飞行控制器', 'Flight Controller'), ('遥测', 'telemetry')])
                window.refresh(ident)
                window.learning.start(shuffle=False)
                assert window.yes.isEnabled() and window.no.isEnabled()
                missed = window.learning.current()['id']
                window.answer(False)
                window.answer(True)
                assert window.learning.state['pass_number'] == 2
                assert window.learning.current()['id'] == missed
                window.answer(True)
                assert window.learning.current() is None
                assert window.learning.remaining == 0
                store.backup(directory / 'smoke-backup.json')
                assert not app.windowIcon().isNull(), 'Application icon missing'
                app.processEvents()
                atomic_json(directory / 'smoke-result.json', {'ok': True, 'cards': len(store.cards(ident)), 'reviews': store.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0], 'frozen': bool(getattr(sys, 'frozen', False)), 'icon_loaded': not app.windowIcon().isNull(), 'training_passes': window.learning.state['pass_number'], 'mastered': window.learning.state['mastered'], 'remaining': window.learning.remaining})
                window.grab().save(str(directory / 'window.png'))
                app.exit(0)
            except Exception:
                atomic_json(directory / 'smoke-result.json', {'ok': False, 'error': traceback.format_exc()})
                app.exit(1)
        QTimer.singleShot(500, check)
    result = app.exec()
    store.close()
    lock.unlock()
    return result


if __name__ == '__main__':
    sys.exit(main())
