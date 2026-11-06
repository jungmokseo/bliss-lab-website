import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from notion_people_news import merge_news, merge_team


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for image in ('images/news/card_image.jpg', 'images/news/replacement.png', 'images/team/new-member.jpg'):
            asset = self.root / image
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.touch()
        self.person = {'id': 'kim-jin', 'initials': 'JK', 'nameKr': '김진', 'nameEn': 'Jin Kim',
                       'roleKr': '석사과정', 'roleEn': 'M.S. Candidate', 'category': 'phd',
                       'email': 'jin.kim@yonsei.ac.kr', 'research': 'Soft materials',
                       'education': ['M.S. Candidate, Yonsei University (2026.09–present)']}
        self.team = {'pi': {'id': 'seo-jungmok', 'nameKr': '서정목', 'nameEn': 'Jungmok Seo', 'bioEn': 'PI bio'},
                     'categories': [{'id': 'phd'}, {'id': 'intern'}],
                     'members': [self.person], 'alumni': [{'nameKr': '이연', 'nameEn': 'Yeon Lee'}]}
        self.team_row = {'_id': 'member-row', 'Name': '김진', 'Name EN': 'Jin Kim', 'Active': True,
                         'Role': 'M.S. Student', 'Email': 'jin.kim@yonsei.ac.kr',
                         'Research Topic': 'Soft materials', 'Order': 4, 'Photo': ''}
        self.article = {'title': '수상 소식', 'titleEn': 'Award news', 'date': '2026-10-05', 'month': 'Oct 2026',
                        'categories': ['Award', 'Event'], 'slug': 'award-news', 'summary': '기존 공개 문안',
                        'summaryEn': 'Original public summary.', 'thumbnail': 'images/news/card_image.jpg',
                        'contentImage': 'images/news/original_content.jpg', 'journal': 'Sample Journal'}
        self.news = {'news': [self.article]}
        self.news_row = {'_id': 'news-row', 'Name': '수상 소식', 'Name EN': 'Award news', 'Date': '2026-10-05',
                         'Category': 'Award', 'Content': '출처: 내부 메일', 'Image': r'images/news/card\_image.jpg',
                         'Public Summary KR': '기존 공개 문안', 'Summary EN': 'Original public summary.'}

    def delta(self, original, changes):
        return dict(original, **changes, _previous=deepcopy(original), _changed_fields=list(changes))

    def test_team_preserves_website_overrides_and_protected_data(self):
        before = deepcopy(self.team)
        row = dict(self.team_row, **{'Name EN': 'Jin K.', 'Role': 'M.S./Ph.D. Student'})
        update = self.delta(row, {'Research Topic': 'Hydrogel electrodes', 'Email': ''})
        out = merge_team(self.team, [update], root=self.root)
        self.assertEqual(out['members'][0], dict(self.person, research='Hydrogel electrodes'))
        for protected in ('pi', 'categories', 'alumni'):
            self.assertEqual(out[protected], before[protected])
        self.assertEqual(self.team, before)

    def test_team_renames_without_losing_the_existing_portrait_identity(self):
        update = self.delta(self.team_row, {'Name': '김새진', 'Name EN': 'Saejin Kim'})
        out = merge_team(self.team, [update], root=self.root)
        self.assertEqual(out['members'][0], dict(self.person, nameKr='김새진', nameEn='Saejin Kim'))

    def test_team_holds_inactivation_private_email_and_site_role_conflict(self):
        cases = [({'Active': '__NO__'}, 'inactive'),
                 ({'Email': 'private@example.com'}, 'valid yonsei'),
                 ({'Name EN': '<img src=x onerror=alert(1)>'}, 'plain, single-line'),
                 ({'Order': 5}, 'full roster review')]
        for change, message in cases:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                merge_team(self.team, [self.delta(self.team_row, change)], root=self.root)
        old = dict(self.team_row, Role='M.S./Ph.D. Student')
        with self.assertRaisesRegex(ValueError, 'published role or a site exception'):
            merge_team(self.team, [self.delta(old, {'Role': 'Ph.D. Student'})], root=self.root)

    def test_team_adds_complete_active_member_with_existing_portrait(self):
        new = {'_id': 'new-member', 'Name': '새 연구원', 'Name EN': 'New Member', 'Active': '__YES__',
               'Role': 'Undergraduate', 'Research Topic': 'Device packaging', 'Photo': 'images/team/new-member.jpg'}
        out = merge_team(self.team, [new], root=self.root)
        self.assertEqual(out['members'][0], self.person)
        self.assertEqual(out['members'][1]['id'], 'new-member')
        self.assertEqual(out['members'][1]['category'], 'intern')
        self.assertEqual(out['members'][1]['education'], [])
        with self.assertRaisesRegex(ValueError, 'existing local image'):
            merge_team(self.team, [dict(new, Photo='images/team/absent.jpg')], root=self.root)

    def test_news_updates_bilingual_content_and_keeps_editorial_fields(self):
        update = self.delta(self.news_row, {'Name': '수상 소식 수정', 'Name EN': 'Updated award news',
                                           'Public Summary KR': '수정 공개 문안', 'Summary EN': 'New public summary.',
                                           'Image': 'images/news/replacement.png', 'Date': '2026-11-01'})
        update['_text'] = '한국어\n옛 본문\nEnglish\nOld content.'
        out = merge_news(self.news, [update], root=self.root)
        self.assertEqual(out['news'][0], dict(self.article, title='수상 소식 수정', titleEn='Updated award news',
                                             summary='수정 공개 문안', summaryEn='New public summary.',
                                             date='2026-11-01', month='Nov 2026', thumbnail='images/news/replacement.png'))

    def test_news_preserves_site_bilingual_copy_when_only_internal_content_changes(self):
        update = self.delta(self.news_row, {'Content': '출처: 새 내부 메일'})
        self.assertEqual(merge_news(self.news, [update], root=self.root), self.news)
        previous = dict(self.news_row, **{'Public Summary KR': '', 'Summary EN': ''})
        update = self.delta(previous, {'Content': '출처: 새 내부 메일'})
        with self.assertRaisesRegex(ValueError, 'unlabelled Content'):
            merge_news(self.news, [update], root=self.root)

    def test_news_requires_safe_bilingual_summary_and_retains_blank_fields(self):
        for change, message in [({'Summary EN': ''}, 'both Korean and English'),
                                ({'Summary EN': '한국어'}, 'English page'),
                                ({'Public Summary KR': '메일 링크 https://mail.google.com/mail/'}, 'internal source')]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                merge_news(self.news, [self.delta(self.news_row, change)], root=self.root)
        out = merge_news(self.news, [self.delta(self.news_row, {'Name EN': '', 'Image': '', 'Content': ''})], root=self.root)
        self.assertEqual(out, self.news)

    def test_news_adds_bilingual_body_without_private_blocks_or_supports_title_only(self):
        new = {'_id': 'new-news', 'Name': '연구 발표', 'Name EN': 'Research presentation',
               'date:Date:start': '2026-11-06', 'Category': 'Event', 'Image': r'images/news/card\_image.jpg'}
        out = merge_news(self.news, [new], root=self.root)
        self.assertEqual(out['news'][0]['summary'], '')
        self.assertEqual(out['news'][0]['thumbnail'], 'images/news/card_image.jpg')
        bilingual = dict(new, Content='내부 내용',
                         _text='## 한국어\n공개 한글.\n## English\nPublic English.\n관리 근거\nhttps://mail.google.com/mail/')
        out = merge_news(self.news, [bilingual], root=self.root)
        self.assertEqual((out['news'][0]['summary'], out['news'][0]['summaryEn']), ('공개 한글.', 'Public English.'))
        with self.assertRaisesRegex(ValueError, 'existing local image'):
            merge_news(self.news, [dict(new, Image='images/news/../secret.jpg')], root=self.root)

    def test_news_holds_conflicts_and_ambiguous_identity_without_mutating_input(self):
        before = deepcopy(self.news)
        prev = dict(self.news_row, **{'Summary EN': 'Notion draft not previously published.'})
        with self.assertRaisesRegex(ValueError, 'summaryEn conflicts'):
            merge_news(self.news, [self.delta(prev, {'Summary EN': 'New summary.'})], root=self.root)
        duplicated = {'news': [self.article, dict(self.article, slug='second-news')]}
        with self.assertRaisesRegex(ValueError, 'different News records'):
            merge_news(duplicated, [self.delta(self.news_row, {'Name EN': 'Award announcement'})], root=self.root)
        self.assertEqual(self.news, before)


if __name__ == '__main__':
    unittest.main()
