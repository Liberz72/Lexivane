from pathlib import Path
import sqlite3
from PySide6.QtCore import Qt, QPropertyAnimation, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QComboBox, QCheckBox, QProgressBar,
    QDialog, QPlainTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QAbstractItemView, QMenu, QFrame, QLineEdit, QGraphicsOpacityEffect, QSizePolicy, QApplication)
from .parser import parse_text, normalize, valid_pair
from .learning import Learning
from .theme import apply_theme, APPEARANCES, ASSETS
from .widgets import (caption, NameDialog, DeckRow, ElidedLabel, VocabularyTable,
                      FlipCard, ConfirmDialog, CenteredComboBox, DataDialog, line_icon)


def button(text, callback, layout=None):
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(callback)
    if layout:
        layout.addWidget(b)
    return b


def table(headers, source_column=None):
    t = VocabularyTable(0, len(headers), source_column)
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().hide()
    t.verticalHeader().setDefaultSectionSize(44)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    return t


class ImportDialog(QDialog):
    def __init__(self, store, selected, parent):
        super().__init__(parent)
        self.store = store
        self.existing_keys = {}
        self.setWindowTitle('导入词汇 · Lexivane')
        self.setMinimumSize(780, 620)
        self.resize(920, 730)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(caption('把词汇放进你的词库', 'dialogHeading'))
        layout.addWidget(caption('粘贴、检查，然后开始记忆。'))
        top = QHBoxLayout()
        top.addWidget(QLabel('导入到'))
        self.deck = QComboBox()
        for d in store.decks():
            self.deck.addItem(d['name'], d['id'])
        self.deck.setCurrentIndex(max(0, self.deck.findData(selected)))
        top.addWidget(self.deck, 1)
        button('新建词库', self.new_deck, top)
        layout.addLayout(top)
        layout.addWidget(caption('每行一对中英文，支持空格、Tab、冒号、逗号或等号分隔。'))
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText('飞行控制器 Flight Controller\nautopilot 自动驾驶\nrobust control：鲁棒控制')
        self.text.setMaximumHeight(130)
        self.text.setMinimumHeight(100)
        self.text.textChanged.connect(self.invalidate)
        layout.addWidget(self.text)
        button('解析预览', self.parse, layout)
        self.preview = table(['原始文本（双击选词）', '中文（可修改）', '英文（可修改）', '状态'], source_column=0)
        self.preview.itemChanged.connect(self.validate)
        self.deck.currentIndexChanged.connect(self.validate)
        layout.addWidget(self.preview, 1)
        self.summary = QLabel('先解析，再检查预览。待修正行不会写入。')
        layout.addWidget(self.summary)
        bottom = QHBoxLayout()
        button('删除选中行', self.remove, bottom)
        bottom.addStretch()
        button('取消', self.reject, bottom)
        self.confirm = button('确认导入', self.commit, bottom)
        self.confirm.setObjectName('primary')
        self.confirm.setEnabled(False)
        layout.addLayout(bottom)

    def new_deck(self):
        name, ok = NameDialog.ask(self)
        if ok:
            try:
                ident = self.store.create_deck(name)
                self.deck.addItem(name.strip(), ident)
                self.deck.setCurrentIndex(self.deck.count()-1)
            except (ValueError, sqlite3.Error) as e:
                QMessageBox.warning(self, '无法新建', str(e))

    def invalidate(self):
        self.confirm.setEnabled(False)
        self.summary.setText('文本已改变，请重新解析预览。')

    def parse(self):
        rows = parse_text(self.text.toPlainText())
        self.preview.blockSignals(True)
        self.preview.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, value in enumerate((r.source, r.chinese, r.english, '')):
                item = QTableWidgetItem(value)
                if j == 3:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 0:
                    item.setToolTip('双击后拖选需要的词汇，按 Ctrl+C 复制；原文不可修改')
                self.preview.setItem(i, j, item)
        self.preview.blockSignals(False)
        self.confirm.setEnabled(bool(rows) and bool(self.deck.currentData()))
        self.validate()

    def pairs(self):
        return [(self.preview.item(i, 1).text().strip(), self.preview.item(i, 2).text().strip()) for i in range(self.preview.rowCount())]

    def validate(self, *_):
        if not hasattr(self, 'preview'):
            return
        deck_id = self.deck.currentData()
        if deck_id not in self.existing_keys:
            self.existing_keys[deck_id] = set(self.store.db.execute('SELECT cn_key,en_key FROM cards WHERE deck_id=?', (deck_id,)).fetchall())
        seen = {tuple(key) for key in self.existing_keys[deck_id]}
        counts = [0, 0, 0]
        self.preview.blockSignals(True)
        for i, (c, e) in enumerate(self.pairs()):
            key = (normalize(c), normalize(e))
            if not valid_pair(c, e):
                status, n = '待修正', 2
            elif key in seen:
                status, n = '重复', 1
            else:
                status, n = '可导入', 0
                seen.add(key)
            counts[n] += 1
            self.preview.item(i, 3).setText(status)
        self.preview.blockSignals(False)
        self.summary.setText(f'可导入 {counts[0]} · 重复 {counts[1]} · 待修正 {counts[2]}（待修正行将跳过）')

    def remove(self):
        for row in sorted({i.row() for i in self.preview.selectedIndexes()}, reverse=True):
            self.preview.removeRow(row)
        self.validate()

    def commit(self):
        if not self.deck.currentData():
            return
        self.validate()
        a, d, i = self.store.add_cards(self.deck.currentData(), self.pairs())
        self.existing_keys.clear()
        QMessageBox.information(self, '导入完成', f'成功 {a} 条\n重复 {d} 条\n待修正 {i} 条')
        if i:
            self.preview.blockSignals(True)
            for row in range(self.preview.rowCount()-1, -1, -1):
                if self.preview.item(row, 3).text() != '待修正':
                    self.preview.removeRow(row)
            self.preview.blockSignals(False)
            self.validate()
        else:
            self.accept()


