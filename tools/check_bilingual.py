#!/usr/bin/env python3
"""Check bilingual data completeness and route identity without rewriting content.

Run: python3 tools/check_bilingual.py [--json] [--root SITE_DIRECTORY]
Exit 1 means a missing translation, inconsistent identity, or broken language route.
Shared English paper titles and proper names are reported as evidence, not errors.
This checks structure and metadata; it does not certify translation semantics.
"""
import argparse
from collections import defaultdict
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

from publication_links import normalize_doi


SITE = 'https://bliss.yonsei.ac.kr'
STATUS_EN = {
    '출원': {'Filed'}, '등록': {'Registered'}, '공개': {'Published'},
    # Existing US and Korean records distinguish abandoned and lapsed rights.
    '소멸': {'Abandoned', 'Lapsed'}, '거절': {'Rejected'}, '취하': {'Withdrawn'},
}
HANGUL = re.compile(r'[가-힣]')


class Report:
    def __init__(self):
        self.errors, self.evidence, self.counts = [], [], {}

    def error(self, location, message):
        self.errors.append({'location': location, 'message': message})

    def note(self, location, message):
        self.evidence.append({'location': location, 'message': message})

    def pair(self, item, kr, en, location):
        for field in (kr, en):
            if not isinstance(item.get(field), str) or not item[field].strip():
                self.error(location, f'Missing nonempty {field}')
        if item.get(kr) and item.get(en):
            if HANGUL.search(item[en]):
                self.error(location, f'{en} contains Korean text; review English value')
            elif item[kr] == item[en]:
                self.note(location, f'Shared value in {kr}/{en}: {item[en]}')

    def as_dict(self):
        return {'ok': not self.errors, 'counts': self.counts,
                'errors': self.errors, 'evidence': self.evidence,
                'scope': 'Data completeness, metadata identity and language routes; '
                         'translation meaning requires editorial review.'}


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs), self.getpos()[0]))


def check_patents(patents, report):
    seen = set()
    for index, patent in enumerate(patents):
        location = f'patents[{index}] {patent.get("number", "")}'
        key = (patent.get('country'), patent.get('number'))
        if not all(isinstance(v, str) and v.strip() for v in key):
            report.error(location, 'Country and patent number are required')
        elif key in seen:
            report.error(location, f'Duplicate country/number: {key}')
        seen.add(key)
        for kr, en in [('title', 'titleEn'), ('inventors', 'inventorsEn'), ('status', 'statusEn')]:
            report.pair(patent, kr, en, location)
        allowed = STATUS_EN.get(patent.get('status'))
        if allowed is None:
            report.error(location, f'Unrecognized Korean status: {patent.get("status")}')
        elif patent.get('statusEn') not in allowed:
            report.error(location, f'Status mismatch: {patent.get("status")} / {patent.get("statusEn")}')
    report.counts['patents'] = len(patents)


def check_data(publications, team, news, report):
    check_patents(publications.get('patents', []), report)
    for index, item in enumerate(news.get('news', [])):
        location = f'news[{index}] {item.get("slug", "")}'
        report.pair(item, 'title', 'titleEn', location)
        if item.get('summary'):
            report.pair(item, 'summary', 'summaryEn', location)
    people = [('pi', team.get('pi', {}))]
    people += [(f'members[{i}]', item) for i, item in enumerate(team.get('members', []))]
    for location, person in people:
        report.pair(person, 'nameKr', 'nameEn', location)
        report.pair(person, 'roleKr', 'roleEn', location)
    report.pair(team.get('pi', {}), 'bioKr', 'bioEn', 'pi')
    for index, person in enumerate(team.get('alumni', [])):
        report.pair(person, 'nameKr', 'nameEn', f'alumni[{index}]')
    for index, category in enumerate(team.get('categories', [])):
        report.pair(category, 'labelKr', 'labelEn', f'categories[{index}]')
    report.counts.update(publications=len(publications.get('publications', [])),
                         news=len(news.get('news', [])), members=len(team.get('members', [])),
                         alumni=len(team.get('alumni', [])))


def check_homepage(text, report):
    pairs = 0
    for tag, attrs, line in Markup(text).elements:
        location = f'index.html:{line} <{tag}>'
        for kr, en in [('data-kr', 'data-en'), ('data-href-kr', 'data-href-en')]:
            if kr not in attrs and en not in attrs:
                continue
            pairs += 1
            for field in (kr, en):
                if not attrs.get(field):
                    report.error(location, f'Missing nonempty {field}')
            if attrs.get(kr) == attrs.get(en) and attrs.get(kr):
                report.note(location, f'Shared value in {kr}/{en}: {attrs[kr]}')
    report.counts['homepage_static_attribute_pairs'] = pairs


