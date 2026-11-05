"""Check that editorial labels stay separate from original publication titles."""
from html.parser import HTMLParser
import unittest

from prerender import render_publications, render_patents
from build_llms import patent_lines


class TextParts(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.text, self.anchor_text, self.tags = [], [], []
        self.in_anchor = False
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == 'a':
            self.in_anchor = True

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_anchor = False

    def handle_data(self, data):
        self.text.append(data)
        if self.in_anchor:
            self.anchor_text.append(data)


class EditorialLabelTests(unittest.TestCase):
    def render(self, label=None):
        paper = {
            'number': 74, 'year': 2024, 'title': 'SiO<sub>2</sub> publication',
            'authors': 'A. Author', 'journal': 'Example Journal, 2 (2024)',
            'link': 'https://doi.org/10.1000/example',
        }
        if label is not None:
            paper['displayLabel'] = label
        return TextParts(render_publications({'publications': [paper]}, {}))

    def test_label_is_visible_once_outside_title_link(self):
        page = self.render('Invited Review')
        self.assertEqual(''.join(page.text).count('[Invited Review]'), 1)
        self.assertNotIn('Invited Review', ''.join(page.anchor_text))
        self.assertIn('SiO2 publication', ''.join(page.anchor_text))
        self.assertIn('sub', page.tags)

    def test_label_markup_is_escaped_separately(self):
        label = '<img src=x onerror=alert(1)> & "Review"'
        page = self.render(label)
        self.assertEqual(''.join(page.text).count('[' + label + ']'), 1)
        self.assertNotIn('img', page.tags)
        self.assertNotIn(label, ''.join(page.anchor_text))

    def test_missing_label_does_not_add_brackets(self):
        page = self.render()
        self.assertNotIn('[', ''.join(page.text))
        self.assertIn('SiO2 publication', ''.join(page.anchor_text))


class PatentFallbackTests(unittest.TestCase):
    def record(self, **overrides):
        record = {
            'number': '10-2026-0123456', 'year': 2026, 'country': 'KR',
            'title': '습윤 조직 접착제', 'titleEn': 'Wet-Tissue Adhesive',
            'inventors': '서정목, 김태영', 'inventorsEn': 'Jungmok Seo, Tae Young Kim',
            'status': '출원', 'statusEn': 'Filed',
        }
        record.update(overrides)
        return record

    def test_patents_exist_in_static_html_with_both_languages(self):
        markup = render_patents({'patents': [self.record()]})
        page = TextParts(markup)
        self.assertIn('습윤 조직 접착제', ''.join(page.text))
        self.assertIn('10-2026-0123456', ''.join(page.text))
        self.assertIn('[출원]', ''.join(page.text))
        self.assertIn('data-en="Wet-Tissue Adhesive"', markup)
        self.assertIn('data-en="Jungmok Seo, Tae Young Kim"', markup)
        self.assertIn('data-en="[Filed]"', markup)
        self.assertIn('noscript', page.tags)
        self.assertIn('#patentSection .patent-list { max-height: none;', markup)

    def test_patent_titles_remain_text_before_and_after_language_toggle(self):
        dangerous = '<img src=x onerror=alert(1)> & "Adhesive"'
        markup = render_patents({'patents': [self.record(title=dangerous, titleEn=dangerous)]})
        page = TextParts(markup)
        self.assertIn(dangerous, ''.join(page.text))
        self.assertNotIn('img', page.tags)

        class EnglishTitles(HTMLParser):
            def __init__(self):
                super().__init__()
                self.values = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get('class') == 'patent-title':
                    self.values.append(attrs['data-en'])

        attrs = EnglishTitles()
        attrs.feed(markup)
        toggled = TextParts(attrs.values[0])
        self.assertEqual(''.join(toggled.text), dangerous)
        self.assertNotIn('img', toggled.tags)

    def test_empty_patents_do_not_leave_a_stale_count(self):
        self.assertEqual(render_patents({'patents': []}), '')
        self.assertEqual(render_patents({}), '')

    def test_llms_retains_number_bilingual_titles_and_application_status(self):
        text = '\n'.join(patent_lines([self.record()]))
        for value in ['10-2026-0123456', 'Wet-Tissue Adhesive', '습윤 조직 접착제',
                      'Jungmok Seo, Tae Young Kim', '서정목, 김태영', 'status: Filed (출원)']:
            self.assertIn(value, text)


if __name__ == '__main__':
    unittest.main()
