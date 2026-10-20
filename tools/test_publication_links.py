"""Regression checks for publication renumbering and ambiguous brief identities."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

from publication_links import brief_slugs_by_number, normalize_doi


def catalogue_entry(doi, slug, number=1):
    return [{'doi': doi, 'slug': slug, 'number': number, 'language': language}
            for language in ('en', 'ko')]


class DoiMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name') == 'citation_doi':
            self.values.append(normalize_doi(attrs.get('content')))


class BriefIdentityTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = (catalogue_entry('10.1002/advs.78062', 'advs-78062', 102)
                          + catalogue_entry('10.1016/j.mser.2026.101285', 'mser-2026-101285', 101))

    def test_number_changes_keep_original_doi_destinations(self):
        # A new item takes an old label, and older papers acquire new labels.
        publications = [
            {'number': 102, 'link': 'https://doi.org/10.1002/new.123'},
            {'number': 104, 'link': 'https://doi.org/10.1002/advs.78062'},
            {'number': 103, 'link': 'https://doi.org/10.1016/j.mser.2026.101285'},
        ]
        self.assertEqual(brief_slugs_by_number(publications, self.catalogue),
                         {104: 'advs-78062', 103: 'mser-2026-101285'})

    def test_missing_doi_never_inherits_old_number_link(self):
        for link in ('', None, 'https://example.org/article'):
            with self.subTest(link=link):
                self.assertEqual(brief_slugs_by_number([{'number': 102, 'link': link}], self.catalogue), {})

    def test_doi_url_and_case_normalization(self):
        self.assertEqual(normalize_doi(' HTTPS://DX.DOI.ORG/10.1002%2FADVS.78062 '),
                         '10.1002/advs.78062')
        self.assertEqual(normalize_doi('doi: 10.1002/ADVS.78062'), '10.1002/advs.78062')
        self.assertEqual(normalize_doi('https://doi.org.example.com/10.1002/advs.78062'), '')

    def test_bilingual_slug_conflict_is_rejected(self):
        broken = copy.deepcopy(self.catalogue)
        broken[1]['slug'] = 'different-brief'
        with self.assertRaisesRegex(ValueError, 'conflicting bilingual slugs'):
            brief_slugs_by_number([], broken)

    def test_slug_cannot_identify_two_dois(self):
        broken = self.catalogue + catalogue_entry('10.1002/other.123', 'advs-78062', 50)
        with self.assertRaisesRegex(ValueError, 'shared by DOI'):
            brief_slugs_by_number([], broken)

    def test_duplicate_language_entry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate en entry'):
            brief_slugs_by_number([], self.catalogue + [dict(self.catalogue[0])])

    def test_missing_language_is_rejected_before_two_language_links_are_generated(self):
        with self.assertRaisesRegex(ValueError, 'missing brief language ko'):
            brief_slugs_by_number([], [self.catalogue[0]])

    def test_duplicate_homepage_doi_is_rejected(self):
        publications = [{'number': n, 'link': 'https://doi.org/10.1002/advs.78062'} for n in (101, 102)]
        with self.assertRaisesRegex(ValueError, 'duplicate entries #101 and #102'):
            brief_slugs_by_number(publications, self.catalogue)

    def test_duplicate_homepage_display_number_is_rejected(self):
        publications = [
            {'number': 102, 'link': 'https://doi.org/10.1002/advs.78062'},
            {'number': 102, 'link': 'https://doi.org/10.1016/j.mser.2026.101285'},
        ]
        with self.assertRaisesRegex(ValueError, 'duplicate display number 102'):
            brief_slugs_by_number(publications, self.catalogue)

    def test_current_destinations_identify_the_linked_doi_in_both_languages(self):
        root = Path(__file__).resolve().parents[1]
        publications = json.loads((root / 'data/publications.json').read_text())['publications']
        catalogue = json.loads((root / 'resources/data/publications.json').read_text())
        links = brief_slugs_by_number(publications, catalogue)
        for publication in publications:
            slug = links.get(publication['number'])
            if slug is None:
                continue
            doi = normalize_doi(publication['link'])
            for language in ('en', 'ko'):
                with self.subTest(doi=doi, language=language):
                    page = root / 'resources' / language / 'papers' / f'{slug}.html'
                    markup = page.read_text()
                    # Check the destination's declared identity, not its display number.
                    metadata = DoiMetadata()
                    metadata.feed(markup)
                    self.assertEqual(metadata.values, [doi])


if __name__ == '__main__':
    unittest.main()
