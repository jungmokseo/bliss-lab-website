"""Merge changed Notion publication and patent rows into shared website data.

Existing rows are patched only for their explicit ``_changed_fields``. A new
Notion row that identifies an existing website record adopts that record as-is.
``_previous`` supplies the prior Notion identity and status when available.
"""
from collections import defaultdict
from copy import deepcopy
from html import unescape
import json
from math import isfinite
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote, urlsplit

from check_bilingual import HANGUL, STATUS_EN
from publication_links import normalize_doi


PAPER_STATUS = {'Submitted': 0, 'Accepted': 1, 'In Press': 2, 'Published': 3}
PATENT_STATUS = {'출원': 1, '공개': 2, '등록': 3, '소멸': 4}
COUNTRIES = {'KR', 'US', 'PCT', 'KR/EPO/US', 'US/EPO'}
AUTHOR_TAGS = re.compile(r'</?(?:strong|sup)>')
AUTHOR_MARKS = re.compile(r'[†*]+$')


def _text(item, key):
    value = item.get(key)
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValueError(f'{key} must be text')
    return value.strip()


def _integer(item, key):
    value = item.get(key)
    if value is None or value == '':
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f'{key} must be a positive integer')
    if value <= 0 or value != int(value):
        raise ValueError(f'{key} must be a positive integer')
    return int(value)


def _plain(text):
    return unescape(re.sub(r'<[^>]*>', '', text))


def _identity(text):
    text = _plain(text)
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def _unique(records, matches, label):
    candidates = [record for record in records if matches(record)]
    if len(candidates) > 1:
        raise ValueError(f'Ambiguous {label}')
    return candidates[0] if candidates else None


def _doi(row):
    value = _text(row, 'DOI Link')
    doi = normalize_doi(value)
    if value and not doi:
        raise ValueError(f'Invalid DOI Link: {value!r}')
    return doi


def _paper_match(records, row, *, private):
    number, doi = _integer(row, 'Number'), _doi(row)
    previous = row.get('_previous') or {}
    previous_number, previous_doi = _integer(previous, 'Number'), _doi(previous)
    title_keys = {_identity(_text(source, 'Name')) for source in (row, previous)} - {''}
    doi_keys = {doi, previous_doi} - {''}
    by_doi = _unique(records, lambda p: normalize_doi(p.get('link')) in doi_keys, 'publication DOI')
    by_number = _unique(records, lambda p: p.get('number') in {number, previous_number},
                        'publication display number')
    if by_doi and by_number and by_doi is not by_number:
        raise ValueError(f'Publication #{number}: DOI and display number identify different records')
    if by_number and not by_doi and _identity(by_number['title']) not in title_keys:
        if private:
            return None
        raise ValueError(f'Publication #{number}: number is already assigned to another title')
    existing = by_doi or by_number
    if existing is None:
        if not private and any(_identity(p['title']) in title_keys for p in records):
            raise ValueError(f'Publication #{number}: existing title has a different display number')
        return None
    if number is not None and number != existing['number']:
        raise ValueError(f'Publication #{existing["number"]}: automatic renumbering to #{number} is unsafe')
    current_doi = normalize_doi(existing.get('link'))
    if current_doi and doi and current_doi != doi:
        raise ValueError(f'Publication #{existing["number"]}: existing DOI cannot be replaced automatically')
    return existing


def _authors(text):
    authors = []
    for part in text.split(','):
        name = unescape(AUTHOR_TAGS.sub('', part)).strip().replace(r'\*', '*')
        marks = AUTHOR_MARKS.search(name)
        if marks:
            name = name[:marks.start()].rstrip()
        if not name or re.search(r'[<>*†]', name):
            raise ValueError('Authors must be comma-separated names with optional trailing † or *')
        authors.append((name, tuple(marks.group()) if marks else (), '<strong>' in part))
    if len({_identity(name) for name, _, _ in authors}) != len(authors):
        raise ValueError('Authors contains an ambiguous repeated name')
    return authors