def check_library(root, catalogue, publications, report):
    pairs = defaultdict(dict)
    for entry in catalogue:
        location = f'catalogue #{entry.get("number")} {entry.get("language")}'
        language = entry.get('language')
        if language not in ('ko', 'en'):
            report.error(location, f'Unsupported language: {language}')
            continue
        if language in pairs[entry.get('number')]:
            report.error(location, 'Duplicate number/language')
        pairs[entry.get('number')][language] = entry
        expected = f'{SITE}/resources/{language}/papers/{entry.get("slug")}.html'
        if entry.get('url') != expected:
            report.error(location, f'Catalogue URL differs from slug route: {entry.get("url")}')
        if not (root / urlsplit(expected).path.lstrip('/')).is_file():
            report.error(location, f'Missing page: {expected}')
    for number, entries in pairs.items():
        location = f'catalogue #{number}'
        if set(entries) != {'ko', 'en'}:
            report.error(location, 'Missing Korean or English catalogue entry')
            continue
        ko, en = entries['ko'], entries['en']
        for field in ('number', 'slug', 'year'):
            if ko.get(field) != en.get(field):
                report.error(location, f'Korean/English {field} differs')
        if normalize_doi(ko.get('doi')) != normalize_doi(en.get('doi')):
            report.error(location, 'Korean/English DOI differs')
        if ko.get('title') == en.get('title'):
            report.note(location, 'Shared original publication title in both languages')
    by_number = {paper.get('number'): paper for paper in publications}
    for number, entries in pairs.items():
        paper = by_number.get(number)
        if paper is None:
            report.error(f'catalogue #{number}', 'No corresponding homepage publication')
        else:
            for language, entry in entries.items():
                if normalize_doi(paper.get('link')) != normalize_doi(entry.get('doi')):
                    report.error(f'publication #{number}', f'{language} catalogue DOI differs')
    for number in by_number.keys() - pairs.keys():
        report.note(f'publication #{number}', 'Listed on the homepage; no reviewed bilingual brief yet')

    routes = {language: {p.relative_to(root / 'resources' / language)
                         for p in (root / 'resources' / language).rglob('*.html')}
              for language in ('ko', 'en')}
    for language, other in [('ko', 'en'), ('en', 'ko')]:
        for relative in sorted(routes[language] - routes[other]):
            report.error(f'resources/{language}/{relative}', f'Missing {other} page at same route')
        for relative in sorted(routes[language]):
            path = root / 'resources' / language / relative
            own_url = f'{SITE}/resources/{language}/{relative.as_posix()}'
            counterpart = f'{SITE}/resources/{other}/{relative.as_posix()}'
            elements = Markup(path.read_text(encoding='utf-8')).elements
            html_lang = [a.get('lang') for t, a, _ in elements if t == 'html']
            if html_lang != [language]:
                report.error(str(path.relative_to(root)), f'Incorrect HTML lang: {html_lang}')
            refreshes = [a.get('content', '') for t, a, _ in elements
                         if t == 'meta' and a.get('http-equiv', '').lower() == 'refresh']
            if refreshes:
                # Frozen numeric aliases redirect inside their own language tree.
                for refresh in refreshes:
                    match = re.search(r'url\s*=\s*(.+)', refresh, re.I)
                    target = urljoin(own_url, match.group(1).strip(' \"\'')) if match else ''
                    if not target.startswith(f'{SITE}/resources/{language}/'):
                        report.error(str(path.relative_to(root)), 'Redirect changes language or has no target')
                    elif not (root / urlsplit(target).path.lstrip('/')).is_file():
                        report.error(str(path.relative_to(root)), 'Redirect target does not exist')
                continue
            alternates = {(a.get('hreflang'), urljoin(own_url, a.get('href', '')))
                          for t, a, _ in elements if t == 'link' and a.get('rel') == 'alternate'}
            numbered_notice = relative.stem.isdigit() and any(
                t == 'meta' and a.get('name') == 'robots' and
                'noindex' in a.get('content', '').lower() for t, a, _ in elements)
            if numbered_notice:
                report.note(str(path.relative_to(root)),
                            'Frozen numbered-address notice is intentionally noindex; '
                            'check its language switch instead of canonical hreflang')
            else:
                for lang, url in ((language, own_url), (other, counterpart)):
                    if (lang, url) not in alternates:
                        report.error(str(path.relative_to(root)), f'Missing correct {lang} hreflang')
            switches = [urljoin(own_url, a.get('href', '')) for t, a, _ in elements
                        if t == 'a' and 'lang-switch' in a.get('class', '').split()]
            if switches != [counterpart]:
                report.error(str(path.relative_to(root)), f'Incorrect language switch: {switches}')
    report.counts.update(library_catalogue_pairs=len(pairs),
                         library_ko_pages=len(routes['ko']), library_en_pages=len(routes['en']))


def audit(root):
    report = Report()
    def read_json(relative):
        return json.loads((root / relative).read_text(encoding='utf-8'))
    try:
        publications = read_json('data/publications.json')
        check_data(publications, read_json('data/team.json'), read_json('data/news.json'), report)
        check_homepage((root / 'index.html').read_text(encoding='utf-8'), report)
        check_library(root, read_json('resources/data/publications.json'),
                      publications.get('publications', []), report)
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.error('input', f'{type(error).__name__}: {error}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--json', action='store_true', help='Emit complete machine-readable evidence')
    args = parser.parse_args()
    result = audit(args.root).as_dict()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('PASS' if result['ok'] else 'FAIL', json.dumps(result['counts'], ensure_ascii=False))
        for error in result['errors']:
            print(f'ERROR {error["location"]}: {error["message"]}')
        print(f'{len(result["evidence"])} shared-value observations; use --json for evidence.')
        print(result['scope'])
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
