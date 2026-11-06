"""Apply approved bilingual text changes to existing research highlight cards."""

from hashlib import sha256
from html import escape, unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from publication_links import brief_slugs_by_number, normalize_doi


# Verified legacy page IDs are hashed to keep Notion identifiers out of the
# public repository. Publication Number can change when papers are renumbered.
LEGACY_DOIS = {
    'fc804724bdca124efccc1a052547bffcb4659750f3b06c1f6f76a78b18510ea5': '10.1126/sciadv.adz1228',
    'bf09e752c5aca0193151cb5a27c3430d26290ca3e126499b327795d4f65714ce': '10.1002/advs.202303651',
    '96c20110ccf2c362f9012736204469ab3db7797589f94a92e92879791cf7cf69': '10.1038/s41528-024-00327-x',
    'e9c224f5e546271f5330ad81753cc2dc253533e21994b0fce342620f612cd2ad': '10.1016/j.bioactmat.2026.02.003',
    '656124b65017a376417ede8ee14261cf189734e67d22005de01a908bad89ac90': '10.1002/adfm.202312740',
    'eabd389320f2d9913de8a989510d2872fb6541f4c211b6f146fae08642e41430': '10.1021/acsnano.4c00396',
}

TITLE = re.compile(r'<h3(?P<attrs>[^<>]*)>(?P<body>[^<]*)</h3>')
DESCRIPTION = re.compile(r'<div(?P<attrs>\s+class="hl-desc"[^<>]*)>(?P<body>[^<]*)</div>')
LANG_ATTR = re.compile(r'\s+data-(kr|en)="([^"]*)"')
HANGUL = re.compile(r'[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]')
EDITABLE = {'Title KR', 'Title EN', 'Description', 'Description EN'}


class HighlightCards(HTMLParser):
    """Locate card source spans without reserializing the surrounding HTML."""

    def __init__(self, source):
        super().__init__()
        self.line_offsets = [0] + [match.end() for match in re.finditer('\n', source)]
        self.section_depth = 0
        self.card_depth = 0
        self.cards = []
        self.feed(source)
        self.close()

    def source_position(self):
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get('class') or '').split()
        if tag == 'section' and (self.section_depth or attrs.get('id') == 'highlights'):
            self.section_depth += 1
        if not self.section_depth:
            return
        if tag == 'div' and 'hl-card' in classes and not self.card_depth:
            self.card_start = self.source_position()
            self.card_links = []
            self.card_depth = 1
        elif tag == 'div' and self.card_depth:
            self.card_depth += 1
        elif tag == 'a' and self.card_depth and 'read-link' in classes:
            self.card_links.append(attrs)

    def handle_endtag(self, tag):
        if tag == 'div' and self.card_depth:
            self.card_depth -= 1
            if not self.card_depth:
                self.cards.append((self.card_start, self.source_position() + len('</div>'), self.card_links))
        if tag == 'section' and self.section_depth:
            self.section_depth -= 1


def plain(row, key):
    value = row.get(key)
    return value.strip() if isinstance(value, str) else ''


def bound_doi(row, previous, fingerprint, label):
    legacy = LEGACY_DOIS.get(fingerprint)
    identities = {legacy} if legacy else set()
    for props in (previous, row):
        for key in ('DOI', 'DOI Link'):
            if not plain(props, key):
                continue
            try:
                doi = normalize_doi(plain(props, key))
            except ValueError:
                doi = ''
            if not doi:
                raise ValueError(f'{label}: supply a valid DOI in {key}')
            identities.add(doi)
    if len(identities) != 1:
        raise ValueError(f'{label}: verify a single DOI binding before publishing')
    return identities.pop()


def card_span(cards, slug, label):
    ko = f'/resources/ko/papers/{slug}.html'
    en = f'/resources/en/papers/{slug}.html'
    candidates = [
        (start, end, links) for start, end, links in cards
        if any(link.get('data-href-kr') == ko or link.get('data-href-en') == en for link in links)
    ]
    if len(candidates) == 1:
        start, end, links = candidates[0]
        if (len(links) == 1 and links[0].get('data-href-kr') == ko
                and links[0].get('data-href-en') == en and links[0].get('href') in (ko, en)):
            return start, end
    raise ValueError(f'{label}: verify one existing card with both research brief links')