def _render_authors(text, previous, members):
    current = _authors(text)
    old = {_identity(name): (name, marks, bold) for name, marks, bold in _authors(previous)} if previous else {}
    current_keys = {_identity(name) for name, _, _ in current}
    for key, (name, marks, _) in old.items():
        if marks and key not in current_keys:
            raise ValueError(f'Authors change removes a marked author: {name}; verify the author roles')
    result = []
    for name, marks, bold in current:
        key = _identity(name)
        _, old_marks, was_bold = old.get(key, ('', (), False))
        # A missing mark in plain text cannot revoke a verified author role.
        marks = tuple(dict.fromkeys((*old_marks, *marks)))
        if was_bold or bold or key in members:
            name = f'<strong>{name}</strong>'
        result.append(name + ''.join(f'<sup>{mark}</sup>' for mark in marks))
    return ', '.join(result)


def _check_image(root, value):
    relative = Path(value)
    if (relative.is_absolute() or '..' in relative.parts or '\\' in value or
            relative.parts[:2] != ('images', 'publications')):
        raise ValueError(f'Publication image must be a local images/publications path: {value!r}')
    image = (root / relative).resolve()
    if not image.is_relative_to(root.resolve()) or not image.is_file():
        raise ValueError(f'Publication image does not exist in repository: {value!r}')
    return relative.as_posix()


def _set_press(result, row, fields):
    press = dict(result.get('press') or {})
    original = dict(press)
    for source, target in [('Press Link', 'url'), ('Press', 'label'), ('Press EN', 'labelEn')]:
        if source in fields and _text(row, source):
            press[target] = _text(row, source)
    if press == original:
        return
    url = urlsplit(press.get('url', ''))
    if url.scheme not in ('http', 'https') or not url.hostname:
        raise ValueError('Press requires a valid HTTP(S) link')
    if not press.get('label') or not press.get('labelEn') or HANGUL.search(press['labelEn']):
        raise ValueError('Press requires Korean and English labels')
    result['press'] = press


def _paper_record(row, existing, status, members, root):
    result = dict(existing or {})
    fields = set(row.get('_changed_fields', ())) if existing is not None else set(row)
    if existing is not None and not fields:
        return result
    if existing is None:
        result['number'] = _integer(row, 'Number')
    if 'Name' in fields and _text(row, 'Name'):
        title = _text(row, 'Name')
        # A plain-text match should not strip the existing publisher markup.
        if not existing or title != _plain(result['title']):
            result['title'] = title
    if 'Year' in fields and (year := _integer(row, 'Year')) is not None:
        result['year'] = year
    if 'Authors' in fields and _text(row, 'Authors'):
        result['authors'] = _render_authors(_text(row, 'Authors'), result.get('authors', ''), members)
    if 'Journal' in fields and _text(row, 'Journal'):
        result['journal'] = _text(row, 'Journal')
    if 'DOI Link' in fields and (doi := _doi(row)) and not normalize_doi(result.get('link')):
        result['link'] = 'https://doi.org/' + quote(doi, safe='/:;()+._-')
    if 'Image Path' in fields and (image := _text(row, 'Image Path')):
        if image != result.get('image'):
            result['image'] = _check_image(root, image)
    if 'Impact Factor' in fields and row.get('Impact Factor') is not None:
        impact = row['Impact Factor']
        if not isinstance(impact, (int, float)) or isinstance(impact, bool) or not isfinite(impact) or impact < 0:
            raise ValueError('Impact Factor must be a nonnegative number')
        result['impactFactor'] = impact
    if 'Awards' in fields and _text(row, 'Awards'):
        awards = _text(row, 'Awards').splitlines()
        result['awards'] = list(dict.fromkeys([*result.get('awards', []), *(a.strip() for a in awards if a.strip())]))
    _set_press(result, row, fields)
    if not all(result.get(field) for field in ('number', 'year', 'title', 'authors', 'journal')):
        raise ValueError('Publications require Number, Year, Name, Authors and Journal')
    effective_status = status
    if existing and 'Status' not in fields:
        effective_status = _paper_status(existing) or status
    if effective_status == 'Published':
        if not normalize_doi(result.get('link')):
            raise ValueError('Published publications require a verified DOI Link')
        if _paper_status(result) in ('Accepted', 'In Press'):
            raise ValueError('Published status requires a journal citation that no longer says Accepted or In Press')
    elif existing is None or fields & {'Status', 'Journal'}:
        if _paper_status(result) not in ('Accepted', 'In Press'):
            result['journal'] += f', {effective_status} ({result["year"]})'
        elif _paper_status(result) != effective_status:
            raise ValueError('Journal citation and publication status disagree')
    result.setdefault('link', '')
    return result


