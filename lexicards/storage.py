import csv
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .parser import normalize, valid_pair


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    try:
        with temp.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS decks(id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cards(id TEXT PRIMARY KEY, deck_id TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
          chinese TEXT NOT NULL, english TEXT NOT NULL, cn_key TEXT NOT NULL, en_key TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(deck_id,cn_key,en_key));
        CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
          result INTEGER NOT NULL CHECK(result IN (0,1)), reviewed_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS review_card ON reviews(card_id,reviewed_at);
        CREATE TABLE IF NOT EXISTS sessions(deck_id TEXT PRIMARY KEY REFERENCES decks(id) ON DELETE CASCADE, state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def decks(self):
        return [dict(r) for r in self.db.execute('SELECT d.*,COUNT(c.id) AS count FROM decks d LEFT JOIN cards c ON c.deck_id=d.id GROUP BY d.id ORDER BY d.created_at,d.id')]

    def create_deck(self, name):
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError('词库名应为 1–100 个字符')
        ident = uid()
        with self.db:
            self.db.execute('INSERT INTO decks VALUES(?,?,?)', (ident, name, now()))
        return ident

    def rename_deck(self, ident, name):
        if not name.strip() or len(name.strip()) > 100:
            raise ValueError('词库名应为 1–100 个字符')
        with self.db:
            self.db.execute('UPDATE decks SET name=? WHERE id=?', (name.strip(), ident))

    def delete_deck(self, ident):
        with self.db:
            self.db.execute('DELETE FROM decks WHERE id=?', (ident,))

    def cards(self, deck):
        return [dict(r) for r in self.db.execute('''SELECT c.*,
          (SELECT COUNT(*) FROM reviews r WHERE r.card_id=c.id AND result=1) known,
          (SELECT COUNT(*) FROM reviews r WHERE r.card_id=c.id AND result=0) unknown,
          (SELECT result FROM reviews r WHERE r.card_id=c.id ORDER BY reviewed_at DESC,rowid DESC LIMIT 1) last_result
          FROM cards c WHERE deck_id=? ORDER BY c.created_at,c.id''', (deck,))]

    def add_cards(self, deck, pairs):
        added = duplicate = invalid = 0
        with self.db:
            for c, e in pairs:
                c, e = c.strip(), e.strip()
                if not valid_pair(c, e):
                    invalid += 1
                    continue
                cursor = self.db.execute('INSERT OR IGNORE INTO cards VALUES(?,?,?,?,?,?,?)',
                    (uid(), deck, c, e, normalize(c), normalize(e), now()))
                if cursor.rowcount:
                    added += 1
                else:
                    duplicate += 1
        return added, duplicate, invalid

    def edit_card(self, ident, chinese, english):
        if not valid_pair(chinese, english):
            raise ValueError('请填写含中文的释义和不含中文的英文')
        with self.db:
            self.db.execute('UPDATE cards SET chinese=?,english=?,cn_key=?,en_key=? WHERE id=?',
                            (chinese.strip(), english.strip(), normalize(chinese), normalize(english), ident))

    def delete_card(self, ident):
        with self.db:
            self.db.execute('DELETE FROM cards WHERE id=?', (ident,))

    def session(self, deck):
        row = self.db.execute('SELECT state FROM sessions WHERE deck_id=?', (deck,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_session(self, deck, state):
        self.db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?)', (deck, json.dumps(state)))

    def set_setting(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, value))

    def setting(self, key, default=''):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

    def backup(self, path):
        data = {'format': 'LexiCards', 'version': 1}
        for table in ('decks', 'cards', 'reviews', 'sessions', 'settings'):
            data[table] = [dict(r) for r in self.db.execute('SELECT * FROM ' + table)]
        for session in data['sessions']:
            session['state'] = json.loads(session['state'])
        atomic_json(path, data)

    def restore(self, path, replace=False):
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        self.validate_backup(data)
        deck_map, card_map = {}, {}
        with self.db:
            if replace:
                self.db.execute('DELETE FROM decks')
                self.db.execute('DELETE FROM settings')
            for d in data['decks']:
                row = self.db.execute('SELECT id FROM decks WHERE id=? OR name=? ORDER BY id=? DESC', (d['id'], d['name'], d['id'])).fetchone()
                target = row[0] if row else d['id']
                deck_map[d['id']] = target
                if not row:
                    self.db.execute('INSERT INTO decks VALUES(?,?,?)', (target, d['name'], d['created_at']))
            for c in data['cards']:
                deck = deck_map[c['deck_id']]
                row = self.db.execute('SELECT id FROM cards WHERE deck_id=? AND cn_key=? AND en_key=?', (deck, normalize(c['chinese']), normalize(c['english']))).fetchone()
                target = row[0] if row else c['id']
                if not row and self.db.execute('SELECT 1 FROM cards WHERE id=?', (target,)).fetchone():
                    target = uid()
                card_map[c['id']] = target
                if not row:
                    self.db.execute('INSERT INTO cards VALUES(?,?,?,?,?,?,?)', (target, deck, c['chinese'], c['english'], normalize(c['chinese']), normalize(c['english']), c['created_at']))
            for r in data['reviews']:
                self.db.execute('INSERT OR IGNORE INTO reviews VALUES(?,?,?,?)', (r['id'], card_map[r['card_id']], r['result'], r['reviewed_at']))
            if replace:
                for s in data.get('sessions', []):
                    self.save_session(s['deck_id'], s['state'])
                for s in data.get('settings', []):
                    self.db.execute('INSERT INTO settings VALUES(?,?)', (s['key'], s['value']))
        return len(data['decks']), len(data['cards'])

    @staticmethod
    def validate_backup(data):
        if not isinstance(data, dict) or data.get('format') != 'LexiCards' or data.get('version') != 1:
            raise ValueError('不是受支持的 LexiCards 备份')
        try:
            decks, cards, reviews = data['decks'], data['cards'], data['reviews']
            for rows in (decks, cards, reviews):
                if not isinstance(rows, list) or len({r['id'] for r in rows}) != len(rows):
                    raise ValueError('记录 ID 重复或格式错误')
                for r in rows:
                    if not all(isinstance(r[k], str) and r[k] for k in ('id',)):
                        raise ValueError('无效 ID')
            ds, cs = {d['id'] for d in decks}, {c['id'] for c in cards}
            card_decks = {c['id']: c['deck_id'] for c in cards}
            if len({d['name'] for d in decks}) != len(decks):
                raise ValueError('词库名称重复')
            for d in decks:
                if not isinstance(d['name'], str) or not d['name'].strip() or not isinstance(d['created_at'], str):
                    raise ValueError('无效词库')
            pairs = set()
            for c in cards:
                if c['deck_id'] not in ds or not valid_pair(c['chinese'], c['english']) or not isinstance(c['created_at'], str):
                    raise ValueError('无效卡片')
                key = (c['deck_id'], normalize(c['chinese']), normalize(c['english']))
                if key in pairs:
                    raise ValueError('备份存在重复词条')
                pairs.add(key)
            for r in reviews:
                if r['card_id'] not in cs or type(r['result']) is not int or r['result'] not in (0, 1) or not isinstance(r['reviewed_at'], str):
                    raise ValueError('无效学习记录')
            for s in data.get('sessions', []):
                state = s['state']
                if s['deck_id'] not in ds or not isinstance(state, dict):
                    raise ValueError('无效学习进度')
                if not isinstance(state['queue'], list) or len(set(state['queue'])) != len(state['queue']):
                    raise ValueError('无效学习队列')
                # Deleted cards may remain in an already completed queue; the
                # learning engine safely skips missing pending cards on resume.
                if any(not isinstance(i, str) or (i in card_decks and card_decks[i] != s['deck_id']) for i in state['queue']) or type(state['index']) is not int or not 0 <= state['index'] <= len(state['queue']):
                    raise ValueError('无效学习进度')
                if any(type(state[k]) is not int or state[k] < 0 for k in ('known', 'unknown')) or state['known'] + state['unknown'] != state['index']:
                    raise ValueError('无效学习计数')
                if state['mode'] not in ('cn', 'en') or type(state['shuffle']) is not bool or type(state['only_unknown']) is not bool:
                    raise ValueError('无效学习设置')
                if 'training_version' in state:
                    if type(state['training_version']) is not int or state['training_version'] != 1:
                        raise ValueError('不支持的巩固进度版本')
                    if any(type(state[k]) is not int or state[k] < 0 for k in ('initial_total', 'mastered', 'removed', 'attempts')) or type(state['pass_number']) is not int or state['pass_number'] < 1:
                        raise ValueError('无效巩固计数')
                    retry = state['retry']
                    if not isinstance(retry, list) or any(not isinstance(i, str) for i in retry) or len(set(retry)) != len(retry) or not set(retry).issubset(state['queue'][:state['index']]):
                        raise ValueError('无效待巩固队列')
                    remaining = len(state['queue'])-state['index']+len(retry)
                    if state['initial_total'] != state['mastered']+state['removed']+remaining or len(retry) > state['unknown'] or state['attempts'] < max(state['mastered'], state['index']):
                        raise ValueError('巩固进度不一致')
            for s in data.get('settings', []):
                if not isinstance(s['key'], str) or not isinstance(s['value'], str):
                    raise ValueError('无效设置')
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError('备份字段不完整或类型错误') from exc

    def export_deck(self, deck, path):
        cards = self.cards(deck)
        if Path(path).suffix.lower() == '.csv':
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['chinese', 'english'])
                writer.writeheader()
                writer.writerows({k: c[k] for k in writer.fieldnames} for c in cards)
        else:
            atomic_json(path, [{'chinese': c['chinese'], 'english': c['english']} for c in cards])
