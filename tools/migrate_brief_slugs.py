#!/usr/bin/env python3
"""Move research-library briefs from number-keyed to DOI-slug addresses.

  python3 tools/migrate_brief_slugs.py            # perform the migration (git mv + rewrites)
  python3 tools/migrate_brief_slugs.py --dry-run  # list what would change, touch nothing
  python3 tools/migrate_brief_slugs.py --check    # verify the migrated tree (exit 1 on problems)

Why: brief pages used to live at resources/{ko,en}/papers/NNN.html where NNN is the
site paper number. Numbers shift when a paper is inserted (2026-10-16: #88 was
inserted and 88-101 became 89-102), which silently broke every shared link.
GitHub Pages cannot send 301s, so the stable address is a DOI-derived slug and
the numbered addresses stay behind as thin stubs.

Slug rule (slug_for): lowercase the DOI, keep only the part after the registrant
prefix "10.xxxx/", drop a leading "j.", turn every run of non-alphanumerics into
"-". If the result does not start with a letter (e.g. 10.1063/1.4994708) the
registrant code is kept in front ("1063-1-4994708"). A paper without a DOI gets
the first six words of its title. Examples: 10.1002/adhm.202504939 ->
adhm-202504939, 10.1016/j.mtbio.2026.103405 -> mtbio-2026-103405.

What the migration does
1. resources/data/publications.json|csv: add "slug" after "doi"; "url" points at
   the slug page.
2. git mv resources/{ko,en}/papers/NNN.html -> <slug>.html. Inside each page every
   papers/NNN.html reference (canonical, og:url, hreflang, language switch, JSON-LD,
   related-brief links) becomes the slug path, and the 2026-10-16 renumber notice is
   removed (it moves to the numbered stub).
3. Numbered stubs NNN.html are written back:
   - plain stub: <meta http-equiv="refresh" content="0; url=<slug>.html"> + canonical
     to the slug page + a one-line link (no noindex: an instant refresh already tells
     crawlers the page moved, and noindex would make them ignore the canonical);
   - 088-101 (addresses whose paper changed on 2026-10-16): a no-redirect choice page
     that names the paper now at that number and keeps the earlier notice naming the
     paper shown there before, each linked to its slug page; noindex,follow.
   Stubs are frozen at the 2026-10-19 mapping and are never regenerated; new papers
   get a slug page only.
4. Every papers/NNN.html reference in index.html, resources/**/*.html and
   resources/sitemap.xml is rewritten to the slug path (sitemap lastmod = today).

Afterwards run  python3 tools/prerender.py && python3 tools/build_llms.py  and
commit everything. Figure assets (resources/assets/*/paper-NNN-*) and the
in-page labels ("PUBLICATION 088", breadcrumb "088", card anchors #paper-NNN)
keep the number: they are not shared addresses.
"""
import csv, datetime, io, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://bliss.yonsei.ac.kr'
RES = os.path.join(ROOT, 'resources')
CAT_JSON = os.path.join(RES, 'data', 'publications.json')
CAT_CSV = os.path.join(RES, 'data', 'publications.csv')
LANGS = ('ko', 'en')
RENUMBERED = range(88, 102)          # addresses whose paper changed on 2026-10-16 (old paper = number + 1)
STUB_MARK = '<!-- numbered-address-stub: frozen 2026-10-19; the slug page is canonical -->'
NUM_REF = re.compile(r'papers/(\d{3})\.html')
SAME_DIR_REF = re.compile(r'href="(\d{3})\.html"')
NOTICE = re.compile(r'<aside class="notice compact renumber-notice" role="note">(.*?)</aside>', re.S)

