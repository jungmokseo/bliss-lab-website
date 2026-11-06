"""Safety checks for the snapshot boundary and retained public records."""
import importlib.util
from copy import deepcopy
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('sync_notion', Path(__file__).resolve().parents[1] / 'sync-notion.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'version': 1, 'captured_at': '2026-11-06T00:00:00Z', 'sources': {
            key: [{'_id': f'{i:032x}', 'Name': 'Existing text', 'Image': 'existing.jpg'}]
            for i, key in enumerate(sync.SOURCES)
        }}
        self.hashes = {key: 'public-copy' for key in sync.SOURCES}
        self.baseline = {'snapshot': self.snapshot, 'site_hashes': self.hashes}

    def test_delta_has_previous_identity_and_only_edited_fields(self):
        current = deepcopy(self.snapshot)
        current['sources']['news'][0]['Name'] = 'Edited title'
        d = sync.differences(current, self.baseline, self.hashes)
        self.assertEqual(d['news'][0]['_changed_fields'], ['Name'])
        self.assertEqual(d['news'][0]['_previous']['Name'], 'Existing text')
        self.assertTrue(d['news'][0]['_site_unchanged'])
        self.assertFalse(any(rows for key, rows in d.items() if key != 'news'))

    def test_source_row_loss_and_duplicate_ids_fail_closed(self):
        current = deepcopy(self.snapshot)
        current['sources']['news'].append(deepcopy(current['sources']['news'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            sync.validate_snapshot(current, fresh=False)
        current['sources']['news'] = []
        with self.assertRaisesRegex(ValueError, 'disappeared'):
            sync.differences(current, self.baseline, self.hashes)

    def test_public_history_and_assets_cannot_be_erased(self):
        before = {'members': [{'id': 'm', 'education': ['Prior degree'], 'image': 'portrait.jpg'}]}
        for after in ({'members': []}, {'members': [{'id': 'm', 'education': [], 'image': ''}]}):
            with self.subTest(after=after), self.assertRaises(ValueError):
                sync.keep_fields(before, after, 'members', lambda x: x['id'])


if __name__ == '__main__':
    unittest.main()
