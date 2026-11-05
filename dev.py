"""Save-to-restart desktop preview using only the Python standard library."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def snapshot():
    paths = [ROOT / 'main.py', *sorted((ROOT / 'lexicards').rglob('*.py'))]
    paths += sorted(p for p in (ROOT / 'assets').rglob('*') if p.is_file())
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.exists())


def stop_process(process, stop_file):
    if process.poll() is None:
        stop_file.touch()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
    stop_file.unlink(missing_ok=True)


def watch(stop_file, observer=None, should_stop=lambda: False):
    env = dict(os.environ, LEXICARDS_DEV_STOP_FILE=str(stop_file))
    command = [sys.executable, str(ROOT / 'main.py'), '--dev']

    def start():
        process = subprocess.Popen(command, cwd=ROOT, env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0)
        print(f'Preview started: PID {process.pid}', flush=True)
        if observer:
            observer(process.pid)
        return process

    previous = snapshot()
    process = start()
    try:
        while not should_stop():
            time.sleep(0.25)
            current = snapshot()
            if current != previous:
                # Wait for editor writes to settle before restarting.
                time.sleep(0.6)
                previous = snapshot()
                stop_process(process, stop_file)
                print('Saved changes detected. Restarting preview...', flush=True)
                process = start()
    finally:
        stop_process(process, stop_file)


def main():
    print('Lexivane development preview. Save source files to restart. Ctrl+C to stop.', flush=True)
    print('Data: %LOCALAPPDATA%\\LexiCards-dev (separate from your real vocabulary).', flush=True)
    with tempfile.TemporaryDirectory(prefix='lexicards-dev-') as directory:
        try:
            watch(Path(directory) / 'stop')
        except KeyboardInterrupt:
            print('\nPreview stopped.', flush=True)


if __name__ == '__main__':
    main()