T = {
    'ko': dict(moved='이 논문 해설은 새 주소로 옮겨졌습니다:', skip='본문으로 건너뛰기',
               h1='주소 안내', now='현재 이 번호({n}번)의 논문은 「{title}」입니다.', read='해설 보기 →',
               title_stub='{n}번 주소 안내', lib='BLISS Lab Research Library, Yonsei University'),
    'en': dict(moved='This research brief has moved to:', skip='Skip to content',
               h1='Address notice', now='The paper now at this number (No. {n}) is “{title}”.', read='Read the brief →',
               title_stub='Address notice for No. {n}', lib='BLISS Lab Research Library, Yonsei University'),
}


def slug_for(entry):
    doi = (entry.get('doi') or '').strip().lower()
    if doi and '/' in doi:
        prefix, suffix = doi.split('/', 1)
        suffix = re.sub(r'^j\.', '', suffix)
        s = re.sub(r'[^a-z0-9]+', '-', suffix).strip('-')
        if not re.match(r'[a-z]', s):
            s = re.sub(r'^10\.', '', prefix) + '-' + s
        return s
    words = re.findall(r'[a-z0-9]+', (entry.get('title') or '').lower())
    return '-'.join(words[:6])


def load_catalogue():
    return json.load(open(CAT_JSON, encoding='utf-8'))


def slug_map(cat):
    """number -> slug, checking that both languages agree and slugs are unique."""
    m = {}
    for e in cat:
        s = e.get('slug') or slug_for(e)
        if m.setdefault(e['number'], s) != s:
            raise SystemExit(f'slug mismatch for #{e["number"]}: {m[e["number"]]} / {s}')
    rev = {}
    for n, s in m.items():
        if rev.setdefault(s, n) != n:
            raise SystemExit(f'duplicate slug {s} for #{rev[s]} and #{n}')
    return m


def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))


def with_slug(entry, slug):
    out = {}
    for k, v in entry.items():
        if k == 'slug':
            continue
        out[k] = v
        if k == 'doi':
            out['slug'] = slug
    if 'slug' not in out:
        out['slug'] = slug
    out['url'] = f'{SITE}/resources/{entry["language"]}/papers/{slug}.html'
    return out


def write_catalogue(cat, slugs):
    new = [with_slug(e, slugs[e['number']]) for e in cat]
    open(CAT_JSON, 'w', encoding='utf-8').write(json.dumps(new, indent=2, ensure_ascii=False) + '\n')
    raw = open(CAT_CSV, encoding='utf-8-sig', newline='').read()
    rows = list(csv.reader(io.StringIO(raw)))
    head = rows[0]
    if 'slug' not in head:
        head.insert(head.index('doi') + 1, 'slug')
    ni, li, si, ui = head.index('number'), head.index('language'), head.index('slug'), head.index('url')
    body = []
    for r in rows[1:]:
        if len(r) == len(head) - 1:
            r.insert(si, '')
        n = int(r[ni])
        r[si] = slugs[n]
        r[ui] = f'{SITE}/resources/{r[li]}/papers/{slugs[n]}.html'
        body.append(r)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(head)
    w.writerows(body)
    open(CAT_CSV, 'w', encoding='utf-8', newline='').write('﻿' + buf.getvalue())
    return new


def rewrite_refs(text, slugs):
    return NUM_REF.sub(lambda m: f'papers/{slugs[int(m.group(1))]}.html', text)


def rewrite_same_dir(text, slugs):
    return SAME_DIR_REF.sub(lambda m: f'href="{slugs[int(m.group(1))]}.html"', text)


def is_stub(path):
    return os.path.exists(path) and STUB_MARK in open(path, encoding='utf-8').read(4096)


def h1_text(html):
    m = re.search(r'<h1 class="paper-title">(.*?)</h1>', html, re.S)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else ''


def head_bits(html, lang, n):
    """Site header/footer of the brief, with the language switch pointing at the other stub."""
    other = 'en' if lang == 'ko' else 'ko'
    header = re.search(r'<header class="site-header">.*?</header>', html, re.S).group(0)
    header = re.sub(r'(<a class="lang-switch" href=")[^"]*(")', rf'\g<1>../../{other}/papers/{n:03d}.html\2', header)
    footer = re.search(r'<footer class="site-footer">.*?</footer>', html, re.S).group(0)
    return header, footer