def replace_pair(card, row, previous, changed, fields, pattern, tag, label):
    if not changed.intersection(fields):
        return card
    matches = list(pattern.finditer(card))
    if len(matches) != 1:
        raise ValueError(f'{label}: review the card markup for {fields[0]}')
    match = matches[0]
    attrs = match.group('attrs')
    languages = LANG_ATTR.findall(attrs)
    if sorted(lang for lang, _ in languages) == ['en', 'kr']:
        values = {lang: unescape(unescape(value)) for lang, value in languages}
        current = values['kr'], values['en']
    elif tag == 'h3' and not languages and 'data-kr' not in attrs and 'data-en' not in attrs:
        current = (unescape(match.group('body')),) * 2
    else:
        raise ValueError(f'{label}: review the card language attributes for {fields[0]}')

    desired = tuple(plain(row, field) for field in fields)
    if desired == current:
        return card
    if not all(desired) or not HANGUL.search(desired[0]) or HANGUL.search(desired[1]):
        raise ValueError(f'{label}: supply explicit Korean and English values in {" / ".join(fields)}')
    old = tuple(plain(previous, field) for field in fields)
    if row.get('_site_unchanged') is not True and current != old:
        raise ValueError(f'{label}: reconcile the current site and previous Notion values for {fields[0]}')
    adding_english = old[0] and not old[1] and fields[1] in changed
    if not changed.issuperset(fields) and not adding_english:
        raise ValueError(f'{label}: review and update both language fields together for {fields[0]}')

    def dataset_text(value):
        # The homepage assigns dataset text to innerHTML when changing language.
        return escape(escape(value, quote=False), quote=True)

    localized_attrs = dict(zip(('kr', 'en'), map(dataset_text, desired)))
    if languages:
        attrs = LANG_ATTR.sub(lambda item: f' data-{item[1]}="{localized_attrs[item[1]]}"', attrs)
    else:
        attrs += f' data-kr="{localized_attrs["kr"]}" data-en="{localized_attrs["en"]}"'
    replacement = f'<{tag}{attrs}>{escape(desired[0], quote=False)}</{tag}>'
    return card[:match.start()] + replacement + card[match.end():]


def merge_highlights(html: str, rows: list[dict], *, publications: list[dict], root: Path) -> str:
    """Merge changed Notion rows using immutable DOI bindings and a public baseline.

    Rows carry flat Notion properties, _id, _previous, and _changed_fields.
    _site_unchanged may be set by the caller after comparing the public section
    with the stored baseline. Unsupported changes stop the entire merge.
    """
    pending = []
    for index, row in enumerate(rows, 1):
        raw_id = row.get('_id')
        page_id = raw_id.replace('-', '').lower() if isinstance(raw_id, str) else ''
        fingerprint = sha256(page_id.encode()).hexdigest() if re.fullmatch(r'[0-9a-f]{32}', page_id) else ''
        label = f'Highlights row {index}'
        if fingerprint:
            label += f' (ref {fingerprint[:8]})'
        previous = row.get('_previous')
        if not isinstance(previous, dict):
            raise ValueError(f'{label}: new rows need a manually configured card and baseline')
        fields = row.get('_changed_fields')
        if not isinstance(fields, (list, tuple, set)) or not all(isinstance(name, str) for name in fields):
            raise ValueError(f'{label}: missing comparison with the previous Notion fields')
        changed = set(fields)
        if not changed:
            continue
        unsupported = changed - EDITABLE
        if unsupported:
            names = sorted(name for name in unsupported if re.fullmatch(r'[A-Za-z_ ]{1,40}', name))
            fields_label = ', '.join(names) if names else 'unrecognized fields'
            raise ValueError(f'{label}: review changes to {fields_label} manually')
        if 'Visible' in row and row['Visible'] not in (True, '__YES__'):
            raise ValueError(f'{label}: review the text change for the hidden Notion row manually')
        pending.append((row, previous, changed, bound_doi(row, previous, fingerprint, label), label))
    if not pending:
        return html

    catalogue = json.loads((root / 'resources/data/publications.json').read_text(encoding='utf-8'))
    brief_slugs = brief_slugs_by_number(publications, catalogue)
    by_doi = {
        normalize_doi(item.get('link')): brief_slugs[int(item['number'])]
        for item in publications if int(item['number']) in brief_slugs
    }
    cards = HighlightCards(html).cards
    replacements = {}
    for row, previous, changed, doi, label in pending:
        slug = by_doi.get(doi)
        if not slug or any(not (root / f'resources/{lang}/papers/{slug}.html').is_file() for lang in ('ko', 'en')):
            raise ValueError(f'{label}: verify that the DOI has published Korean and English research briefs')
        start, end = card_span(cards, slug, label)
        if (start, end) in replacements:
            raise ValueError(f'{label}: multiple Notion rows target the same highlight card')
        card = html[start:end]
        card = replace_pair(card, row, previous, changed, ('Title KR', 'Title EN'), TITLE, 'h3', label)
        card = replace_pair(card, row, previous, changed, ('Description', 'Description EN'), DESCRIPTION, 'div', label)
        replacements[start, end] = card

    for (start, end), card in sorted(replacements.items(), reverse=True):
        html = html[:start] + card + html[end:]
    return html
