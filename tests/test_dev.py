import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import dev
from main import data_dir


class DevelopmentTests(unittest.TestCase):
    def test_watcher_restarts_and_closes_child(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root / 'lexicards').mkdir()
            (root / 'assets').mkdir()
            source = root / 'lexicards' / 'ui.py'
            source.write_text('# original', encoding='utf-8')
            (root / 'main.py').write_text(
                'import os,time\nfrom pathlib import Path\n'
                'while not Path(os.environ["LEXICARDS_DEV_STOP_FILE"]).exists(): time.sleep(0.05)\n', encoding='utf-8')
            pids = []
            started = threading.Event()

            def observer(pid):
                pids.append(pid)
                started.set()

            def edit():
                if started.wait(5):
                    source.write_text('# changed content', encoding='utf-8')

            editor = threading.Thread(target=edit)
            editor.start()
            deadline = time.monotonic() + 12
            with patch.object(dev, 'ROOT', root):
                dev.watch(root / 'stop', observer, lambda: len(pids) == 2 or time.monotonic() > deadline)
            editor.join()
            self.assertEqual(len(pids), 2)
            self.assertNotEqual(pids[0], pids[1])
            self.assertFalse((root / 'stop').exists())

    def test_development_uses_separate_data_and_exits_gracefully(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            stop = root / 'stop'
            env = dict(os.environ, LOCALAPPDATA=str(root), LEXICARDS_DEV_STOP_FILE=str(stop), QT_QPA_PLATFORM='offscreen')
            with patch.dict(os.environ, {'LOCALAPPDATA': str(root)}):
                self.assertEqual(data_dir(), root / 'LexiCards')
                self.assertEqual(data_dir(True), root / 'LexiCards-dev')
            process = subprocess.Popen([sys.executable, 'main.py', '--dev'], env=env, cwd=Path(__file__).resolve().parents[1])
            try:
                deadline = time.monotonic() + 8
                db = root / 'LexiCards-dev' / 'lexicards.sqlite3'
                while not db.exists() and time.monotonic() < deadline and process.poll() is None:
                    time.sleep(0.1)
                self.assertTrue(db.exists())
                self.assertFalse((root / 'LexiCards').exists())
                stop.touch()
                self.assertEqual(process.wait(timeout=8), 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
