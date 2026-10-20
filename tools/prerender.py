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
in sync; the generated block must equal what the JS template would produce.
Team members and news: plain <noscript> lists (browsers with JS never show
them; the JS renderers fill the same containers on load).
"""
import json, os, re, sys
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
            img = (f'<div class="pub-img"><img src="{esc(pub["image"])}" alt="" loading="lazy" '
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
    return out


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
        parts.append(f'<li><time datetime="{esc(n.get("date"))}">{esc(n.get("date"))}</time> — <strong>{esc(title)}</strong>'
                     + (f'. {esc(summ)}' if summ else '') + '</li>')
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
