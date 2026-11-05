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

## Bilingual content checks

Homepage patents share one JSON array. Maintain `title/titleEn`,
`inventors/inventorsEn`, and `status/statusEn` together; a filed application
must remain distinct from a registered patent. News uses `title/titleEn` and,
when present, `summary/summaryEn`. Run `python3 tools/check_bilingual.py` before
publication; `--json` emits the detailed evidence. The check covers required
language fields, patent status and identity, paired library metadata, page
existence and reciprocal language routes. It does not certify translation
meaning or re-verify historical legal status.

Run `prerender.py` after patent changes as well as other homepage data changes.
It keeps bilingual patent records in the HTML when JavaScript or the data fetch
is unavailable. `build_llms.py` also exports the same patent records. Keep the
JavaScript and Python patent templates aligned when changing their presentation.

Notion changes use the connected tools and a reviewed merge into existing JSON.
Preserve fields absent from the current Notion schema, including English
inventor spellings and status labels. `sync-notion.py` remains an explanatory
file and does not perform synchronization when executed.

## Interface engineering: bilingual terminology and evidence

Use **interface engineering / 계면공학** to explain the lab's research across
tissue-contacting materials, deformable conductors, material/device integration,
and host-facing surfaces. Connect Jungmok Seo / 서정목 and BLISS Lab to this work
in the homepage introduction and library introduction. Preserve the four existing
library themes and DOI-based briefs; do not create parallel keyword landing pages.
The umbrella term does not make every paper an experimental bioelectronic device
study. Preserve the original paper's authorship and institutional attribution.

Maintain the following map here when editing either language. Terms belong in
the explanation of the relevant problem, material, mechanism or test; they are
not a list to paste into every page.

