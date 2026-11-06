"""Merge approved Notion Team and News deltas into the public site data.

Existing rows use a three-way comparison with the previous Notion snapshot.
Missing values do not clear the site. Unsupported transitions raise ValueError
so the caller can hold the release for review. No source IDs enter public JSON.
"""

from copy import deepcopy
from datetime import date
from pathlib import Path
import re
import unicodedata


TEAM_ROLES = {
    'Research Professor': ('연구교수', 'Research Professor', 'researchprof'),
    'Post-Doc': ('박사후연구원', 'Postdoctoral Researcher', 'postdoc'),
    'Ph.D. Student': ('박사과정', 'Ph.D. Candidate', 'phd'),
    'M.S. Student': ('석사과정', 'M.S. Candidate', 'phd'),
    'M.S./Ph.D. Student': ('통합과정', 'Joint M.S. & Ph.D. Candidate', 'phd'),
    'Undergraduate': ('학부인턴', 'Undergraduate Intern', 'intern'),
}
NEWS_CATEGORIES = {'Publication', 'Award', 'Grant', 'Event', 'Media', 'General'}
MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
HANGUL = re.compile(r'[가-힣ᄀ-ᇿㄱ-ㆎ]')
PRIVATE_MARKER = re.compile(
    r'\b(?:mail\.google\.com|notion\.so|app\.notion\.com|notion-file-block)\b'
    r'|(?:^|\n)\s*(?:관리\s*근거|내부\s*메모|출처\s*[:：]|웹사이트\s*slug\s*[:：])',
    re.IGNORECASE,
)


def _error(row, reason):
    raise ValueError(f'Notion row {row.get("_id", "unknown")}: {reason}')


def _text(row, key):
    value = row.get(key)
    if value is None:
        return ''
    if not isinstance(value, str):
        _error(row, f'{key} must be plain text')
    if any(ord(char) < 32 and char not in '\n\r\t' for char in value):
        _error(row, f'{key} contains a control character')
    return value.strip()


def _norm(value):
    return ' '.join(unicodedata.normalize('NFC', value or '').casefold().split())


def _english(row, key, value):
    if HANGUL.search(value):
        _error(row, f'{key} would display Korean on the English page')
    return value


def _changed(row, key):
    if '_changed_fields' in row:
        return key in row['_changed_fields']
    return row.get(key) != (row.get('_previous') or {}).get(key)


def _update(row, record, key, value, previous):
    """Leave local editorial values intact when Notion did not edit the field."""
    if not value or value == record.get(key):
        return
    if not row.get('_site_unchanged') and record.get(key) and (not previous or record[key] != previous):
        _error(row, f'{key} conflicts with the published value')
    record[key] = value


def _asset(row, root, value, prefix):
    # The Notion connector may Markdown-escape underscores in a path.
    value = value.replace(r'\_', '_')
    path = Path(value)
    directory = root.resolve() / prefix
    resolved = (root / path).resolve()
    if (path.is_absolute() or '..' in path.parts or any(c in value for c in '\\?#%') or not value.startswith(prefix + '/')
            or not resolved.is_relative_to(directory) or resolved.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}
            or not resolved.is_file()):
        _error(row, f'expected an existing local image under {prefix}/')
    return path.as_posix()


def _slug(value):
    ascii_value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_value.casefold()).strip('-')


def _active(row):
    value = row.get('Active')
    if value is True or value == '__YES__':
        return True
    if value is False or value == '__NO__':
        return False
    if value is None or value == '':
        return None
    _error(row, 'Active must be a checkbox')


def _team_match(row, entries):
    matches = set()
    for version in (row.get('_previous') or {}, row):
        for key, target in [('Name', 'nameKr'), ('Name EN', 'nameEn'), ('Email', 'email')]:
            value = _norm(_text(version, key))
            if value:
                matches.update(i for i, (_, item) in enumerate(entries) if _norm(item.get(target)) == value)
    if len(matches) > 1:
        _error(row, 'names or email point to different Team records')
    return next(iter(matches), None)


def _public_email(row, value):
    if not re.fullmatch(r'[a-z0-9._%+\-]+@yonsei\.ac\.kr', value, re.IGNORECASE):
        _error(row, 'new or changed public email needs a valid yonsei.ac.kr address')
    return value


def _public_name(row, key, value):
    # The Team renderer puts these names into innerHTML on language switches.
    if any(char in value for char in '<>\r\n'):
        _error(row, f'{key} must be a plain, single-line name')
    if key == 'Name EN':
        _english(row, key, value)
    return value