def _paper_status(existing):
    journal = existing.get('journal', '')
    if re.search(r',\s*accepted\b', journal, re.I):
        return 'Accepted'
    if re.search(r',\s*in press\b', journal, re.I):
        return 'In Press'
    return 'Published' if normalize_doi(existing.get('link')) else ''


def _merge_papers(records, rows, members, root):
    highest = max((p['number'] for p in records), default=0)
    seen = set()
    for row in rows:
        label = f'Notion publication {row.get("_id", "")} (#{row.get("Number")})'
        try:
            status = _text(row, 'Status')
            existing = _paper_match(records, row, private=status == 'Submitted')
            if existing and not status:
                status = _paper_status(existing)
            if status not in PAPER_STATUS:
                raise ValueError(f'Unsupported or missing Status: {status!r}')
            previous_status = _text(row.get('_previous') or {}, 'Status')
            if existing and (status == 'Submitted' or ('Status' in row.get('_changed_fields', ()) and
                    PAPER_STATUS[status] < max(PAPER_STATUS.get(previous_status, 0),
                                               PAPER_STATUS.get(_paper_status(existing), 0)))):
                raise ValueError(f'Existing publication cannot regress to {status!r} automatically')
            if status == 'Submitted':
                continue
            result = _paper_record(row, existing, status, members, root)
            number = result['number']
            if number in seen:
                raise ValueError(f'Multiple Notion rows identify publication #{number}')
            seen.add(number)
            if existing is not None:
                records[records.index(existing)] = result
            elif number <= highest:
                raise ValueError(f'New publication #{number} must follow existing numbers')
            else:
                position = next((i for i, p in enumerate(records) if p['number'] < number), len(records))
                records.insert(position, result)
        except ValueError as error:
            raise ValueError(f'{label}: {error}') from error


def _patent_key(country, number):
    return country.upper(), re.sub(r'[\s,]+', '', number).upper()


def _names(text):
    return [name.strip() for name in text.split(',') if name.strip()]


def _verified_names(team, patents):
    names = defaultdict(set)
    for person in [team.get('pi', {}), *team.get('members', []), *team.get('alumni', [])]:
        if person.get('nameKr') and person.get('nameEn'):
            names[_identity(person['nameKr'])].add(person['nameEn'])
    for patent in patents:
        ko, en = _names(patent.get('inventors', '')), _names(patent.get('inventorsEn', ''))
        if len(ko) == len(en):
            for name, english in zip(ko, en):
                names[_identity(name)].add(english)
    return names


def _english_inventors(inventors, explicit, existing, verified_names):
    names = _names(inventors)
    if explicit:
        if HANGUL.search(explicit) or len(_names(explicit)) != len(names):
            raise ValueError('Inventors EN must give one English name per inventor, in the same order')
        return explicit
    if existing and _identity(inventors) == _identity(existing['inventors']):
        return existing['inventorsEn']
    translated = []
    for name in names:
        if not HANGUL.search(name) and re.search('[A-Za-z]', name):
            translated.append(name)
            continue
        spellings = verified_names.get(_identity(name), set())
        if len(spellings) != 1:
            raise ValueError(f'English inventor spelling requires confirmation: {name!r}')
        translated.append(next(iter(spellings)))
    return ', '.join(translated)


def _patent_match(records, row):
    key = _patent_key(_text(row, 'Country'), _text(row, 'Patent Number'))
    previous = row.get('_previous') or {}
    old_key = _patent_key(_text(previous, 'Country'), _text(previous, 'Patent Number'))
    keys = {key, old_key} - {('', '')}
    existing = _unique(records, lambda p: _patent_key(p['country'], p['number']) in keys, 'patent country/number')
    if existing is not None and all(key) and _patent_key(existing['country'], existing['number']) != key:
        raise ValueError('Existing patent country/number changes require verification')
    return existing


