"""Exercise release-blocking patent translation and identity regressions."""
from copy import deepcopy
import unittest

from check_bilingual import Report, check_patents


class PatentBilingualGateTests(unittest.TestCase):
    def test_shared_original_title_passes_but_lost_translation_and_wrong_status_fail(self):
        patent = {
            'country': 'US', 'number': 'US 123', 'title': 'Original English Title',
            'titleEn': 'Original English Title', 'inventors': 'Jungmok Seo',
            'inventorsEn': 'Jungmok Seo', 'status': '등록', 'statusEn': 'Registered',
        }
        baseline = Report()
        check_patents([patent], baseline)
        self.assertFalse(baseline.errors)
        self.assertTrue(baseline.evidence)

        untranslated = deepcopy(patent)
        untranslated['titleEn'] = '번역 누락'
        untranslated['statusEn'] = 'Filed'
        regression = Report()
        check_patents([patent, untranslated], regression)
        messages = ' '.join(error['message'] for error in regression.errors)
        self.assertIn('Duplicate country/number', messages)
        self.assertIn('titleEn contains Korean text', messages)
        self.assertIn('Status mismatch', messages)


if __name__ == '__main__':
    unittest.main()
