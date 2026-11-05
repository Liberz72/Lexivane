import random
from .storage import uid, now


class Learning:
    def __init__(self, store, deck):
        self.store, self.deck = store, deck
        self.state = store.session(deck)
        self.flipped = False
        if self.state is not None and 'training_version' not in self.state:
            # Upgrade old, single-pass progress without erasing past answers.
            cards = {c['id']: c for c in store.cards(deck)}
            answered = self.state['queue'][:self.state['index']]
            retry = [i for i in answered if i in cards and cards[i]['last_result'] == 0]
            self.state.update(training_version=1, pass_number=1, retry=retry,
                              initial_total=len(self.state['queue']), mastered=self.state['known'],
                              removed=max(0, self.state['unknown']-len(retry)), attempts=self.state['index'])
            with self.store.db:
                self.store.save_session(deck, self.state)

    def start(self, mode='cn', shuffle=True, only_unknown=False):
        cards = self.store.cards(self.deck)
        queue = [c['id'] for c in cards if not only_unknown or c['last_result'] != 1]
        if shuffle:
            random.shuffle(queue)
        state = dict(queue=queue, index=0, known=0, unknown=0, mode=mode, shuffle=shuffle,
                     only_unknown=only_unknown, training_version=1, pass_number=1,
                     retry=[], initial_total=len(queue), mastered=0, removed=0, attempts=0)
        self.flipped = False
        with self.store.db:
            self.store.save_session(self.deck, state)
        self.state = state

    def _next_pass(self, state):
        """Advance only at a pass boundary; each missed card occurs once per pass."""
        if state['index'] < len(state['queue']) or not state['retry']:
            return False
        existing = {r[0] for r in self.store.db.execute('SELECT id FROM cards WHERE deck_id=?', (self.deck,))}
        queue = [i for i in state['retry'] if i in existing]
        state['removed'] += len(state['retry'])-len(queue)
        state['retry'] = []
        if queue:
            if state['shuffle']:
                random.shuffle(queue)
            state.update(queue=queue, index=0, known=0, unknown=0, pass_number=state['pass_number']+1)
        return True

    @property
    def remaining(self):
        return self.state['initial_total']-self.state['mastered']-self.state['removed'] if self.state else 0

    def current(self):
        if not self.state:
            return None
        # Deleted cards are skipped without fabricating a review.
        while True:
            if self.state['index'] >= len(self.state['queue']):
                state = dict(self.state)
                if self._next_pass(state):
                    with self.store.db:
                        self.store.save_session(self.deck, state)
                    self.state = state
                    self.flipped = False
                if self.state['index'] >= len(self.state['queue']):
                    return None
            ident = self.state['queue'][self.state['index']]
            row = self.store.db.execute('SELECT * FROM cards WHERE id=? AND deck_id=?', (ident, self.deck)).fetchone()
            if row:
                return dict(row)
            state = dict(self.state, queue=list(self.state['queue']))
            state['queue'].pop(state['index'])
            state['removed'] += 1
            with self.store.db:
                self.store.save_session(self.deck, state)
            self.state = state

    def flip(self):
        if self.current():
            self.flipped = not self.flipped

    def answer(self, known):
        card = self.current()
        if not card:
            return False
        state = dict(self.state)
        state['index'] += 1
        state['known' if known else 'unknown'] += 1
        state['attempts'] += 1
        if known:
            state['mastered'] += 1
        else:
            state['retry'] = state['retry'] + [card['id']]
        with self.store.db:
            self.store.db.execute('INSERT INTO reviews VALUES(?,?,?,?)', (uid(), card['id'], int(known), now()))
            self._next_pass(state)
            self.store.save_session(self.deck, state)
        self.state, self.flipped = state, False
        return True