def _patent_record(row, existing, status, verified_names):
    result = dict(existing or {})
    fields = set(row.get('_changed_fields', ())) if existing is not None else set(row)
    if existing is not None and not fields:
        return result
    if existing is None:
        result.update(number=_text(row, 'Patent Number'), country=_text(row, 'Country'), status=status)
    if 'Year' in fields and (year := _integer(row, 'Year')) is not None:
        result['year'] = year
    if 'Name' in fields and (title := _text(row, 'Name')):
        if (existing and _identity(title) != _identity(existing['title']) and
                ('Title (EN)' not in fields or not _text(row, 'Title (EN)'))):
            raise ValueError('A substantive patent name change requires a corresponding Title (EN) update')
        result['title'] = title
    if 'Title (EN)' in fields and (english := _text(row, 'Title (EN)')):
        result['titleEn'] = english
    if not result.get('titleEn') and re.search('[A-Za-z]', result.get('title', '')) and not HANGUL.search(result['title']):
        result['titleEn'] = result['title']
    if 'Inventors' in fields and (inventors := _text(row, 'Inventors')):
        result['inventors'] = inventors
    if result.get('inventors') and (existing is None or fields & {'Inventors', 'Inventors EN'}):
        explicit = _text(row, 'Inventors EN') if 'Inventors EN' in fields else ''
        result['inventorsEn'] = _english_inventors(result['inventors'], explicit, existing, verified_names)
    if 'Status' in fields and status:
        result['status'] = status
    if existing is None or result['status'] != existing['status'] or 'Status EN' in fields:
        allowed = STATUS_EN[result['status']]
        explicit = _text(row, 'Status EN') if 'Status EN' in fields else ''
        if explicit:
            if explicit not in allowed:
                raise ValueError(f'Status EN does not match {result["status"]}')
            result['statusEn'] = explicit
        elif len(allowed) == 1:
            result['statusEn'] = next(iter(allowed))
        elif result.get('statusEn') not in allowed:
            raise ValueError(f'Status EN requires confirmation for {result["status"]}')
    required = ('number', 'country', 'year', 'title', 'titleEn', 'inventors', 'inventorsEn', 'statusEn')
    if not all(result.get(field) for field in required):
        raise ValueError('Patents require a country, number, year, and titles, inventors and status in both languages')
    if result['country'] not in COUNTRIES:
        raise ValueError(f'Unsupported patent country: {result["country"]!r}')
    if HANGUL.search(result['titleEn']) or HANGUL.search(result['inventorsEn']):
        raise ValueError('Patent English title and inventors must be supplied in English')
    return result


def _merge_patents(records, rows, verified_names):
    seen = set()
    for row in rows:
        label = f'Notion patent {row.get("_id", "")} ({row.get("Patent Number")})'
        try:
            existing = _patent_match(records, row)
            status = _text(row, 'Status') or (existing['status'] if existing else '')
            if status not in STATUS_EN:
                raise ValueError(f'Unsupported or missing Status: {status!r}')
            if status not in PATENT_STATUS:
                if existing:
                    raise ValueError(f'Existing patent cannot become nonpublic ({status}) automatically')
                continue
            if existing and 'Status' in row.get('_changed_fields', ()):
                previous = _text(row.get('_previous') or {}, 'Status')
                if PATENT_STATUS[status] < max(PATENT_STATUS.get(existing['status'], 0), PATENT_STATUS.get(previous, 0)):
                    raise ValueError(f'Existing patent cannot regress to {status!r} automatically')
            result = _patent_record(row, existing, status, verified_names)
            key = _patent_key(result['country'], result['number'])
            if key in seen:
                raise ValueError(f'Multiple Notion rows identify patent {key}')
            seen.add(key)
            if existing is not None:
                records[records.index(existing)] = result
            else:
                if any(p['country'] == result['country'] and _identity(p['title']) == _identity(result['title']) for p in records):
                    raise ValueError('Existing patent with this country/title has a different number')
                position = next((i for i, p in enumerate(records) if p['year'] <= result['year']), len(records))
                records.insert(position, result)
        except ValueError as error:
            raise ValueError(f'{label}: {error}') from error


def merge_bibliography(existing: dict, publications: list[dict], patents: list[dict], *, root: Path) -> dict:
    """Return a new data object; any unsafe change aborts the entire merge."""
    result = deepcopy(existing)
    if not publications and not patents:
        return result
    team = json.loads((root / 'data/team.json').read_text(encoding='utf-8'))
    names = _verified_names(team, result['patents'])
    members = {_identity(person['nameEn']) for person in
               [team.get('pi', {}), *team.get('members', []), *team.get('alumni', [])] if person.get('nameEn')}
    _merge_papers(result['publications'], publications, members, root)
    _merge_patents(result['patents'], patents, names)
    return result
