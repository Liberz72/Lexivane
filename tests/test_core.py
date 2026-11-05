import json
import tempfile
import unittest
from pathlib import Path
from lexicards.parser import parse_text
from lexicards.storage import Store
from lexicards.learning import Learning


class ParserTests(unittest.TestCase):
    def test_requested_formats(self):
        text = '''飞行控制器 Flight Controller\\
无人机 Unmanned Aerial Vehicle\\
autopilot 自动驾驶\\
telemetry 遥测\\
trajectory planning - 轨迹规划\\
robust control：鲁棒控制
飞行控制器：Flight Controller
无人机 = Unmanned Aerial Vehicle
telemetry, 遥测
1. 控制理论\tControl Theory
2、科研英语 = Research English'''
        rows = parse_text(text)
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(r.chinese and r.english and not r.error for r in rows))
        self.assertEqual(rows[4].english, 'trajectory planning')
        self.assertEqual(rows[3].chinese, '遥测')

    def test_ambiguous_does_not_guess(self):
        rows = parse_text('\n1.\n纯中文\nonly English\n控制 control 控制\nPID控制 PID Control\n')
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r.error and not r.english for r in rows))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.path = Path(self.tmp.name) / 'db.sqlite3'
        self.s = Store(self.path)
        self.d = self.s.create_deck('控制理论')

    def tearDown(self):
        self.s.close()
        self.tmp.cleanup()

    def test_dedup_and_isolation(self):
        self.assertEqual(self.s.add_cards(self.d, [('控制', 'Control'), ('控制', ' control '), ('', 'x')]), (1, 1, 1))
        other = self.s.create_deck('科研英语')
        self.assertEqual(self.s.add_cards(other, [('控制', 'Control')]), (1, 0, 0))
        self.assertEqual(len(self.s.cards(self.d)), 1)

    def test_round_resume_history_and_new_cards(self):
        self.s.add_cards(self.d, [('一', 'one'), ('二', 'two'), ('三', 'three')])
        l = Learning(self.s, self.d)
        l.start()
        first = l.current()['id']
        self.assertTrue(l.answer(True))
        self.s.add_cards(self.d, [('四', 'four')])
        self.s.close()
        self.s = Store(self.path)
        l = Learning(self.s, self.d)
        self.assertEqual(l.state['index'], 1)
        seen = {first}
        for _ in range(2):
            card = l.current()
            self.assertNotIn(card['id'], seen)
            seen.add(card['id'])
            l.answer(False)
        self.assertEqual(len(seen), 3)
        self.assertEqual(l.state['pass_number'], 2)
        self.assertEqual(l.state['mastered'], 1)
        self.assertEqual(l.remaining, 2)
        l.start(only_unknown=True)
        self.assertEqual(len(l.state['queue']), 3)
        l.start()
        self.assertEqual(len(l.state['queue']), 4)
        self.assertEqual(sum(c['known']+c['unknown'] for c in self.s.cards(self.d)), 3)

    def test_answers_without_flip_are_persisted_once(self):
        self.s.add_cards(self.d, [('一', 'one'), ('二', 'two')])
        learning = Learning(self.s, self.d)
        learning.start(shuffle=False)
        self.assertFalse(learning.flipped)
        self.assertTrue(learning.answer(True))
        self.assertTrue(learning.answer(False))
        self.assertEqual(learning.state['pass_number'], 2)
        self.assertTrue(learning.answer(True))
        self.assertFalse(learning.answer(True))
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0], 3)
        self.s.close()
        self.s = Store(self.path)
        state = Learning(self.s, self.d).state
        self.assertEqual((state['mastered'], state['attempts'], state['pass_number']), (2, 3, 2))

    def test_delete_current_skips(self):
        self.s.add_cards(self.d, [('一', 'one'), ('二', 'two')])
        l = Learning(self.s, self.d)
        l.start()
        self.s.delete_card(l.current()['id'])
        self.assertIsNotNone(l.current())
        self.assertEqual(len(l.state['queue']), 1)

    def test_backup_merge_replace_and_atomic_reject(self):
        self.s.add_cards(self.d, [('遥测', 'telemetry')])
        l = Learning(self.s, self.d)
        l.start()
        l.flip()
        l.answer(True)
        path = Path(self.tmp.name) / 'backup.json'
        self.s.backup(path)
        self.s.restore(path)
        self.s.restore(path)
        self.assertEqual(len(self.s.cards(self.d)), 1)
        self.assertEqual(self.s.cards(self.d)[0]['known'], 1)
        self.s.create_deck('临时')
        self.s.restore(path, replace=True)
        self.assertEqual(len(self.s.decks()), 1)
        self.assertEqual(Learning(self.s, self.d).state['index'], 1)
        broken = json.loads(path.read_text(encoding='utf-8'))
        broken['reviews'][0]['card_id'] = 'missing'
        path.write_text(json.dumps(broken), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.s.restore(path, replace=True)
        self.assertEqual(self.s.cards(self.d)[0]['known'], 1)

    def test_edit_export_and_cascade(self):
        self.s.add_cards(self.d, [('遥测', 'telemetry')])
        card = self.s.cards(self.d)[0]
        self.s.edit_card(card['id'], '轨迹规划', 'trajectory planning')
        path = Path(self.tmp.name) / 'deck.csv'
        self.s.export_deck(self.d, path)
        self.assertIn('trajectory planning', path.read_text(encoding='utf-8-sig'))
        self.s.delete_deck(self.d)
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM cards').fetchone()[0], 0)

    def test_restore_completed_round_with_deleted_card(self):
        self.s.add_cards(self.d, [('一', 'one'), ('二', 'two')])
        l = Learning(self.s, self.d)
        l.start()
        ident = l.current()['id']
        l.answer(False)
        self.s.delete_card(ident)
        path = Path(self.tmp.name) / 'deleted.json'
        self.s.backup(path)
        self.s.restore(path, replace=True)
        resumed = Learning(self.s, self.d)
        self.assertEqual(resumed.state['index'], 1)
        self.assertIsNotNone(resumed.current())

    def test_duplicate_edit_does_not_erase_card(self):
        import sqlite3
        self.s.add_cards(self.d, [('一', 'one'), ('二', 'two')])
        rows = self.s.cards(self.d)
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.edit_card(rows[0]['id'], rows[1]['chinese'], rows[1]['english'])
        self.assertEqual(len(self.s.cards(self.d)), 2)
        self.assertEqual(self.s.db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')


if __name__ == '__main__':
    unittest.main()
