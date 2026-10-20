"""Check that editorial labels stay separate from original publication titles."""
from html.parser import HTMLParser
import unittest

from prerender import render_publications


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


if __name__ == '__main__':
    unittest.main()