Each page should answer one main search intent, with only the related synonyms
that help readers. Follow the [Google SEO starter guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide)
and [AI features guidance](https://developers.google.com/search/docs/appearance/ai-features):
clear visible text and links remain the basis; special AI markup is not required.

| English term | Korean term | Where it applies and what must remain separate |
| --- | --- | --- |
| interface engineering; bioelectronic interface | 계면공학; 생체전자 계면 | Homepage and existing `/resources/ko/index.html` / English counterpart; explain which interfaces are designed and which measurements evaluate them. Do not claim field leadership or clinical validation. |
| hydrogel adhesion; wet-tissue adhesion | 하이드로젤 접착 / 하이드로겔 접착; 습윤 조직 접착 | Link tissue-facing work to the existing `tissue` theme, including STAT, DOI `10.1038/s41467-026-72068-6`. Treat 하이드로젤 and 하이드로겔 as spelling variants of the same term, without duplicate pages. Identify the substrate, bonding mechanism, wet condition and adhesion or biological endpoint. A tissue adhesive is not automatically an electrical interconnect. |
| heterogeneous material bonding; hydrogel adhesive | 이종 재료 접합; 하이드로젤 접착제 | Link d-HAPT to its existing DOI brief, `10.1038/s41528-024-00327-x`, under `integration`. The PVA–tannic-acid study's dry/dry bonding uses interfacial water and heating at 130 °C for 1 min; wet/dry bonding can occur without heating. Wet/wet and dry/tissue adhesion are limited, so do not describe it as a universal wet-tissue adhesive. Use “이종 재료 접합” for bonding unlike materials; do not imply a semiconductor heterojunction or a verified IC package. |
| hydrogel anisotropic conductive film; H-ACF | 하이드로젤 이방성 전도 필름; H-ACF | Keep this term attached to the [official 2023 MRS presentation](https://www.mrs.org/meetings-events/annual-meetings/archive/meeting/presentations/view/2023-mrs-spring-meeting/2023-mrs-spring-meeting-3837486). As of 2026-10-25, a corresponding peer-reviewed DOI is unconfirmed. Do not add a journal-publication record, invent a DOI, or conflate the presentation with the separate Nature Electronics 2022 interconnect study. |
| soft electronics; rigid–soft integration; IC packaging | 연성 전자소자; 강성–연성 집적; IC 패키징 | Use the existing `integration` theme. Distinguish packaging frameworks/reviews from devices actually fabricated and tested. DOI `10.1016/j.mser.2026.101285` is a review/framework; it does not establish experimental package performance. Attribute strain, pitch, resistance and lifetime to the tested specimen and conditions. |
| liquid metal; stretchable conductors and interconnects | 액체금속; 신축성 전도체와 배선 | Use the existing `routing` theme. Identify the conductive material, deformation and electrical measurement; material stretchability is not proof of complete package or implanted-device reliability. |
| antifouling; anti-biofouling; biofilm | 방오; 생물오염 억제; 바이오필름 | Use the existing `host` theme for the related stent/surface studies. Identify the endpoint: protein adsorption, initial bacterial attachment, mature biofilm, friction or encrustation. Reduction of one endpoint does not establish complete biofilm prevention. |
| ureteral stent; FLUID | 요관 스텐트; FLUID | DOI `10.1016/j.mtbio.2026.103405`. Preserve the distinction between 72-hour initial attachment and 14-day mature-biofilm assays, including species and comparator. Do not recast a urinary device as a biliary or vascular stent. |
| biliary stent; ELFS | 담도 스텐트; ELFS | DOI `10.1016/j.bioactmat.2026.02.003`. Keep gallbladder fouling and bile-duct patency models distinct. Describe the evaluated preclinical models, not clinical efficacy or all implant lifetimes. |
| endoscope antifogging and antifouling | 내시경 김서림·오염 억제 | DOI `10.1038/s41598-020-74517-8` concerns a lens surface; DOI `10.1021/acsami.6c04312` concerns a disposable cap. Keep optical visibility, fouling and mechanical durability endpoints with the correct device. |
| immune-evasive encapsulation; foreign-body response | 면역회피 캡슐화; 이물 반응 | Use only with the measured host-response evidence. For MOLE, DOI `10.1002/smll.202510949`, distinguish host-facing surface effects from the encapsulation barrier and mechanical tests. Do not imply absence of every immune response. |
| barrier encapsulation; moisture protection | 배리어 봉지; 수분 차단 | State the tested barrier function and environment. Moisture protection and immune evasion are different properties; an OLED encapsulation review (`10.1002/aelm.202500475`) is not evidence of implanted-device lifetime. |
| neural interface; chronic recording | 신경 계면; 장기 신경 기록 | TAB, DOI `10.1126/sciadv.adz1228`, combines a lubricated interface with immobilized BDNF. Distinguish representative 12-month mouse recordings from the separate 8-month electrode-level statistical comparison. Do not imply zero immune response or a one-year guarantee for every device. |
| liquid metal; EGaIn; PVA-modified particles | 액체금속; 공정 갈륨–인듐; PVA 개질 입자 | PmLMP, DOI `10.1002/advs.78062`, uses spray-impact activation together with flow-driven capillary fusion. Do not attribute oxide disruption to capillarity alone or use conductor performance as IC-bond yield evidence. |
| hydrogel interface; analyte diffusion | 하이드로젤 계면; 분석물 확산 | ISC-PAH, DOI `10.1002/adma.202515767`, belongs with tissue-contacting materials and electrochemical biosensors. Small healthy-participant and mouse demonstrations do not establish clinical efficacy. |

For each substantive claim, preserve the sequence **interface problem → design
and mechanism → measured result → test conditions and limits → DOI/original
source**. Keep units, sample type, comparator and duration alongside numerical
results. Preserve differences between representative examples and comparative
statistics. Keep reviews, conference presentations, in vitro tests, animal
experiments and clinical studies explicitly distinct. Use nanowire terminology
only for papers that actually study nanowires, not as a general lab positioning
claim. Never infer “first”, “leading”, clinical validation or universal device
lifetime from an individual paper.

## Where to maintain the terms

- **Homepage and library headings:** name interface engineering and describe the
  actual research questions. Homepage text lives in `index.html`, including its
  `data-kr` / `data-en` values; library introductions live in the existing
  `resources/{ko,en}/index.html` pages. Keep the language pairs equivalent in
  evidence and certainty, while allowing natural phrasing.
- **Titles and descriptions:** use a descriptive editorial page title and a
  readable summary of its subject. Keep `<title>`, description and Open Graph
  descriptions consistent with visible content. Preserve the formal published
  article title in bibliography and `ScholarlyArticle`; do not insert search
  phrases into an original title.
- **Headings and links:** use specific anchors such as “hydrogel material
  bonding” or “담도 스텐트 방오 연구” when linking to the matching existing
  brief/theme. Preserve stable DOI slugs, self-canonicals and reciprocal language
  links. Do not add duplicate URLs solely to target spelling variants.
- **Classification and structured data:** assign `theme` for the paper's actual
  main subject. Keep `source_level`, `source_scope` and
  `jungmok_seo_author_role` evidence-based. Structured data must describe visible
  content and distinguish the editorial WebPage from the DOI-identified article.
  Do not add meta-keyword lists, hidden search terms, AI-specific schema or
  unsupported schema claims. Do not create new keyword pages.
- **Generated copies:** when changing a catalogue summary, update its matching
  brief, listing and featured-card copies in both languages as applicable, plus
  `resources/data/publications.csv`. Regenerate `llms.txt` / `llms-full.txt` when
  their source changes. Review generated diffs and actual modification dates;
  `build_llms.py` currently stamps `/` and `/llms.txt` with its execution date.

## Selected brief titles and entry links

For the three briefs below, the localized `<title>`, `og:title` and `WebPage.name`
describe the library commentary. The visible paper H1, catalogue title and
`ScholarlyArticle.name/headline` retain the formal published title. This is a
small editorial selection, not a template change for every paper.

| Existing DOI slug | Main reading intent (Korean / English) |
| --- | --- |
| `acsami-6c04312` | 내시경 캡의 김서림·오염 억제 / Endoscope-cap fogging and fouling (SHIELD-C) |
| `mtbio-2026-103405` | 요관 스텐트의 윤활·세균 부착·결석 침착 / Ureteral-stent lubrication, adhesion and encrustation (FLUID) |
| `mser-2026-101285` | 유연·신축성 전자소자의 IC 칩 패키징 종설 / IC-chip packaging review for flexible and stretchable electronics |

The existing library introduction links directly to these DOI briefs; retain the
featured cards and four themes. Keep the root Korean alias's links relative to
`ko/`. The SHIELD-C catalogue summary is synchronized to its listing/theme cards,
page description, Open Graph description, WebPage description and `llms-full.txt`.
It identifies benchtop/ex vivo endoscopic evaluation; exact results remain in the
brief body. Source-scope records are not recertified by a title or summary edit.

The packaging brief's related-reading paragraph separates d-HAPT material bonding,
IC electrical contacts, and MOLE moisture-barrier encapsulation. MOLE's accelerated
and short animal tests do not demonstrate cyclic IC-contact reliability or human
service life. Its H-ACF link leads to the existing, separately labelled conference
note; it is not a claim that the packaging review cites or validates that work.

The homepage's original English hero copy, design, buttons and font were restored
at the user's request in `144b884`; preserve them during discovery improvements.
Content edits and successful local checks do not authorize a push, PR or deployment.

## Notion publication records and public website data

`sync-notion.py` documents the existing Notion Publication DB and its manual MCP
export route; it is a comments-only guide, not an automatic synchronizer. Use the
active DB identified there, never the archived seed DB. Coordinate any Notion
write with the person maintaining that DB; website editing alone does not require
or authorize changing it. The live DB schema and sync freshness were not audited
in the 2026-10-25 website maintenance pass.

Treat the DOI, checked against the publisher/original source, as the join key:

| Destination | Public fields eligible for a reviewed transfer | Handling |
| --- | --- | --- |
| `data/publications.json` | Published title, authors and author order, journal/volume/pages, year, DOI link; existing public display number and image reference | Verify bibliographic changes against public records. Display numbers are labels, not permanent identifiers. Confirm image source and reuse permission separately. Do not infer or refresh impact factors from unverified notes. |
| `resources/data/publications.json` | The verified public bibliography above, `doi`, stable `slug`, `url`, `language` | Match existing English and Korean records by DOI. Do not create a second brief because a display number changed. |
| Library editorial fields and HTML | `theme`, verified `jungmok_seo_author_role`, `source_level`, `summary`, `source_scope`, explanations and limitations | Maintain as reviewed website commentary based on the stated sources. These are not an automatic import of a Notion abstract or private research notes. Keep JSON, CSV, pages and generated summaries consistent. |

Do not export private notes, unpublished manuscripts or results, internal review
status, student information, credentials, private attachments or private links.
Keep records marked **Submitted** private; do not include them in public exports.
An entry's presence in Notion does not establish permission to publish it. Include
patent information only after checking its public disclosure and citation details.
Public bibliographic metadata does not confer permission to republish full text
or figures. This workflow does not change Notion access or sharing permissions.

## Local review, deployment and measurement

The institutional domain remains `https://bliss.yonsei.ac.kr/` (`CNAME`). Main
commits currently trigger GitHub Pages builds and deployment: for example,
`fe89679625a8cd30c20803255e923b7e0ad93ad7` ran
[pages build and deployment](https://github.com/jungmokseo/bliss-lab-website/actions/runs/39366435460)
on 2026-10-20. Treat pushing to `main` as publishing. Prepare and review exact
diffs, source references, bilingual wording, metadata/canonical links, internal
links, structured data, local checks and desktop/mobile readability before an
authorized deployment. The 2026-10-25 maintenance scope permits local editing and
verification only; do not push or deploy until the concrete changes are reviewed
and publication authorization is confirmed.

Keep the existing eight evaluation questions and search conditions fixed. The
actual AI baseline is **2026-10-14–15**, with the planned four-week comparison on
**2026-11-11** and eight-week comparison on **2026-12-09**. Do not rerun the baseline
on 2026-10-25 or retry to select favorable answers. A page availability or sitemap
check is an operational check, not a new AI baseline.

Record these outcomes separately: (1) discovery of relevant research, (2) direct
discovery of BLISS/Jungmok Seo, (3) actual AI citation of a source, and (4) search
traffic. An HTTP 200, valid structured data, an indexed page or a related-paper
mention does not establish the other outcomes. Content and keyword maintenance
can improve clarity and source traceability; it does not guarantee rankings,
traffic, prominence or AI citations. Google API recovery remains a separate,
deferred task and is outside this website edit.