class CardsDialog(QDialog):
    def __init__(self, store, deck, parent):
        super().__init__(parent)
        self.store, self.deck = store, deck
        self.setWindowTitle('词条管理 · Lexivane')
        self.setMinimumSize(760, 540)
        self.resize(850, 580)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(caption('整理你的词汇', 'dialogHeading'))
        layout.addWidget(caption('双击中文或英文进行修改，再保存选中的词条。'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索中文或英文')
        self.search.textChanged.connect(self.filter)
        layout.addWidget(self.search)
        self.table = table(['中文', '英文', '已会 / 再学', '最近结果'])
        layout.addWidget(self.table)
        bottom = QHBoxLayout()
        button('保存选中行', self.save, bottom).setObjectName('primary')
        button('删除选中行', self.delete, bottom)
        bottom.addStretch()
        button('关闭', self.accept, bottom)
        layout.addLayout(bottom)
        self.reload()

    def reload(self):
        self.rows = self.store.cards(self.deck)
        self.table.setRowCount(len(self.rows))
        for i, c in enumerate(self.rows):
            values = [c['chinese'], c['english'], f"{c['known']} / {c['unknown']}", {None:'未学习', 0:'再学', 1:'已会'}[c['last_result']]]
            for j, value in enumerate(values):
                item = QTableWidgetItem(value)
                if j > 1:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, j, item)
        self.filter(self.search.text())

    def filter(self, text):
        for i in range(self.table.rowCount()):
            self.table.setRowHidden(i, text.casefold() not in (self.table.item(i, 0).text()+' '+self.table.item(i, 1).text()).casefold())

    def save(self):
        row = self.table.currentRow()
        if row < 0:
            return
        try:
            self.store.edit_card(self.rows[row]['id'], self.table.item(row, 0).text(), self.table.item(row, 1).text())
            self.reload()
        except (ValueError, sqlite3.Error) as e:
            QMessageBox.warning(self, '无法保存（可能重复）', str(e))

    def delete(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if rows and ConfirmDialog.ask(self, '删除选中词条', f'将删除 {len(rows)} 条词汇及其学习记录。\n此操作无法撤销，建议先备份。', '删除词条'):
            with self.store.db:
                for i in rows:
                    self.store.db.execute('DELETE FROM cards WHERE id=?', (self.rows[i]['id'],))
            self.reload()


class MainWindow(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store, self.learning, self.deck_id = store, None, None
        self.setWindowTitle('Lexivane')
        self.resize(1180, 800)
        self.setMinimumSize(920, 640)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(240)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(20, 30, 20, 24)
        left.setSpacing(12)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        mark = QLabel()
        mark.setObjectName('brandMark')
        mark.setFixedSize(42, 42)
        mark.setPixmap(QPixmap(str(ASSETS / 'app.png')).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(mark)
        brand.addWidget(caption('Lexivane', 'brand'))
        brand.addStretch()
        left.addLayout(brand)
        left.addWidget(caption('让每一次记忆，都有回响。'))
        left.addSpacing(26)
        section = QHBoxLayout()
        section.addWidget(caption('我的词库', 'eyebrow'))
        section.addStretch()
        self.deck_count = caption('0', 'countBadge')
        section.addWidget(self.deck_count)
        left.addLayout(section)
        button('＋  新建词库', self.new_deck, left).setObjectName('soft')
        self.decks = QListWidget()
        self.decks.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.decks.currentItemChanged.connect(self.select_deck)
        self.decks.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.decks.customContextMenuRequested.connect(self.deck_menu)
        left.addWidget(self.decks, 1)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.rename_button = button('重命名', self.rename_deck, actions)
        self.delete_button = button('删除词库', self.delete_deck, actions)
        self.rename_button.setObjectName('quiet')
        self.delete_button.setObjectName('quiet')
        left.addLayout(actions)
        left.addSpacing(6)
        self.backup_button = button('数据与备份', self.data_settings, left)
        self.backup_button.setFixedHeight(42)
        self.theme = CenteredComboBox()
        self.theme.setObjectName('appearance')
        self.theme.setFixedHeight(42)
        self.theme.setToolTip('选择外观')
        for key, name in APPEARANCES:
            self.theme.addItem(name, key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(store.setting('appearance', 'lavender'))))
        self.theme.currentIndexChanged.connect(self.apply_theme)
        left.addWidget(self.theme)
        saved = caption('所有学习记录自动保存')
        saved.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(saved)
        outer.addWidget(sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(36, 30, 36, 24)
        content.setSpacing(18)
        outer.addLayout(content, 1)
        top = QHBoxLayout()
        top.setSpacing(10)
        heading = QVBoxLayout()
        heading.setSpacing(6)
        heading.addWidget(caption('LEARN A LITTLE, EVERY DAY', 'eyebrow'))
        self.title = ElidedLabel('开始你的学习')
        self.title.setObjectName('heading')
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title.setMinimumWidth(80)
        heading.addWidget(self.title)
        top.addLayout(heading, 1)
        self.manage_button = button('词条管理', self.manage, top)
        self.export_button = button('导出', self.export, top)
        button('＋  导入词汇', self.import_cards, top).setObjectName('primary')
        content.addLayout(top)

        option_panel = QFrame()
        option_panel.setObjectName('options')
        controls = QHBoxLayout(option_panel)
        controls.setContentsMargins(12, 10, 12, 10)
        controls.setSpacing(16)
        self.mode = QComboBox()
        self.mode.addItems(['中译英', '英译中'])
        self.mode.setMinimumWidth(106)
        self.mode.setToolTip('开始新一轮时使用所选方向')
        self.shuffle = QCheckBox('随机顺序')
        self.shuffle.setChecked(True)
        self.unknown = QCheckBox('仅未掌握')
        self.unknown.setToolTip('包括未学习及最近一次不认识的卡片')
        controls.addWidget(self.mode)
        controls.addWidget(self.shuffle)
        controls.addWidget(self.unknown)
        controls.addStretch()
        self.restart_button = button('开始新一轮', self.restart, controls)
        self.restart_button.setObjectName('quiet')
        content.addWidget(option_panel)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.progress_label = caption('')
        progress_row.addWidget(self.progress_label)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        progress_row.addWidget(self.progress, 1)
        self.progress_percent = caption('0%')
        progress_row.addWidget(self.progress_percent)
        content.addLayout(progress_row)

        self.card = FlipCard()
        self.card.setObjectName('card')
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.card.setMinimumHeight(220)
        self.card.clicked.connect(self.flip)
        self.card.setCursor(Qt.CursorShape.PointingHandCursor)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        badge_row = QHBoxLayout()
        self.side_label = caption('', 'sideLabel')
        self.card_number = caption('')
        badge_row.addWidget(self.side_label, 0, Qt.AlignmentFlag.AlignLeft)
        badge_row.addStretch()
        badge_row.addWidget(self.card_number)
        card_layout.addLayout(badge_row)
        card_layout.addStretch(2)
        self.word = caption('', 'word')
        self.word.setWordWrap(True)
        self.word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        card_layout.addWidget(self.word)
        card_layout.addStretch(2)
        self.card_hint = caption('', 'cardHint')
        self.card_hint.setWordWrap(True)
        self.card_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.card_hint)
        for label in (self.side_label, self.word, self.card_hint, self.card_number):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        content.addWidget(self.card, 1)
        self.fade_effect = QGraphicsOpacityEffect(self.word)
        self.fade_effect.setOpacity(1.0)
        self.word.setGraphicsEffect(self.fade_effect)
        self.fade = QPropertyAnimation(self.fade_effect, b'opacity', self)
        self.fade.setDuration(140)
        self.fade.setStartValue(0.35)
        self.fade.setEndValue(1.0)

        bottom = QVBoxLayout()
        bottom.setSpacing(12)
        answers = QHBoxLayout()
        answers.setSpacing(16)
        answers.addStretch()
        self.no = button('再学', lambda: self.answer(False), answers)
        self.no.setObjectName('answerNo')
        self.yes = button('已会', lambda: self.answer(True), answers)
        self.yes.setObjectName('primary')
        self.yes.setProperty('answer', True)
        for b in (self.no, self.yes):
            b.setMinimumSize(196, 52)
            b.setIconSize(QSize(18, 18))
        answers.addStretch()
        bottom.addLayout(answers)
        content.addLayout(bottom)
        for key, callback in [('Space', self.flip), ('Left', lambda: self.answer(False)), ('Right', lambda: self.answer(True))]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(callback)
        self.apply_theme()
        self.refresh(store.setting('selected'))

    def apply_theme(self, *_):
        appearance = self.theme.currentData() or 'lavender'
        self.store.set_setting('appearance', appearance)
        colors = apply_theme(self, appearance)
        self.no.setIcon(line_icon('retry', colors['accent']))
        self.yes.setIcon(line_icon('check', colors['inverse']))

    def refresh(self, selected=None):
        selected = selected or self.deck_id
        self.decks.blockSignals(True)
        self.decks.clear()
        chosen = None
        decks = self.store.decks()
        self.deck_count.setText(str(len(decks)))
        for d in decks:
            item = QListWidgetItem()
            item.setSizeHint(QSize(180, 54))
            item.setData(Qt.ItemDataRole.UserRole, d)
            item.setToolTip(d['name'])
            self.decks.addItem(item)
            self.decks.setItemWidget(item, DeckRow(d['name'], d['count']))
            if d['id'] == selected:
                chosen = item
        self.decks.blockSignals(False)
        if chosen:
            self.decks.setCurrentItem(chosen)
        elif self.decks.count():
            self.decks.setCurrentRow(0)
        else:
            self.select_deck(None)

    def select_deck(self, item, *_):
        d = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.deck_id = d['id'] if d else None
        for b in (self.manage_button, self.export_button, self.restart_button, self.rename_button, self.delete_button):
            b.setEnabled(bool(d))
        self.title.setText(d['name'] if d else '开始你的学习')
        self.title.setToolTip(d['name'] if d else '')
        self.learning = Learning(self.store, self.deck_id) if d else None
        if self.learning:
            self.store.set_setting('selected', self.deck_id)
            if self.learning.state is None:
                self.learning.start()
            s = self.learning.state
            self.mode.setCurrentIndex(int(s['mode'] == 'en'))
            self.shuffle.setChecked(s['shuffle'])
            self.unknown.setChecked(s['only_unknown'])
        self.render()

    def render(self):
        card = self.learning.current() if self.learning else None
        state = self.learning.state if self.learning else None
        total = len(state['queue']) if state else 0
        index = state['index'] if state else 0
        initial = state['initial_total']-state['removed'] if state else 0
        mastered = state['mastered'] if state else 0
        self.progress.setRange(0, max(1, initial))
        self.progress.setValue(mastered)
        self.progress_percent.setText(f'{round(mastered / initial * 100) if initial else 0}%')
        self.progress_label.setText(f"已会 {mastered}/{initial} · 第 {state['pass_number']} 遍 {index}/{total}" if state else '准备开始')
        self.card_number.setText(f'{min(index + 1, total):02d} / {total:02d}' if total else '')
        self.no.setEnabled(bool(card))
        self.yes.setEnabled(bool(card))
        self.card.setCursor(Qt.CursorShape.PointingHandCursor if card else Qt.CursorShape.ArrowCursor)
        if card:
            back = self.learning.flipped
            field = ('english' if back else 'chinese') if state['mode'] == 'cn' else ('chinese' if back else 'english')
            direction = '中文 → 英文' if state['mode'] == 'cn' else '英文 → 中文'
            self.side_label.setText('答案' if back else (f'错词巩固 · {direction}' if state['pass_number'] > 1 else direction))
            self.word.setText(card[field])
            self.card_hint.setText(f'本次还有 {self.learning.remaining} 个待巩固；标记「再学」会继续留在练习中。' if back else ('点击卡片查看答案 · 未掌握词汇会自动继续巩固' if state['pass_number'] == 1 else '正在巩固未掌握词汇 · 点击卡片查看答案'))
        else:
            completed = bool(state and state['initial_total'])
            self.side_label.setText('本次练习完成' if completed else '准备开始')
            self.word.setText(('本次词汇已掌握' if not state['removed'] else '本次练习已完成') if completed else '让词汇，慢慢变熟悉。')
            if completed:
                summary = f"已会 {mastered} 个 · 共练习 {state['attempts']} 次 · 完成 {state['pass_number']} 遍"
                if state['removed']:
                    summary += f" · 移除 {state['removed']} 个"
                self.card_hint.setText(summary + '\n以后要复习全部词汇，取消「仅未掌握」后点击「开始新一轮」。')
            else:
                self.card_hint.setText(('当前没有待练词汇；取消「仅未掌握」后可重新练习全部词汇。' if self.unknown.isChecked() else '点击「导入」添加词汇；新增词汇在开始新一轮时加入。') if self.deck_id else '点击「导入」，粘贴你的第一组词汇。')

    def flip(self):
        if self.learning:
            self.learning.flip()
            self.render()
            self.fade.stop()
            self.fade.start()

    def answer(self, known):
        if self.learning and self.learning.answer(known):
            self.fade.stop()
            self.fade_effect.setOpacity(1.0)
            self.render()

    def restart(self):
        if not self.learning:
            return
        if self.learning.current() and self.learning.state['attempts'] > 0:
            if not ConfirmDialog.ask(self, '开始新一轮', f'本次还有 {self.learning.remaining} 个词待巩固。\n开始新一轮将按当前设置重新练习，历史学习记录仍会保留。', '开始新一轮', danger=False):
                return
        self.learning.start('en' if self.mode.currentIndex() else 'cn', self.shuffle.isChecked(), self.unknown.isChecked())
        self.render()

    def new_deck(self):
        name, ok = NameDialog.ask(self)
        if ok:
            try:
                self.refresh(self.store.create_deck(name))
            except (ValueError, sqlite3.Error) as e:
                QMessageBox.warning(self, '无法新建', str(e))

    def rename_deck(self):
        if self.deck_id:
            name, ok = NameDialog.ask(self, '重命名词库', self.title.text())
            if ok:
                try:
                    self.store.rename_deck(self.deck_id, name)
                    self.refresh()
                except (ValueError, sqlite3.Error) as e:
                    QMessageBox.warning(self, '无法重命名', str(e))

    def delete_deck(self):
        if self.deck_id and ConfirmDialog.ask(self, '删除词库', f'确定删除「{self.title.text()}」吗？\n\n词库中的词条和学习记录将一并删除。\n此操作无法撤销，建议先备份。', '删除词库'):
            self.store.delete_deck(self.deck_id)
            self.refresh()

    def deck_menu(self, point):
        item = self.decks.itemAt(point)
        if item:
            self.decks.setCurrentItem(item)
            menu = QMenu(self)
            menu.addAction('重命名', self.rename_deck)
            menu.addAction('删除词库', self.delete_deck)
            menu.exec(self.decks.mapToGlobal(point))

    def import_cards(self):
        dialog = ImportDialog(self.store, self.deck_id, self)
        dialog.exec()
        self.refresh(dialog.deck.currentData())
        if self.learning and not self.learning.state['queue'] and self.store.cards(self.deck_id):
            self.learning.start()
            self.render()

    def manage(self):
        if self.deck_id:
            CardsDialog(self.store, self.deck_id, self).exec()
            self.refresh()

    def export(self):
        if self.deck_id:
            path, selected = QFileDialog.getSaveFileName(self, '导出词库', '词库.json', 'JSON (*.json);;CSV (*.csv)')
            if path:
                if not Path(path).suffix:
                    path += '.csv' if selected.startswith('CSV') else '.json'
                self.store.export_deck(self.deck_id, path)
                QMessageBox.information(self, '导出完成', '词库已导出。完整学习记录请使用备份。')

    def data_settings(self):
        dialog = DataDialog(self, self.store.path)
        choice = dialog.exec()
        dialog.deleteLater()
        if choice == DataDialog.BACKUP:
            self.backup()
        elif choice == DataDialog.RESTORE:
            self.restore()

    def backup(self):
        path, _ = QFileDialog.getSaveFileName(self, '备份全部数据', 'Lexivane-backup.json', 'JSON (*.json)')
        if path:
            self.store.backup(path)
            QMessageBox.information(self, '备份完成', '词库、学习记录、当前进度及设置已保存。')

    def restore(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择备份', '', 'JSON (*.json)')
        if not path:
            return
        box = QMessageBox(self)
        box.setWindowTitle('恢复方式')
        box.setText('合并保留现有数据并跳过重复词条；替换将覆盖全部当前数据。恢复前会自动备份当前数据。')
        merge = box.addButton('合并', QMessageBox.ButtonRole.AcceptRole)
        replace = box.addButton('替换全部', QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() not in (merge, replace):
            return
        try:
            from .storage import now
            safety = self.store.path.parent / ('before-restore-' + now().replace(':', '-') + '.json')
            self.store.backup(safety)
            self.store.restore(path, replace=box.clickedButton() == replace)
            self.theme.setCurrentIndex(max(0, self.theme.findData(self.store.setting('appearance', 'lavender'))))
            self.refresh()
            QMessageBox.information(self, '恢复完成', f'数据已恢复。恢复前副本：\n{safety}')
        except (ValueError, KeyError, OSError, sqlite3.Error) as e:
            QMessageBox.warning(self, '恢复失败，原数据保留', str(e))
