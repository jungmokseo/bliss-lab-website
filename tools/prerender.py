#!/usr/bin/env python3
"""Rebuild the static (prerendered) parts of index.html from data/*.json.

Static HTML makes publications readable without requiring JavaScript.
Search crawlers and model-training crawlers serve different purposes; rendering
content here does not change their permissions in robots.txt.

  python3 tools/prerender.py          # rewrite index.html
  python3 tools/prerender.py --check  # exit 1 if index.html is out of date

Run it after every change to data/publications.json, data/team.json or
data/news.json, and whenever a research-library brief is added to the
catalogue resources/data/publications.json (the "slug" there names the brief
page resources/{ko,en}/papers/<slug>.html; see tools/migrate_brief_slugs.py).

Publications: Python port of loadPublications() in index.html. Keep the two
in sync; the generated block must equal what the JS template would produce,
except that only this script can add each thumbnail's intrinsic width/height
(read from the image file). They reserve the image's space before it loads, so
the page does not change height under an in-page jump.
Patents: Korean-default bilingual HTML, replaced by the JS renderer on load;
the list remains visible without JavaScript. Team members and news use plain
<noscript> lists (the JS renderers fill the same containers on load).
"""
import json, os, re, struct, sys
from publication_links import brief_slugs_by_number

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
GROUPING_YEAR = 2026  # matches data-grouping-year on #publicationsList


def esc(s):
    if s is None:
        return ''
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&#39;'))


def san(s):
    if not s:
        return ''
    return re.sub(r'&lt;(/?(?:strong|sup|sub))&gt;', r'<\1>', esc(s))


