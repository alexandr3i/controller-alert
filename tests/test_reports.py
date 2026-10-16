import importlib.util
from pathlib import Path
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location('server', Path(__file__).parents[1] / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class Reports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = server.Store(str(Path(self.tmp.name) / 'db'), {'lines': [{'id': '41', 'stops': ['A'], 'reverseStops': ['B']}]})

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def test_shared_votes_and_ownership(self):
        first = self.store.run('owner', 'create', {'line': '41', 'direction': 'forward', 'stop': 'A'})[0]
        rid = first['id']
        self.assertTrue(first['canDelete'])
        other = self.store.run('other', 'list', {})[0]
        self.assertFalse(other['canDelete'])
        for _ in range(2):
            other = self.store.run('other', 'vote', {'id': rid, 'voted': True})[0]
        self.assertEqual(other['confirmations'], 1)
        with self.assertRaises(PermissionError):
            self.store.run('other', 'delete', {'id': rid})
        self.assertEqual(self.store.run('owner', 'delete', {'id': rid}), [])

    def test_validation_rate_and_expiry(self):
        with self.assertRaises(ValueError):
            self.store.run('owner', 'create', {'line': '41', 'direction': 'reverse', 'stop': 'A'})
        for _ in range(3):
            self.store.run('owner', 'create', {'line': '41', 'direction': 'forward', 'stop': 'A'})
        with self.assertRaises(ValueError):
            self.store.run('owner', 'create', {'line': '41', 'direction': 'forward', 'stop': 'A'})
        self.store.db.execute('UPDATE reports SET created=?', (int(time.time()*1000)-server.TTL-1000,))
        self.store.db.commit()
        self.assertEqual(self.store.run('owner', 'list', {}), [])


if __name__ == '__main__':
    unittest.main()
