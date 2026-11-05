"""Convert the supplied PNG into a multi-size Windows ICO, without redesigning it."""
import struct
from pathlib import Path
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    source = QImage(str(ROOT / 'assets' / 'app.png'))
    if source.isNull():
        raise ValueError('assets/app.png could not be read')
    images = []
    sizes = (16, 24, 32, 48, 64, 128, 256)
    for size in sizes:
        scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        canvas = QImage(size, size, QImage.Format.Format_ARGB32)
        canvas.fill(Qt.GlobalColor.transparent)
        from PySide6.QtGui import QPainter
        painter = QPainter(canvas)
        painter.drawImage((size-scaled.width())//2, (size-scaled.height())//2, scaled)
        painter.end()
        array = QByteArray()
        buffer = QBuffer(array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not canvas.save(buffer, 'PNG'):
            raise RuntimeError('Cannot encode icon')
        images.append(bytes(array))
    offset = 6 + len(images)*16
    entries = []
    for size, payload in zip(sizes, images):
        entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(payload), offset))
        offset += len(payload)
    (ROOT / 'assets' / 'app.ico').write_bytes(struct.pack('<HHH', 0, 1, len(images)) + b''.join(entries) + b''.join(images))
    print('Created assets/app.ico (16 to 256 px)')


if __name__ == '__main__':
    prepare()