def num_str(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def image_size(path):
    """Displayed (width, height) of a PNG, GIF or JPEG file, or None if unknown."""
    try:
        with open(path, 'rb') as f:
            head = f.read(26)
            if head[:8] == b'\x89PNG\r\n\x1a\n' and head[12:16] == b'IHDR':
                return struct.unpack('>II', head[16:24])
            if head[:6] in (b'GIF87a', b'GIF89a'):
                return struct.unpack('<HH', head[6:10])
            if head[:2] != b'\xff\xd8':
                return None
            f.seek(2)
            orientation = 1
            while True:
                byte = f.read(1)
                while byte and byte != b'\xff':
                    byte = f.read(1)
                while byte == b'\xff':
                    byte = f.read(1)
                if not byte:
                    return None
                marker = byte[0]
                if marker in (0xd8, 0x01) or 0xd0 <= marker <= 0xd7:
                    continue
                if marker in (0xd9, 0xda):
                    return None
                length = struct.unpack('>H', f.read(2))[0]
                data = f.read(length - 2)
                if marker == 0xe1 and data[:6] == b'Exif\x00\x00':
                    orientation = exif_orientation(data[6:]) or orientation
                # SOF0-SOF15 carry the frame size; C4, C8 and CC are other tables
                if 0xc0 <= marker <= 0xcf and marker not in (0xc4, 0xc8, 0xcc):
                    height, width = struct.unpack('>HH', data[1:5])
                    # Browsers apply the EXIF orientation; 5-8 turn the image by 90 degrees.
                    return (height, width) if orientation in (5, 6, 7, 8) else (width, height)
    except (OSError, struct.error, IndexError):
        return None


def exif_orientation(tiff):
    """EXIF Orientation (tag 0x0112) from a TIFF block, or None."""
    try:
        order = {b'II': '<', b'MM': '>'}[tiff[:2]]
        offset = struct.unpack(order + 'I', tiff[4:8])[0]
        count = struct.unpack(order + 'H', tiff[offset:offset + 2])[0]
        for i in range(count):
            entry = tiff[offset + 2 + 12 * i:offset + 14 + 12 * i]
            if struct.unpack(order + 'H', entry[:2])[0] == 0x0112:
                return struct.unpack(order + 'H', entry[8:10])[0]
    except (KeyError, struct.error, IndexError):
        pass
    return None


def image_dimensions(src):
    """' width="W" height="H"' for a site-relative image path, or '' if unreadable."""
    if not src or re.match(r'^(?:[a-z][a-z0-9+.-]*:|//)', src, re.I):
        return ''
    size = image_size(os.path.join(ROOT, src.split('?')[0].split('#')[0].lstrip('/')))
    return f' width="{size[0]}" height="{size[1]}"' if size and all(size) else ''


def brief_slugs(publications):
    """Current display number -> research-library slug, matched by DOI."""
    cat = json.load(open(os.path.join(ROOT, 'resources', 'data', 'publications.json'), encoding='utf-8'))
    return brief_slugs_by_number(publications, cat)


def brief_html(pub, slugs):
    n = pub.get('number')
    slug = slugs.get(int(n)) if n is not None else None
    if not slug:
        return ''
    kr, en = f'/resources/ko/papers/{slug}.html', f'/resources/en/papers/{slug}.html'
    return (f'<a class="pub-doi pub-brief" href="{kr}" data-href-kr="{kr}" data-href-en="{en}">'
            f'<i class="fas fa-book-open"></i> <span data-kr="연구 해설" data-en="Research brief">연구 해설</span></a>')


def render_publications(data, slugs):
    recent = GROUPING_YEAR - 2
    range_key = f'2019–{recent - 1}'
    grouped, order = {}, []
    for pub in data['publications']:
        y = pub['year']
        key = str(y) if y >= recent else (range_key if y >= 2019 else '~2018')
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(pub)
    bucket = {range_key: 2019, '~2018': 0}
    years = sorted(order, key=lambda k: -(bucket[k] if k in bucket else int(k)))
    out = ''
    for year in years:
        is_open = 'open' if year not in bucket else ''
        pubs = grouped[year]
        items = []
        for pub in pubs:
            has_img = bool(pub.get('image'))
            ifb = f'<span class="pub-if">IF {esc(num_str(pub["impactFactor"]))}</span>' if pub.get('impactFactor') is not None else ''
            numl = f'<span class="pub-number">{esc(num_str(pub["number"]))}.</span>' if pub.get('number') is not None else ''
            img = (f'<div class="pub-img"><img src="{esc(pub["image"])}" alt=""{image_dimensions(pub["image"])} '
                   f'loading="lazy" decoding="async" '
                   f'onerror="this.parentElement.style.display=\'none\'"></div>') if has_img else ''
            chips = ''.join(f'<span class="pub-award"><i class="fas fa-trophy"></i> {esc(a)}</span>' for a in (pub.get('awards') or []))
            press = ''
            pr = pub.get('press')
            if pr and pr.get('url'):
                pkr = '언론 보도' + (' · ' + pr['label'] if pr.get('label') else '')
                pen = 'Press' + (' · ' + pr['labelEn'] if pr.get('labelEn') else '')
                plain = re.sub(r'<[^>]+>', '', pub['title'])
                press = (f'<a class="pub-press" href="{esc(pr["url"])}" target="_blank" rel="noopener noreferrer" '
                         f'aria-label="Press coverage of {esc(plain)}"><i class="far fa-newspaper"></i> '
                         f'<span data-kr="{esc(esc(pkr))}" data-en="{esc(esc(pen))}">{esc(pkr)}</span></a>')
            awards_html = f'<div class="pub-awards">{chips}{press}</div>' if (chips or press) else ''
            link = pub.get('link')
            doi = (f'<a class="pub-doi" href="{esc(link)}" target="_blank" rel="noopener noreferrer" title="Open at publisher" '
                   f'aria-label="Open {esc(pub["title"])} at publisher"><i class="fas fa-external-link-alt"></i> DOI</a>') if link else ''
            js = pub.get('journal') or ''
            ci = js.find(',')
            jn = js[:ci].strip() if ci > 0 else js
            jr = js[ci:] if ci > 0 else ''
            jh = (f'<span class="pub-journal-name">{esc(jn)}</span><span style="color:var(--text-muted);font-weight:400;">{esc(jr)}</span>'
                  if jn else esc(js))
            ts = san(pub['title'])
            th = f'<a href="{esc(link)}" target="_blank" rel="noopener noreferrer">{ts}</a>' if link else ts
            label = (f'<span class="pub-display-label">[{esc(pub["displayLabel"])}]</span> '
                     if pub.get('displayLabel') else '')
            items.append(f'''
        <div class="pub-item{' pub-item-with-img' if has_img else ''}">
          {img}
          <div class="pub-content">
            <div class="pub-title">{numl}{label}{th}</div>
            <div class="pub-authors">{san(pub['authors'])}</div>
            <div class="pub-journal">{jh}{ifb}{doi}{brief_html(pub, slugs)}</div>
            {awards_html}
          </div>
        </div>''')
        n = len(pubs)
        out += f'''
        <div class="pub-year-group {is_open} reveal">
          <div class="pub-year-header" onclick="toggleYear(this)" aria-expanded="{'true' if is_open else 'false'}">
            <div class="year-label">{esc(year)} <span class="year-count">{n} paper{'s' if n != 1 else ''}</span></div>
            <i class="fas fa-chevron-down chevron"></i>
          </div>
          <div class="pub-year-items">
            {''.join(items)}
          </div>
        </div>
      '''
    return '\n'.join(line.rstrip() for line in out.split('\n'))


def render_patents(data):
    """Keep patent records readable when JavaScript or the JSON fetch fails."""
    patents = data.get('patents', [])
    if not patents:
        return ''

    def bi(kr, en, cls=''):
        return (f'<span class="{cls}" data-kr="{esc(esc(kr))}" '
                f'data-en="{esc(esc(en))}">{esc(kr)}</span>')

    items = []
    for p in patents:
        tkr, ten = p.get('title', ''), p.get('titleEn') or p.get('title', '')
        ikr, ien = p.get('inventors', ''), p.get('inventorsEn') or p.get('inventors', '')
        status = ''
        if p.get('status'):
            skr, sen = f'[{p["status"]}]', f'[{p.get("statusEn") or p["status"]}]'
            status = (f' <span style="color:var(--accent);font-weight:600;" '
                      f'data-kr="{esc(esc(skr))}" data-en="{esc(esc(sen))}">{esc(skr)}</span>')
        items.append(f'''<div class="patent-item">
          <div class="patent-title" data-kr="{esc(esc(tkr))}" data-en="{esc(esc(ten))}">{esc(tkr)}</div>
          <div class="patent-info">{bi(ikr, ien)} · {esc(p.get('number', ''))} · {esc(p.get('country', ''))}{status}</div>
        </div>''')
    count = len(patents)
    return f'''
        <noscript><style>#patentSection .patent-list {{ max-height: none; overflow: visible; }}</style></noscript>
        <div class="patent-toggle reveal" aria-expanded="false" onclick="togglePatents(this)">
          <span data-kr="Patents ({count})" data-en="Patents ({count})">Patents ({count})</span>
          <i class="fas fa-chevron-down chevron"></i>
        </div>
        <div class="patent-list">{''.join(items)}</div>
      '''


def render_team(team):
    cats = {c['id']: c for c in team.get('categories', [])}
    parts = ['<noscript><div class="team-static">']
    for cid, cat in cats.items():
        ms = [m for m in team.get('members', []) if m.get('category') == cid]
        if not ms:
            continue
        parts.append(f'<h4>{esc(cat.get("labelEn"))} ({esc(cat.get("labelKr"))})</h4><ul>')
        for m in ms:
            line = f'{esc(m.get("nameEn"))} ({esc(m.get("nameKr"))}) — {esc(m.get("roleEn"))}'
            if m.get('research'):
                line += f'; research: {esc(m["research"])}'
            parts.append(f'<li>{line}</li>')
        parts.append('</ul>')
    al = team.get('alumni', [])
    if al:
        parts.append('<h4>Alumni (졸업생)</h4><ul>')
        for a in al:
            line = f'{esc(a.get("nameEn"))} ({esc(a.get("nameKr"))})'
            if a.get('degree'):
                line += f', {esc(a["degree"])}'
            if a.get('current'):
                line += f' — {esc(a["current"])}'
            parts.append(f'<li>{line}</li>')
        parts.append('</ul>')
    parts.append('</div></noscript>')
    return ''.join(parts)


def render_news(news, limit=20):
    items = sorted(news.get('news', []), key=lambda n: n.get('date', ''), reverse=True)[:limit]
    parts = ['<noscript><ul class="news-static">']
    for n in items:
        title = n.get('titleEn') or n.get('title')
        summ = n.get('summaryEn') or n.get('summary') or ''
        photos = n.get('photos') or []
        photo_links = ' · '.join(f'<a href="{esc(photo["src"])}">{esc(photo["captionEn"])}</a>'
                                 for photo in photos)
        parts.append(f'<li><time datetime="{esc(n.get("date"))}">{esc(n.get("date"))}</time> — <strong>{esc(title)}</strong>'
                     + (f'. {esc(summ)}' if summ else '')
                     + (f' <a href="{esc(n["thumbnail"])}">Group photo</a> · {photo_links}' if photo_links else '')
                     + '</li>')
    parts.append('</ul></noscript>')
    return ''.join(parts)


def replace_between(html, begin, end, content):
    i = html.index(begin) + len(begin)
    j = html.index(end, i)
    return html[:i] + content + html[j:]


def build(html):
    pubs = json.load(open(os.path.join(ROOT, 'data', 'publications.json'), encoding='utf-8'))
    team = json.load(open(os.path.join(ROOT, 'data', 'team.json'), encoding='utf-8'))
    news = json.load(open(os.path.join(ROOT, 'data', 'news.json'), encoding='utf-8'))
    slugs = brief_slugs(pubs['publications'])
    count = len(pubs['publications'])

    begin, end = '<!-- BEGIN GENERATED PUBLICATIONS -->', '<!-- END GENERATED PUBLICATIONS -->'
    cur = html[html.index(begin) + len(begin):html.index(end)]
    lead = cur[:len(cur) - len(cur.lstrip())]
    trail = cur[len(cur.rstrip()):]
    html = replace_between(html, begin, end, lead + render_publications(pubs, slugs).strip() + trail)

    html = replace_between(html, '<!-- BEGIN GENERATED PATENTS -->', '<!-- END GENERATED PATENTS -->', render_patents(pubs))

    html = re.sub(r'data-publication-count="\d+"', f'data-publication-count="{count}"', html)
    # number -> slug map read by the JS fallback renderer (used only when the list is not prerendered)
    slug_json = json.dumps({str(k): v for k, v in sorted(slugs.items())}, separators=(',', ':'))
    html = re.sub(r'(<script type="application/json" id="briefSlugs">).*?(</script>)',
                  lambda m: m.group(1) + slug_json + m.group(2), html, count=1, flags=re.S)
    html = re.sub(r'(id="impactPubCount">)\d+\+', rf'\g<1>{count}+', html)
    html = re.sub(r'\b\d+\+ publications · ', f'{count}+ publications · ', html)

    html = replace_between(html, '<!-- BEGIN GENERATED TEAM -->', '<!-- END GENERATED TEAM -->', render_team(team))
    html = replace_between(html, '<!-- BEGIN GENERATED NEWS -->', '<!-- END GENERATED NEWS -->', render_news(news))
    return html


if __name__ == '__main__':
    html = open(INDEX, encoding='utf-8').read()
    new = build(html)
    if '--check' in sys.argv:
        print('up to date' if new == html else 'OUT OF DATE')
        sys.exit(0 if new == html else 1)
    if new != html:
        open(INDEX, 'w', encoding='utf-8').write(new)
    print('index.html prerendered')
