#!/usr/bin/env python3
"""Build /llms.txt, /llms-full.txt and the root /sitemap.xml from repo data.

  python3 tools/build_llms.py

Run after changing data/publications.json, data/team.json or the research
library catalogue (resources/data/publications.json).
"""
import json, os, re, html, datetime
from publication_links import brief_slugs_by_number

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://bliss.yonsei.ac.kr'
THEMES = {
    'tissue': 'Materials in contact with tissue',
    'routing': 'Stretchable conductors and interconnects',
    'integration': 'Device integration and packaging',
    'host': 'Biological responses and surface design',
}


def plain(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()


def main():
    pubs = json.load(open(os.path.join(ROOT, 'data', 'publications.json'), encoding='utf-8'))
    team = json.load(open(os.path.join(ROOT, 'data', 'team.json'), encoding='utf-8'))
    cat = json.load(open(os.path.join(ROOT, 'resources', 'data', 'publications.json'), encoding='utf-8'))
    pi = team['pi']
    plist = pubs['publications']
    n_pubs = len(plist)
    recent = [p for p in plist if p['year'] >= max(p['year'] for p in plist) - 1][:12]
    members = team.get('members', [])
    slugs = brief_slugs_by_number(plist, cat)  # DOI identifies the brief; numbers are labels.

    lines = [
        '# BLISS Lab, Yonsei University',
        '',
        f'> BLISS Lab (BioLogical Interfaces and Sensor Systems) is a research group in the School of Electrical and Electronic '
        f'Engineering at Yonsei University, Seoul, Korea, led by {pi["nameEn"]} ({pi["nameKr"]}), {pi["roleEn"]}. '
        'The lab develops soft bioelectronic materials, bio-interfaces, implantable sensors, stretchable circuits and IC packaging '
        'for devices that work reliably in contact with the body.',
        '',
        f'- Principal investigator: {pi["nameEn"]} ({pi["nameKr"]}), ORCID https://orcid.org/0000-0002-8898-044X, '
        'Google Scholar https://scholar.google.com/citations?user=kl7IdKgAAAAJ',
        f'- Publications listed on the site: {n_pubs} (numbered #1–#{max(p["number"] for p in plist)}, newest first)',
        f'- Current members listed: {len(members)}; alumni listed: {len(team.get("alumni", []))}',
        '',
        '## Main pages',
        f'- [Lab homepage]({SITE}/): research areas, highlights, publications, team, news',
        f'- [Research Library]({SITE}/resources/en/index.html): plain-language summaries of each publication, grouped into four research themes (Korean: {SITE}/resources/ko/index.html)',
        f'- [All publications with summaries]({SITE}/resources/en/publications.html)',
        f'- [How the summaries are written]({SITE}/resources/en/methods.html)',
        '',
        '## Research themes',
    ]
    for k, v in THEMES.items():
        lines.append(f'- [{v}]({SITE}/resources/en/themes/{k}.html)')
    lines += ['', '## Recent publications']
    for p in recent:
        link = p.get('link') or ''
        slug = slugs.get(p['number'])
        lines.append(f'- #{p["number"]} {plain(p["title"])} — {plain(p["journal"])}. '
                     + (f'DOI: {link.replace("https://doi.org/", "")}. ' if link else '')
                     + (f'Summary: {SITE}/resources/en/papers/{slug}.html' if slug else '').rstrip())
    lines += ['', '## Data',
              f'- [Publication catalogue (JSON)]({SITE}/resources/data/publications.json): number, title, authors, journal, year, DOI, slug, summary page URL (resources/{{en,ko}}/papers/<slug>.html), theme, summary and source scope (English and Korean)',
              f'- [Publication catalogue (CSV)]({SITE}/resources/data/publications.csv)',
              f'- [Homepage publication data (JSON)]({SITE}/data/publications.json)',
              f'- [Full text of all English summaries]({SITE}/llms-full.txt)',
              '', '## Notes',
              '- Each summary states which sources it was based on (abstract, main text or publication details only). Summaries are written by the lab site, not by the journals; quote the original article for authoritative results.',
              '']
    open(os.path.join(ROOT, 'llms.txt'), 'w', encoding='utf-8').write('\n'.join(lines))

    full = ['# BLISS Lab, Yonsei University — publication summaries (English)', '',
            f'Source: {SITE}/resources/en/publications.html. Principal investigator: {pi["nameEn"]} ({pi["nameKr"]}), '
            'School of Electrical and Electronic Engineering, Yonsei University.', '']
    for e in sorted((x for x in cat if x['language'] == 'en'), key=lambda x: -x['number']):
        full += [f'## #{e["number"]} {e["title"]}',
                 f'- Authors: {e.get("authors", "")}',
                 f'- Journal: {e.get("journal", "")}',
                 f'- DOI: https://doi.org/{e["doi"]}',
                 f'- Summary page: {e.get("url", "")}',
                 f'- Theme: {THEMES.get(e.get("theme"), e.get("theme") or "")}',
                 f'- Summary: {e["summary"]}',
                 f'- Source scope: {e["source_scope"]}', '']
    open(os.path.join(ROOT, 'llms-full.txt'), 'w', encoding='utf-8').write('\n'.join(full))

    today = datetime.date.today().isoformat()
    urls = [('/', today), ('/privacy.html', None), ('/llms.txt', today)]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, lm in urls:
        sm.append(f'<url><loc>{SITE}{u}</loc>' + (f'<lastmod>{lm}</lastmod>' if lm else '') + '</url>')
    sm.append('</urlset>')
    open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8').write('\n'.join(sm) + '\n')
    print('llms.txt, llms-full.txt, sitemap.xml written')


if __name__ == '__main__':
    main()
