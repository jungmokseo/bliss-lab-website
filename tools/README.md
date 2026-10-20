# Publication maintenance

Use the DOI to identify each paper and its bilingual Research Library pages.
Homepage publication numbers are display labels; never reassign an old numbered
redirect or infer a summary URL from a current number.

Keep the formal article title in `data/publications.json` and the library
bibliography. Put editorial labels, such as `Invited Review`, in the optional
`displayLabel` field outside the article-title link. Preserve scientific
subscripts and superscripts.

Research Library pages are editorial summaries. Their self-canonical WebPage
retains the summary description, language, classifications and displayed figure
metadata. Its `about` and `citation` references point to a separate
ScholarlyArticle whose `@id` and `url` are the original DOI URL. Original title,
authors, journal and publication date belong to that article. Do not label
editorial prose as the original abstract or article text, or add `citation_*`
paper-identification meta tags to these summaries. See the
[Scholar inclusion guidelines](https://scholar.google.com/intl/en/scholar/inclusion.html)
and Schema.org [citation](https://schema.org/citation).

After updating homepage publication data, regenerate and verify the HTML:

```sh
python3 tools/prerender.py
python3 tools/prerender.py --check
python3 tools/migrate_brief_slugs.py --check
python3 -m unittest discover -s tools -p 'test_*.py'
```

Run `build_llms.py` when its source data changes, and review generated diffs,
including sitemap dates. Set `lastmod` only for pages actually changed.
These checks verify source consistency; they do not measure search indexing,
AI citations or traffic.
