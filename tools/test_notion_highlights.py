"""Regression tests for the Notion research highlight merge."""

from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from check_bilingual import Markup
from notion_highlights import LEGACY_DOIS, merge_highlights


ROOT = Path(__file__).resolve().parent.parent
DOI = '10.1016/j.bioactmat.2026.02.003'
ROW_ID = '12345678-5b22-4e71-bf80-34832ed90102'


class HighlightMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text(encoding='utf-8')
        cls.publications = json.loads((ROOT / 'data/publications.json').read_text())['publications']

    def row(self, **changes):
        previous = {
            'Publication Number': 91,  # This now identifies a different paper.
            'Title KR': '담도 스텐트',
            'Title EN': 'Slippery Dopamine–Fluoropolymer Hybrid Surface for Improving Biliary Stent Longevity',
            'Description': '이전 노션 설명',
            'Visible': True,
            'Order': 1,
        }
        return {
            **previous,
            '_id': ROW_ID,
            '_previous': previous,
            '_site_unchanged': True,
            '_changed_fields': list(changes),
            **changes,
        }

    def merge(self, rows, html=None):
        fingerprint = sha256(ROW_ID.replace('-', '').encode()).hexdigest()
        with patch.dict(LEGACY_DOIS, {fingerprint: DOI}):
            return merge_highlights(html if html is not None else self.html, rows,
                                    publications=self.publications, root=ROOT)

    def attributes(self, html, element, class_name):
        return [attrs for tag, attrs, _ in Markup(html).elements
                if tag == element and attrs.get('class') == class_name]

    def test_update_targets_doi_and_preserves_other_cards(self):
        ko = '담도 스텐트 코팅을 평가했습니다.'
        en = 'The study evaluated biliary stent coatings.'
        merged = self.merge([self.row(**{'Description': ko, 'Description EN': en})])
        source_descriptions = self.attributes(self.html, 'div', 'hl-desc')
        new_descriptions = self.attributes(merged, 'div', 'hl-desc')
        self.assertEqual(len(new_descriptions), len(source_descriptions))
        self.assertEqual([i for i, (old, new) in enumerate(zip(source_descriptions, new_descriptions))
                          if old != new], [1])
        self.assertEqual(new_descriptions[1]['data-kr'], ko)
        self.assertEqual(new_descriptions[1]['data-en'], en)
        self.assertEqual(self.attributes(merged, 'a', 'read-link'),
                         self.attributes(self.html, 'a', 'read-link'))

    def test_title_update_escapes_text_in_initial_and_toggled_view(self):
        ko = '담도 스텐트 & 조직 반응 <후속 분석>'
        en = 'Biliary Stents & Tissue Responses <img src=x onerror=alert(1)>'
        merged = self.merge([self.row(**{'Title KR': ko, 'Title EN': en})])
        translated_headings = [attrs for tag, attrs, _ in Markup(merged).elements
                               if tag == 'h3' and attrs.get('data-en') ==
                               'Biliary Stents &amp; Tissue Responses &lt;img src=x onerror=alert(1)&gt;']
        self.assertEqual(len(translated_headings), 1)
        self.assertEqual(unescape(translated_headings[0]['data-kr']), ko)
        self.assertEqual(unescape(translated_headings[0]['data-en']), en)
        self.assertNotIn('<img src=x onerror=alert(1)>', merged)
        self.assertIn('>담도 스텐트 &amp; 조직 반응 &lt;후속 분석&gt;</h3>', merged)

    def test_one_language_update_holds_after_english_exists(self):
        row = self.row(Description='한국어 설명만 편집했습니다.')
        row['_previous']['Description EN'] = 'Existing English description.'
        row['Description EN'] = row['_previous']['Description EN']
        with self.assertRaisesRegex(ValueError, 'update both language fields'):
            self.merge([row])

    def test_first_english_description_can_be_added_on_verified_baseline(self):
        row = self.row(**{'Description EN': 'The previous description in English.'})
        self.assertIn('The previous description in English.', self.merge([row]))
        row['_site_unchanged'] = False
        with self.assertRaisesRegex(ValueError, 'reconcile the current site'):
            self.merge([row])

    def test_unverified_site_baseline_compares_previous_fields(self):
        row = self.row(**{'Description': '새 설명입니다.', 'Description EN': 'New description.'})
        row['_site_unchanged'] = False
        with self.assertRaisesRegex(ValueError, 'reconcile the current site'):
            self.merge([row])
        published = self.attributes(self.html, 'div', 'hl-desc')[1]
        row['_previous']['Description'] = published['data-kr']
        row['_previous']['Description EN'] = published['data-en']
        self.assertIn('New description.', self.merge([row]))

    def test_missing_pair_holds(self):
        row = self.row(Description='한국어만 제공했습니다.')
        with self.assertRaisesRegex(ValueError, 'supply explicit Korean and English values'):
            self.merge([row])

    def test_changes_to_visibility_and_order_hold(self):
        for change in ({'Visible': False}, {'Order': 3}, {'Publication Number': 92}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'review changes'):
                self.merge([self.row(**change)])

    def test_hidden_notion_row_cannot_update_a_published_card(self):
        row = self.row(**{'Description': '새 설명입니다.', 'Description EN': 'New description.'})
        row['Visible'] = row['_previous']['Visible'] = False
        with self.assertRaisesRegex(ValueError, 'hidden Notion row'):
            self.merge([row])

    def test_new_row_cannot_reassign_a_card(self):
        row = self.row(**{'Description': '새 설명입니다.', 'Description EN': 'New description.'})
        row.pop('_previous')
        with self.assertRaisesRegex(ValueError, 'new rows need a manually configured card'):
            self.merge([row])

    def test_conflicting_explicit_doi_holds(self):
        row = self.row(**{'Title KR': '담도 스텐트 평가', 'Title EN': 'Biliary Stent Evaluation'})
        row['DOI'] = '10.1002/adma.202515767'
        with self.assertRaisesRegex(ValueError, 'single DOI binding'):
            self.merge([row])

    def test_bilingual_links_must_agree(self):
        html = self.html.replace('data-href-en="/resources/en/papers/bioactmat-2026-02-003.html"',
                                 'data-href-en="/resources/en/papers/adma-202515767.html"', 1)
        row = self.row(**{'Description': '새 설명입니다.', 'Description EN': 'New description.'})
        with self.assertRaisesRegex(ValueError, 'verify one existing card with both research brief links'):
            self.merge([row], html)

    def test_unchanged_rows_leave_html_byte_for_byte(self):
        row = self.row()
        row['_id'] = '12345678-5b22-4e71-bf80-34832ed90103'
        self.assertEqual(self.merge([row]), self.html)


if __name__ == '__main__':
    unittest.main()