def merge_team(existing: dict, rows: list[dict], *, root: Path) -> dict:
    result = deepcopy(existing)
    members = result['members']
    entries = [('pi', result['pi'])] + [('member', m) for m in members] + [('alumni', a) for a in result['alumni']]
    categories = {cat['id'] for cat in result['categories']}
    claimed = set()
    for row in rows:
        prior = row.get('_previous') or {}
        idx = _team_match(row, entries)
        active = _active(row)
        role = _text(row, 'Role')
        mapped = TEAM_ROLES.get(role)
        photo = _text(row, 'Photo')

        if idx is None:
            if '_previous' in row:
                _error(row, 'previous Team row has no unambiguous public record')
            name_kr, name_en = _text(row, 'Name'), _text(row, 'Name EN')
            research = _text(row, 'Research Topic')
            if active is not True or not mapped or not all((name_kr, name_en, research)):
                _error(row, 'a new member needs Active, a supported Role, both names and a research topic')
            role_kr, role_en, category = mapped
            if category not in categories:
                _error(row, 'Team category is missing from the site')
            member_id = _slug(name_en)
            if photo:
                image = Path(_asset(row, root, photo, 'images/team'))
                if image != Path('images/team') / f'{image.stem}.jpg':
                    _error(row, 'Team renderer requires images/team/<id>.jpg')
                member_id = image.stem
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', member_id) or any(
                    m.get('id') == member_id for _, m in entries):
                _error(row, 'new Team ID is invalid or already in use')
            email = _text(row, 'Email')
            member = {'id': member_id, 'initials': ''.join(word[0].upper() for word in name_en.split()),
                      'nameKr': _public_name(row, 'Name', name_kr), 'nameEn': _public_name(row, 'Name EN', name_en),
                      'roleKr': role_kr, 'roleEn': role_en, 'research': _english(row, 'Research Topic', research),
                      'email': _public_email(row, email) if email else '', 'category': category, 'education': []}
            members.append(member)
            claimed.add(len(entries))
            entries.append(('member', member))
            continue

        if idx in claimed:
            _error(row, 'multiple Notion rows target the same Team record')
        claimed.add(idx)
        group, member = entries[idx]
        if group in {'pi', 'alumni'}:
            public_fields = ('Name', 'Name EN', 'Role', 'Active', 'Email', 'Photo', 'Research Topic')
            if any(_changed(row, key) and row.get(key) not in (None, '') for key in public_fields):
                _error(row, 'PI and alumni changes require review')
            continue
        if active is False and _changed(row, 'Active'):
            _error(row, 'marking a published member inactive requires review')
        if _changed(row, 'Order') and row.get('Order') is not None:
            _error(row, 'Team reordering needs a full roster review')
        if role and _changed(row, 'Role'):
            if not mapped or mapped[2] not in categories:
                _error(row, 'member Role transition requires review')
            current_role = tuple(member.get(k) for k in ('roleKr', 'roleEn', 'category'))
            if current_role != mapped and TEAM_ROLES.get(_text(prior, 'Role')) != current_role:
                _error(row, 'Role conflicts with the published role or a site exception')
            member['roleKr'], member['roleEn'], member['category'] = mapped
        if photo and _changed(row, 'Photo'):
            path = _asset(row, root, photo, 'images/team')
            if path != f'images/team/{member["id"]}.jpg':
                _error(row, 'changing the portrait path requires a site asset update')
        for source, target in [('Name', 'nameKr'), ('Name EN', 'nameEn'),
                               ('Email', 'email'), ('Research Topic', 'research')]:
            if not _changed(row, source):
                continue
            value = _text(row, source)
            if value and value != member.get(target):
                if source in ('Name', 'Name EN'):
                    _public_name(row, source, value)
                if source == 'Research Topic':
                    _english(row, source, value)
                if source == 'Email':
                    _public_email(row, value)
                _update(row, member, target, value, _text(prior, source))
    return result


def _news_date(row):
    dates = {_text(row, key) for key in ('Date', 'date:Date:start')} - {''}
    if len(dates) > 1:
        _error(row, 'conflicting Date values')
    value = next(iter(dates), '')
    if value:
        try:
            if date.fromisoformat(value).isoformat() == value:
                return value
        except ValueError:
            pass
        _error(row, 'Date must be YYYY-MM-DD')
    return ''


def _news_match(row, items):
    matches = set()
    for version in (row.get('_previous') or {}, row):
        kr, en, when = _norm(_text(version, 'Name')), _norm(_text(version, 'Name EN')), _news_date(version)
        if not (kr or en):
            continue
        titles = {i for i, item in enumerate(items) if (kr and _norm(item['title']) == kr)
                  or (en and _norm(item.get('titleEn')) == en)}
        same_date = {i for i in titles if items[i]['date'] == when}
        matches.update(same_date or titles)
    if len(matches) > 1:
        _error(row, 'titles and dates point to different News records')
    return next(iter(matches), None)


