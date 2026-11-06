import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from notion_bibliography import merge_bibliography


class NotionBibliographyTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'data').mkdir()
        (self.root / 'data/team.json').write_text(json.dumps({
            'pi': {'nameKr': '서정목', 'nameEn': 'Jungmok Seo'},
            'members': [{'nameKr': '김태영', 'nameEn': 'Tae Young Kim'}],
        }), encoding='utf-8')
        self.paper = {
            'number': 1, 'year': 2025, 'title': 'Publisher-corrected title',
            'authors': '<strong>Jungmok Seo</strong><sup>*</sup>, Other Author',
            'journal': 'Journal, 2, 3 (2025)', 'link': 'https://doi.org/10.1000/existing',
            'image': 'images/publications/original.png', 'displayLabel': 'Invited Review',
            'press': {'url': 'https://example.org/press', 'label': '보도', 'labelEn': 'Coverage'},
            'awards': ['Verified award'],
        }
        self.patent = {
            'number': '10-2025-0000001', 'country': 'KR', 'year': 2025,
            'title': '코팅 조성물', 'titleEn': 'Coating composition',
            'inventors': '서정목, 김태영', 'inventorsEn': 'Jungmok Seo, Tae Young Kim',
            'status': '출원', 'statusEn': 'Filed', 'applicationDate': '2025-06-18',
        }
        self.site = {'publications': [self.paper], 'patents': [self.patent], 'custom': {'keep': True}}

    def merge(self, papers=(), patents=()):
        return merge_bibliography(self.site, list(papers), list(patents), root=self.root)

    def test_only_explicit_notion_fields_override_live_values(self):
        row = {
            'Number': 1, 'DOI Link': 'https://doi.org/10.1000/existing', 'Status': 'Published',
            'Name': 'Older Notion title', 'Journal': 'Older journal record', 'Authors': 'Wrong Name',
            'Image Path': '', 'Press': '', 'Impact Factor': 14.1,
            '_changed_fields': ['Image Path', 'Press', 'Impact Factor'],
        }
        result = self.merge([row])
        self.assertEqual(result['publications'], [{**self.paper, 'impactFactor': 14.1}])
        self.assertEqual(result['custom'], {'keep': True})
        self.assertNotIn('impactFactor', self.paper)
        row.pop('_changed_fields')
        self.assertEqual(self.merge([row]), self.site)

    def test_author_edits_preserve_roles_and_confirm_lab_bolding(self):
        row = {
            'Number': 1, 'DOI Link': '10.1000/existing', 'Status': 'Published',
            'Authors': 'Tae Young Kim†, Jungmok Seo, Other Author', '_changed_fields': ['Authors'],
        }
        self.assertEqual(self.merge([row])['publications'][0]['authors'],
                         '<strong>Tae Young Kim</strong><sup>†</sup>, '
                         '<strong>Jungmok Seo</strong><sup>*</sup>, Other Author')
        row['Authors'] = 'Tae Young Kim, Other Author'
        with self.assertRaisesRegex(ValueError, 'removes a marked author'):
            self.merge([row])

    def test_identified_publication_cannot_be_renumbered_or_replaced(self):
        prior = {'Number': 1, 'DOI Link': '10.1000/existing', 'Status': 'Published'}
        row = {**prior, '_previous': prior, '_changed_fields': ['Number'], 'Number': 2}
        with self.assertRaisesRegex(ValueError, 'renumbering'):
            self.merge([row])
        row = {**prior, '_previous': prior, '_changed_fields': ['DOI Link'], 'DOI Link': '10.1000/different'}
        with self.assertRaisesRegex(ValueError, 'DOI cannot be replaced'):
            self.merge([row])
        row = {**prior, '_previous': prior, '_changed_fields': ['Status'], 'Status': 'Accepted'}
        with self.assertRaisesRegex(ValueError, 'cannot regress'):
            self.merge([row])

    def test_publish_requires_doi_and_existing_local_image_when_provided(self):
        row = {'Number': 2, 'Status': 'Published', 'Name': 'New paper', 'Authors': 'Jungmok Seo*',
               'Year': 2026, 'Journal': 'Journal, 3, 4 (2026)'}
        with self.assertRaisesRegex(ValueError, 'verified DOI Link'):
            self.merge([row])
        row.update({'DOI Link': 'doi:10.1000/new', 'Image Path': 'images/publications/new.png'})
        with self.assertRaisesRegex(ValueError, 'image does not exist'):
            self.merge([row])
        image = self.root / row['Image Path']
        image.parent.mkdir(parents=True)
        image.touch()
        result = self.merge([row])['publications'][0]
        self.assertEqual((result['number'], result['link'], result['image']),
                         (2, 'https://doi.org/10.1000/new', row['Image Path']))

    def test_new_patent_uses_verified_english_names_and_skips_withdrawn_records(self):
        row = {
            'Patent Number': '10-2026-0000002', 'Country': 'KR', 'Status': '출원', 'Year': 2026,
            'Name': '접착제 제조법', 'Title (EN)': 'Method of making an adhesive', 'Inventors': '김태영, 서정목',
        }
        result = self.merge(patents=[row, {**row, 'Patent Number': '10-2026-0000003', 'Status': '취하'}])
        self.assertEqual(len(result['patents']), 2)
        self.assertEqual(result['patents'][0]['inventorsEn'], 'Tae Young Kim, Jungmok Seo')
        self.assertEqual(result['patents'][0]['statusEn'], 'Filed')
        row['Inventors'] = '홍길동'
        with self.assertRaisesRegex(ValueError, 'spelling requires confirmation'):
            self.merge(patents=[row])
        row['Inventors EN'] = 'Gil Dong Hong'
        self.assertEqual(self.merge(patents=[row])['patents'][0]['inventorsEn'], 'Gil Dong Hong')

    def test_patent_status_keeps_application_date_and_requires_bilingual_edit(self):
        row = {'Patent Number': self.patent['number'], 'Country': 'KR', 'Status': '공개',
               '_changed_fields': ['Status']}
        self.assertEqual(self.merge(patents=[row])['patents'][0],
                         {**self.patent, 'status': '공개', 'statusEn': 'Published'})
        row.update({'Status': '취하'})
        with self.assertRaisesRegex(ValueError, 'cannot become nonpublic'):
            self.merge(patents=[row])
        row.update({'Status': '출원', 'Name': '다른 조성물', '_changed_fields': ['Name']})
        with self.assertRaisesRegex(ValueError, 'Title \\(EN\\) update'):
            self.merge(patents=[row])


if __name__ == '__main__':
    unittest.main()
