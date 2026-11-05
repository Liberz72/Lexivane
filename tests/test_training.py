import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lexicards.learning import Learning
from lexicards.storage import Store


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.store = Store(self.path)
        self.deck = self.store.create_deck('自动巩固')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def begin(self, count):
        self.store.add_cards(self.deck, [(f'词{i}', f'word{i}') for i in range(count)])
        learning = Learning(self.store, self.deck)
        learning.start(shuffle=True)
        return learning

    def pass_once(self, learning, missed):
        expected = set(learning.state['queue'])
        seen = set()
        for _ in range(len(expected)):
            card = learning.current()
            self.assertIsNotNone(card)
            self.assertNotIn(card['id'], seen)
            seen.add(card['id'])
            learning.answer(card['id'] not in missed)
        self.assertEqual(seen, expected)

    def test_thirty_then_ten_then_four_then_mastered(self):
        learning = self.begin(30)
        missed = set(learning.state['queue'][:10])
        self.pass_once(learning, missed)
        self.assertEqual((learning.state['pass_number'], learning.state['mastered']), (2, 20))
        self.assertEqual(set(learning.state['queue']), missed)
        missed_again = set(learning.state['queue'][:4])
        self.pass_once(learning, missed_again)
        self.assertEqual(set(learning.state['queue']), missed_again)
        self.assertEqual((learning.state['pass_number'], learning.state['mastered']), (3, 26))
        self.pass_once(learning, set())
        self.assertIsNone(learning.current())
        self.assertEqual((learning.remaining, learning.state['mastered'], learning.state['attempts']), (0, 30, 44))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0], 44)

    def test_repeated_miss_stays_until_known(self):
        learning = self.begin(1)
        ident = learning.current()['id']
        for number in range(1, 5):
            self.assertTrue(learning.answer(False))
            self.assertEqual(learning.current()['id'], ident)
            self.assertEqual(learning.state['pass_number'], number+1)
        learning.answer(True)
        self.assertIsNone(learning.current())
        self.assertEqual(learning.state['attempts'], 5)

    def test_resume_and_backup_during_consolidation(self):
        learning = self.begin(4)
        missed = set(learning.state['queue'][:3])
        self.pass_once(learning, missed)
        learning.answer(False)
        state = dict(learning.state)
        self.store.close()
        self.store = Store(self.path)
        resumed = Learning(self.store, self.deck)
        self.assertEqual(resumed.state, state)
        backup = Path(self.temp.name) / 'backup.json'
        self.store.backup(backup)
        self.store.restore(backup, replace=True)
        restored = Learning(self.store, self.deck)
        self.assertEqual(restored.state, state)
        for _ in range(2):
            restored.answer(True)
        self.assertEqual(restored.state['pass_number'], 3)
        self.assertEqual(len(restored.state['queue']), 1)
        restored.answer(True)
        self.assertIsNone(restored.current())

    def test_manual_full_restart_retests_old_known_and_new_words(self):
        learning = self.begin(3)
        all_ids = set(learning.state['queue'])
        self.pass_once(learning, set())
        self.assertIsNone(learning.current())
        learning.start(shuffle=False)
        self.assertEqual(set(learning.state['queue']), all_ids)
        forgotten = learning.current()['id']
        learning.answer(False)
        self.store.add_cards(self.deck, [('新词', 'new word')])
        learning.answer(True)
        learning.answer(True)
        self.assertEqual(learning.state['queue'], [forgotten])
        self.assertEqual(learning.remaining, 1)
        history = self.store.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
        learning.start(shuffle=False)
        self.assertEqual(len(learning.state['queue']), 4)
        self.assertEqual((learning.state['pass_number'], learning.state['mastered'], learning.state['retry']), (1, 0, []))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0], history)

    def test_deleted_missed_and_pending_cards_are_not_reintroduced(self):
        learning = self.begin(3)
        missed = learning.current()['id']
        learning.answer(False)
        self.store.delete_card(missed)
        self.store.delete_card(learning.current()['id'])
        learning.answer(True)
        self.assertIsNone(learning.current())
        self.assertEqual((learning.state['removed'], learning.remaining), (2, 0))
        backup = Path(self.temp.name) / 'deleted.json'
        self.store.backup(backup)
        self.store.restore(backup, replace=True)
        self.assertIsNone(Learning(self.store, self.deck).current())

    def test_upgrade_legacy_progress_keeps_missed_queue(self):
        learning = self.begin(3)
        missed = learning.current()['id']
        learning.answer(False)
        learning.answer(True)
        legacy = {k: learning.state[k] for k in ('queue', 'index', 'known', 'unknown', 'mode', 'shuffle', 'only_unknown')}
        with self.store.db:
            self.store.save_session(self.deck, legacy)
        resumed = Learning(self.store, self.deck)
        self.assertEqual(resumed.state['retry'], [missed])
        resumed.answer(True)
        self.assertEqual(resumed.state['queue'], [missed])

    def test_upgrade_completed_legacy_round_resumes_misses(self):
        learning = self.begin(1)
        ident = learning.current()['id']
        learning.answer(False)
        legacy = dict(queue=[ident], index=1, known=0, unknown=1, mode='cn', shuffle=True, only_unknown=False)
        with self.store.db:
            self.store.save_session(self.deck, legacy)
        resumed = Learning(self.store, self.deck)
        self.assertEqual(resumed.current()['id'], ident)
        self.assertEqual(resumed.state['pass_number'], 2)

    def test_transition_and_review_roll_back_together(self):
        learning = self.begin(1)
        previous = dict(learning.state)
        with patch.object(self.store, 'save_session', side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):
                learning.answer(False)
        self.assertEqual(learning.state, previous)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0], 0)

    def test_corrupt_retry_backup_rejected_without_data_loss(self):
        learning = self.begin(2)
        learning.answer(False)
        backup = Path(self.temp.name) / 'bad.json'
        self.store.backup(backup)
        payload = json.loads(backup.read_text(encoding='utf-8'))
        state = payload['sessions'][0]['state']
        state['retry'].append(state['retry'][0])
        backup.write_text(json.dumps(payload), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.restore(backup, replace=True)
        self.assertEqual(len(self.store.cards(self.deck)), 2)