def _summary_pair(row):
    public_kr = _text(row, 'Public Summary KR')
    public_en = _text(row, 'Summary EN')
    if public_kr or public_en:
        return public_kr, public_en
    sections = {'kr': [], 'en': []}
    current = None
    for line in _text(row, '_text').splitlines():
        heading = re.sub(r'^#{1,6}\s+', '', line.strip())
        label = heading.strip('[]').rstrip(':：').casefold()
        if label in {'한국어', '국문', 'korean', 'summary kr'}:
            current = 'kr'
        elif label in {'영어', '영문', 'english', 'summary en'}:
            current = 'en'
        elif (line.lstrip().startswith('#') or re.match(r'^(관리\s*근거|출처|내부\s*메모|웹사이트\s*slug|notes|sources)\b',
                                                        label, re.IGNORECASE)):
            current = None
        elif current:
            sections[current].append(line)
    return '\n'.join(sections['kr']).strip(), '\n'.join(sections['en']).strip()


def _public_news_text(row, key, value):
    if PRIVATE_MARKER.search(value):
        _error(row, f'{key} contains an internal source or management note')
    if key.endswith('En'):
        _english(row, key, value)
    return value


def _month(value):
    parsed = date.fromisoformat(value)
    return f'{MONTHS[parsed.month - 1]} {parsed.year}'


def merge_news(existing: dict, rows: list[dict], *, root: Path) -> dict:
    result = deepcopy(existing)
    items = result['news']
    claimed = set()
    sort_needed = False
    for row in rows:
        prior = row.get('_previous') or {}
        idx = _news_match(row, items)
        when = _news_date(row)
        category = _text(row, 'Category')
        image = _text(row, 'Image')
        summary_fields = ('_text', 'Content', 'Public Summary KR', 'Summary EN')
        summary_changed = any(_changed(row, key) for key in summary_fields)
        if idx is None or summary_changed:
            summary_kr, summary_en = _summary_pair(row)
            if bool(summary_kr) != bool(summary_en):
                _error(row, 'public news summary requires both Korean and English')
            if not summary_kr and _text(row, 'Content') and (idx is None or _changed(row, 'Content')):
                _error(row, 'unlabelled Content may contain internal notes; supply public summaries in both languages')
            _public_news_text(row, 'summary', summary_kr)
            _public_news_text(row, 'summaryEn', summary_en)

        if idx is None:
            if '_previous' in row:
                _error(row, 'previous News row has no unambiguous public record')
            kr, en = _text(row, 'Name'), _text(row, 'Name EN')
            if not all((kr, en, when, image)) or category not in NEWS_CATEGORIES:
                _error(row, 'a new news item needs both titles, Date, a supported Category and a local Image')
            slug_title = _slug(en)[:72].rstrip('-')
            slug = f'{when}-{slug_title}'
            if not slug_title or any(item['slug'] == slug for item in items):
                _error(row, 'new News slug is invalid or already in use')
            claimed.add(len(items))
            items.append({'title': _public_news_text(row, 'title', kr), 'titleEn': _public_news_text(row, 'titleEn', en),
                          'slug': slug, 'date': when, 'month': _month(when), 'categories': [category],
                          'summary': summary_kr, 'summaryEn': summary_en,
                          'thumbnail': _asset(row, root, image, 'images'), 'contentImage': None})
            sort_needed = True
            continue

        if idx in claimed:
            _error(row, 'multiple Notion rows target the same News record')
        claimed.add(idx)
        item = items[idx]
        kr = _text(row, 'Name')
        if (_changed(row, 'Name') and kr and _norm(kr) != _norm(item['title']) and
                (not _changed(row, 'Name EN') or not _text(row, 'Name EN'))):
            _error(row, 'a changed Korean news title needs the corresponding English title')
        for source, target in [('Name', 'title'), ('Name EN', 'titleEn')]:
            if _changed(row, source):
                value = _public_news_text(row, target, _text(row, source))
                _update(row, item, target, value, _text(prior, source))
        if when and any(_changed(row, key) for key in ('Date', 'date:Date:start')) and when != item['date']:
            _update(row, item, 'date', when, _news_date(prior))
            item['month'] = _month(when)
            sort_needed = True
        if category and _changed(row, 'Category'):
            if category not in NEWS_CATEGORIES:
                _error(row, 'unsupported news Category')
            previous_category = _text(prior, 'Category')
            categories = item.get('categories', [])
            if categories and categories[0] != category and categories[0] != previous_category:
                _error(row, 'Category conflicts with the published categories')
            item['categories'] = [category] + [c for c in categories[1:] if c != category]
        if image and _changed(row, 'Image'):
            old_image = _text(prior, 'Image').replace(r'\_', '_')
            _update(row, item, 'thumbnail', _asset(row, root, image, 'images'), old_image)
        if summary_changed:
            old_kr, old_en = _summary_pair(prior)
            for key, value, old in [('summary', summary_kr, old_kr), ('summaryEn', summary_en, old_en)]:
                if value != old:
                    _update(row, item, key, value, old)
    if sort_needed:
        items.sort(key=lambda item: item['date'], reverse=True)
    return result
