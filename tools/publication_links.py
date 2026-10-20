"""Join publication lists to bilingual research briefs by DOI, never by position."""
import re
from urllib.parse import unquote, urlsplit


def normalize_doi(value):
    """Accept a bare DOI or doi.org URL; leave non-DOI links unmatched."""
    value = (value or '').strip()
    if value.lower().startswith(('http://', 'https://')):
        parsed = urlsplit(value)
        if parsed.netloc.lower() not in ('doi.org', 'dx.doi.org'):
            return ''
        value = unquote(parsed.path.lstrip('/'))
    elif value.lower().startswith('doi:'):
        value = value[4:].strip()
    value = value.lower()
    return value if re.fullmatch(r'10\.\d{4,9}/\S+', value) else ''


def brief_slugs_by_number(publications, catalogue):
    """Return current display number -> slug after an unambiguous DOI match.

    Catalogue numbers may lag behind a reordered homepage. They are labels, not
    identity keys. A missing DOI or an uncatalogued DOI has no brief link.
    """
    by_doi, by_slug = {}, {}
    for entry in catalogue:
        doi, slug = normalize_doi(entry.get('doi')), entry.get('slug')
        if not doi or not slug:
            continue
        language = entry.get('language')
        if language not in ('en', 'ko'):
            raise ValueError(f'Catalogue DOI {doi}: expected language en or ko, got {language!r}')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            raise ValueError(f'Catalogue DOI {doi}: invalid brief slug {slug!r}')
        previous_doi = by_slug.setdefault(slug, doi)
        if previous_doi != doi:
            raise ValueError(f'Catalogue slug {slug!r} is shared by DOI {previous_doi} and {doi}')
        record = by_doi.setdefault(doi, {'slug': slug, 'languages': set()})
        if record['slug'] != slug:
            raise ValueError(f'Catalogue DOI {doi}: conflicting bilingual slugs {record["slug"]!r} and {slug!r}')
        if language in record['languages']:
            raise ValueError(f'Catalogue DOI {doi}: duplicate {language} entry')
        record['languages'].add(language)
    for doi, record in by_doi.items():
        missing = {'en', 'ko'} - record['languages']
        if missing:
            raise ValueError(f'Catalogue DOI {doi}: missing brief language {", ".join(sorted(missing))}')

    result, seen_dois, seen_numbers = {}, {}, set()
    for publication in publications:
        number = int(publication['number'])
        if number in seen_numbers:
            raise ValueError(f'Homepage publications: duplicate display number {number}')
        seen_numbers.add(number)
        doi = normalize_doi(publication.get('link'))
        if not doi:
            continue
        if doi in seen_dois:
            raise ValueError(f'Homepage DOI {doi}: duplicate entries #{seen_dois[doi]} and #{number}')
        seen_dois[doi] = number
        if doi in by_doi:
            result[number] = by_doi[doi]['slug']
    return result
