import unittest
from tools.publication_guard import allowed

class PublicationGuardTests(unittest.TestCase):
    old = {'checked_at': '2026-11-11T02:00:00+00:00'}
    new = {'checked_at': '2026-11-11T03:00:00+00:00'}
    data = ['projects/bet-ledger-hq/data/tickets/health.json', 'projects/nba-edge-lab/state/player_database.json.gz']

    def test_concurrent_older_data_does_not_block_fresh_artifact(self):
        self.assertTrue(allowed(self.data, self.new, self.old))

    def test_newer_competing_publication_blocks_old_artifact(self):
        self.assertFalse(allowed(self.data, self.old, self.new))

    def test_release_code_and_workflow_changes_always_block(self):
        for path in ['tools/refresh.py', '.github/workflows/release.yml', 'projects/bet-ledger-hq/index.html', 'requirements-lock.txt']:
            self.assertFalse(allowed(self.data+[path], self.new, self.old))

    def test_unverifiable_publication_blocks(self):
        for health in [{}, {'checked_at': '2026-11-11T03:00:00'}, {'checked_at': 'invalid'}]:
            self.assertFalse(allowed(self.data, self.new, health))
            self.assertFalse(allowed(self.data, health, self.old))

if __name__ == '__main__': unittest.main()
