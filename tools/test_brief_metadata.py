"""Keep research commentary distinct from the original DOI-identified papers."""
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

from publication_links import brief_slugs_by_number, normalize_doi


ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://bliss.yonsei.ac.kr'


class BriefMetadata(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.links, self.meta, self.nodes = [], [], []
        self._script = None
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link':
            self.links.append(attrs)
        elif tag == 'meta':
            self.meta.append(attrs)
        elif tag == 'script' and attrs.get('type') == 'application/ld+json':
            self._script = []

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self._script is not None:
            document = json.loads(''.join(self._script))
            self._script = None
            self.nodes.extend(document.get('@graph', [document]))

    def of_type(self, name):
        return [node for node in self.nodes if node.get('@type') == name]


def as_list(value):
    return value if isinstance(value, list) else [value]


class BriefMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = json.loads((ROOT / 'resources/data/publications.json').read_text())
        cls.publications = json.loads((ROOT / 'data/publications.json').read_text())['publications']
        cls.pages = []
        for entry in cls.catalogue:
            path = ROOT / 'resources' / entry['language'] / 'papers' / (entry['slug'] + '.html')
            cls.pages.append((entry, BriefMetadata(path.read_text())))

    def test_catalogue_covers_every_current_publication_in_both_languages(self):
        routes = brief_slugs_by_number(self.publications, self.catalogue)
        count = len(self.publications)
        self.assertGreater(count, 0)
        self.assertEqual(len(routes), count)
        self.assertEqual(len(self.catalogue), count * 2)
        self.assertEqual({normalize_doi(p['link']) for p in self.publications},
                         {normalize_doi(e['doi']) for e in self.catalogue})
        self.assertEqual(Counter(e['language'] for e in self.catalogue), {'en': count, 'ko': count})
        expected = {f"resources/{e['language']}/papers/{e['slug']}.html" for e in self.catalogue}
        actual = {
            str(p.relative_to(ROOT))
            for language in ('en', 'ko')
            for p in (ROOT / 'resources' / language / 'papers').glob('*.html')
            if not p.stem.isdigit()
        }
        self.assertEqual(actual, expected)

    def test_canonical_and_bilingual_alternates_remain_summary_urls(self):
        for entry, metadata in self.pages:
            with self.subTest(url=entry['url']):
                canonical = [l['href'] for l in metadata.links if l.get('rel') == 'canonical']
                own_url = f"{SITE}/resources/{entry['language']}/papers/{entry['slug']}.html"
                self.assertEqual(entry['url'], own_url)
                self.assertEqual(canonical, [own_url])
                alternates = [
                    (l.get('hreflang'), l.get('href')) for l in metadata.links
                    if l.get('rel') == 'alternate' and l.get('hreflang') in ('en', 'ko')
                ]
                self.assertCountEqual(alternates, [
                    (lang, f"{SITE}/resources/{lang}/papers/{entry['slug']}.html")
                    for lang in ('en', 'ko')
                ])
                self.assertEqual([m.get('content') for m in metadata.meta
                                  if m.get('property') == 'og:url'], [own_url])

    def test_original_paper_has_separate_doi_identity_and_page_references(self):
        for entry, metadata in self.pages:
            with self.subTest(url=entry['url']):
                pages, articles = metadata.of_type('WebPage'), metadata.of_type('ScholarlyArticle')
                self.assertEqual(len(pages), 1)
                self.assertEqual(len(articles), 1)
                page, article = pages[0], articles[0]
                doi = normalize_doi(entry['doi'])
                doi_url = 'https://doi.org/' + doi
                self.assertEqual(page['@id'], entry['url'] + '#page')
                self.assertEqual(page['url'], entry['url'])
                self.assertEqual(page['inLanguage'], entry['language'])
                self.assertNotIn('mainEntity', page)
                self.assertEqual(article['@id'], doi_url)
                self.assertEqual(article['url'], doi_url)
                identifiers = as_list(article['identifier'])
                self.assertEqual([
                    normalize_doi(i.get('value')) for i in identifiers
                    if i.get('propertyID', '').upper() == 'DOI'
                ], [doi])
                self.assertIn({'@id': doi_url}, as_list(page['about']))
                self.assertIn({'@id': doi_url}, as_list(page['citation']))
                ids = [n['@id'] for n in metadata.nodes if '@id' in n]
                self.assertEqual(len(ids), len(set(ids)))

    def test_editorial_description_and_classifications_belong_to_webpage(self):
        for entry, metadata in self.pages:
            with self.subTest(url=entry['url']):
                page, article = metadata.of_type('WebPage')[0], metadata.of_type('ScholarlyArticle')[0]
                self.assertTrue(page.get('description'))
                descriptions = [m.get('content') for m in metadata.meta if m.get('name') == 'description']
                self.assertEqual(descriptions, [page['description']])
                self.assertTrue(page.get('keywords'))
                for field in ('description', 'abstract', 'keywords', 'image'):
                    self.assertNotIn(field, article)
                self.assertTrue(article.get('name'))
                self.assertEqual(article['headline'], article['name'])
                self.assertTrue(article.get('author'))
                self.assertTrue(article.get('datePublished'))
                self.assertTrue(article.get('isPartOf'))
                for image in as_list(page.get('image', [])):
                    self.assertEqual(image['@type'], 'ImageObject')
                    for field in ('contentUrl', 'caption', 'creditText', 'license', 'acquireLicensePage'):
                        self.assertTrue(image.get(field), field)

    def test_no_scholar_paper_tags_or_noindex_on_commentary_pages(self):
        for entry, metadata in self.pages:
            with self.subTest(url=entry['url']):
                self.assertFalse([m for m in metadata.meta
                                  if m.get('name', '').lower().startswith('citation_')])
                for meta in metadata.meta:
                    if meta.get('name', '').lower() in ('robots', 'googlebot', 'googlebot-news'):
                        self.assertNotIn('noindex', meta.get('content', '').lower())

    def test_lab_publishes_library_without_claiming_original_article(self):
        for entry, metadata in self.pages:
            with self.subTest(url=entry['url']):
                article = metadata.of_type('ScholarlyArticle')[0]
                for publisher in as_list(article.get('publisher', [])):
                    self.assertNotEqual(publisher.get('@id'), SITE + '/#lab')
                    self.assertNotIn('bliss', publisher.get('name', '').lower())
                    self.assertNotEqual(publisher.get('url', '').rstrip('/'), SITE)
                websites = metadata.of_type('WebSite')
                self.assertEqual(len(websites), 1)
                self.assertEqual(websites[0]['publisher'], {'@id': SITE + '/#lab'})


if __name__ == '__main__':
    unittest.main()