def plain_stub(lang, n, slug, title):
    t = T[lang]
    url = f'{SITE}/resources/{lang}/papers/{slug}.html'
    return (f'<!DOCTYPE html>\n<html lang="{lang}"><head><meta charset="utf-8"/>'
            f'<meta content="width=device-width,initial-scale=1" name="viewport"/>\n{STUB_MARK}\n'
            f'<title>{esc(title)} | {t["lib"]}</title>\n'
            f'<meta content="0; url={slug}.html" http-equiv="refresh"/>\n'
            f'<link href="{url}" rel="canonical"/>\n'
            f'<link href="../../assets/library.css" rel="stylesheet"/></head>\n'
            f'<body><main class="container" id="main"><p>{t["moved"]} <a href="{slug}.html">{esc(title)}</a></p></main></body></html>\n')


def choice_stub(lang, n, slug_now, title_now, notice_html, header, footer):
    t = T[lang]
    return (f'<!DOCTYPE html>\n<html lang="{lang}"><head><meta charset="utf-8"/>'
            f'<meta content="width=device-width,initial-scale=1" name="viewport"/>\n{STUB_MARK}\n'
            f'<title>{t["title_stub"].format(n=f"{n:03d}")} | {t["lib"]}</title>'
            f'<meta content="noindex,follow" name="robots"/>\n'
            f'<link href="../../assets/library.css" rel="stylesheet"/><script defer="" src="../../assets/library.js"></script></head>\n'
            f'<body><a class="skip-link" href="#main">{t["skip"]}</a>\n{header}'
            f'<main class="container" id="main"><div class="breadcrumbs"><a class="" href="../index.html">'
            f'{"자료실" if lang == "ko" else "Library"}</a> <span>/</span> {n:03d}</div>'
            f'<section class="page-heading"><div class="paper-meta"><span class="eyebrow">PUBLICATION {n:03d}</span></div>'
            f'<h1 class="paper-title">{t["h1"]}</h1>'
            f'<p class="lead">{t["now"].format(n=f"{n:03d}", title=esc(title_now))} '
            f'<a href="{slug_now}.html">{t["read"]}</a></p></section>'
            f'<aside class="notice renumber-notice" role="note">{notice_html}</aside></main>\n{footer}\n</body></html>\n')


def migrate(dry):
    cat = load_catalogue()
    slugs = slug_map(cat)
    moved = 0
    for lang in LANGS:
        d = os.path.join(RES, lang, 'papers')
        for n in sorted(slugs):
            src, dst = os.path.join(d, f'{n:03d}.html'), os.path.join(d, f'{slugs[n]}.html')
            if is_stub(src):
                continue
            if not os.path.exists(src):
                raise SystemExit(f'missing {src}')
            if os.path.exists(dst):
                raise SystemExit(f'{dst} already exists but {src} is not a stub')
            html = open(src, encoding='utf-8').read()
            m = NOTICE.search(html)
            notice = m.group(1) if m else ''
            page = rewrite_same_dir(rewrite_refs(NOTICE.sub('', html), slugs), slugs)
            title = h1_text(html)
            header, footer = head_bits(page, lang, n)
            if n in RENUMBERED:
                if not notice:
                    raise SystemExit(f'{src}: expected a renumber notice')
                stub = choice_stub(lang, n, slugs[n], title, rewrite_same_dir(notice, slugs), header, footer)
            else:
                stub = plain_stub(lang, n, slugs[n], title)
            print(f'{"would move" if dry else "move"} {lang}/papers/{n:03d}.html -> {slugs[n]}.html'
                  + (' (choice stub)' if n in RENUMBERED else ''))
            moved += 1
            if dry:
                continue
            subprocess.run(['git', 'mv', src, dst], cwd=ROOT, check=True)
            open(dst, 'w', encoding='utf-8').write(page)
            open(src, 'w', encoding='utf-8').write(stub)
    # references elsewhere
    targets = [os.path.join(ROOT, 'index.html'), os.path.join(RES, 'index.html'), os.path.join(RES, 'sitemap.xml')]
    for lang in LANGS:
        for dp, _, fs in os.walk(os.path.join(RES, lang)):
            if os.path.basename(dp) == 'papers':
                continue
            targets += [os.path.join(dp, f) for f in fs if f.endswith('.html')]
    today = datetime.date.today().isoformat()
    for p in targets:
        text = open(p, encoding='utf-8').read()
        new = rewrite_refs(text, slugs)
        if p.endswith('sitemap.xml'):
            new = re.sub(r'(<loc>[^<]*papers/[^<]*</loc><lastmod>)[^<]*(</lastmod>)',
                         lambda m: m.group(1) + today + m.group(2),
                         NUM_REF.sub(lambda m: f'papers/{slugs[int(m.group(1))]}.html', text))
        if new != text:
            print(f'{"would rewrite" if dry else "rewrite"} {os.path.relpath(p, ROOT)} ({len(NUM_REF.findall(text))} refs)')
            if not dry:
                open(p, 'w', encoding='utf-8').write(new)
    if not dry:
        write_catalogue(cat, slugs)
        print('catalogue: slug + url updated')
    print(f'{moved} pages {"would be" if dry else ""} moved')


def check():
    cat = load_catalogue()
    problems = []
    slugs = {}
    for e in cat:
        if not e.get('slug'):
            problems.append(f'catalogue #{e["number"]} {e["language"]}: no slug')
            continue
        slugs[e['number']] = e['slug']
        want = f'{SITE}/resources/{e["language"]}/papers/{e["slug"]}.html'
        if e.get('url') != want:
            problems.append(f'catalogue #{e["number"]} {e["language"]}: url {e.get("url")} != {want}')
        for lang in LANGS:
            if not os.path.exists(os.path.join(RES, lang, 'papers', f'{e["slug"]}.html')):
                problems.append(f'missing {lang}/papers/{e["slug"]}.html')
    for lang in LANGS:
        for n in slugs:
            p = os.path.join(RES, lang, 'papers', f'{n:03d}.html')
            if not is_stub(p):
                problems.append(f'{lang}/papers/{n:03d}.html is not a stub')
    # numbered references outside the stubs; relative links resolve
    files = [os.path.join(ROOT, 'index.html'), os.path.join(ROOT, 'llms.txt'), os.path.join(ROOT, 'llms-full.txt'), CAT_CSV]
    for dp, _, fs in os.walk(RES):
        files += [os.path.join(dp, f) for f in fs if f.endswith(('.html', '.xml'))]
    for p in files:
        text = open(p, encoding='utf-8').read()
        stub = STUB_MARK in text
        if not stub and NUM_REF.search(text):
            problems.append(f'{os.path.relpath(p, ROOT)}: numbered reference {NUM_REF.search(text).group(0)}')
        if p.endswith('.html'):
            for ref in re.findall(r'(?:href|src)="([^"#?]+)', text):
                if '${' in ref:          # JS template literal inside index.html's renderers
                    continue
                if re.match(r'(?:[a-z]+:|//)', ref) or ref.startswith('/'):
                    if ref.startswith('/') and not ref.startswith('//'):
                        tgt = os.path.join(ROOT, ref.lstrip('/'))
                    else:
                        continue
                else:
                    tgt = os.path.normpath(os.path.join(os.path.dirname(p), ref))
                if not os.path.exists(tgt):
                    problems.append(f'{os.path.relpath(p, ROOT)}: broken link {ref}')
    for pr in problems[:60]:
        print('PROBLEM', pr)
    print(f'{len(problems)} problems' if problems else f'ok: {len(slugs)} papers, stubs and slug pages consistent, links resolve')
    return 1 if problems else 0


if __name__ == '__main__':
    if '--check' in sys.argv:
        sys.exit(check())
    migrate('--dry-run' in sys.argv)
