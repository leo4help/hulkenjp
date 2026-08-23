# Hulken JP Weekly Report — Project Guide for Claude

## What this project is

A static, single-page-per-week HTML report site (`廣告成效週報`) for Hulken JP, covering Meta / Google / Amazon / Rakuten / KOL ad performance. Each week produces one self-contained HTML file (no build pipeline, no framework — plain HTML/CSS/JS with the week's numbers hardcoded into `<script>` blocks). The site is published two ways:

- **Production (protected):** Cloudflare Pages → `https://hulkenjp.pages.dev`, gated by Cloudflare Access (Zero Trust) so only `@wakazocorp.com` emails can view it.
- **GitHub Pages is intentionally disabled** (Settings → Pages → Source: None). Do not re-enable it without asking the user — it would create an unprotected public mirror of the same content, defeating the Access gate.

Project root on the user's machine:
```
/Users/leo_zen/Documents/Claude/Projects/Hulken Weekly Report/
```

GitHub repo: `leo4help/hulkenjp`, branch `main`. **Account isolation rule (hard constraint):** the user owns a second GitHub account (`leo-mkter`) used for a different client. Never suggest adding `leo-mkter` as a collaborator on this repo, or otherwise cross-permission the two accounts — the user has explicitly rejected this in the past. All auth for this repo should stay scoped to `leo4help` only (fine-grained PAT scoped to just this repo, if a token is needed).

---

## Weekly workflow (every week)

### Step 1 — User places the data file
User drops the week's data file into a new week folder, e.g. `2026W33/Hulken_Claude_Bridge.xlsx`. As of W33 the user only sends the lightweight `Hulken_Claude_Bridge.xlsx` (not the full `Halken JP_Mastersheet.xlsx` — note the source filename really is spelled "Halken", not "Hulken"; that's not a typo to fix, it's the user's original file name).

### Step 2 — Read the data
**Full instructions live in `Mastersheet_Tab_Guide.md`** (in the project root, gitignored — it's an internal process doc, never pushed to GitHub). Read that file first, every time, before touching the data — it may have been updated since this guide was written. Summary of the current approach:

1. Read `Hulken_Claude_Bridge.xlsx` → `Claude_Analysis_Data` tab (trailing 28 days, fast).
2. Read `_cache/ad_data_historical_cache.pkl.gz` (everything older than 28 days, already has derived columns like `goal`/`testFlag`/`NameRow`/`Row`/`isKOL`).
3. Concat the two → equivalent to the full `ad_data`, without ever opening the full `Halken JP_Mastersheet.xlsx`.
4. Also read `Weekly Report Manual`, `Datastudio Custom Metrics`, and `Weekly Insight` from the Bridge file (all small).
5. Only fall back to the full `Halken JP_Mastersheet.xlsx` if the user actually sends it (e.g. cache needs rebuilding, or checking data older than the cache cutoff).

Known accepted gap: the `成果指標` text column has blanks in the Bridge file vs. the full Mastersheet — already confirmed by the user as ignorable, don't re-raise it. See `Mastersheet_Tab_Guide.md` for the full list of known quirks, the KOL 授權金 formula, and which tabs never need opening.

### Step 3 — Build the week's HTML report
There is no Python build script for this project (unlike some other clients' projects) — each week's HTML is a full copy of the previous week's file with the numbers swapped in. **Always start from the most recent week's HTML as the template**, don't rebuild from scratch — it guarantees the CSS/JS/layout stay identical.

What has to change in the new file:
- `<title>` and the `sub` line under the H1 (updater name, date, date range)
- The `const` data blocks in the closing `<script>` block — these are hand-computed from the xlsx data, not fetched at runtime:
  - `const kpis = [...]` — the 6 Overview KPI tiles (花費金額, CPA, ROAS, CTR, CVR, CPM) incl. WoW deltas
  - `const channelRows = [...]` — Overview · 全渠道 breakdown table
  - `const metaTestRows` / `const metaTestKol` — Meta 測試素材 section (General vs TEST split)
  - `const metaCreative` / `const metaCreativeTotal` — Meta 常態素材 table
  - `const kolRows` / `const kolGrand` — KOL 表現＋授權金 table
- **`const WEEKS = [...]`** at the top of the script — add the new week as a new first entry with `isCurrent:true`, remove `isCurrent` from the previous week, keep `href` as a relative path `../<WeekFolder>/<file>.html`. Only set `isBeta:true` on an entry if the user explicitly asks for a Beta tag (currently only Week 31 has it — don't add it to new weeks by default).
- Footer week/date-range text.

Section IDs/nav: `#overview`, `#channels`, `#meta-test`, `#meta-creative`, `#kol`. Nav labels through W33: Overview 總覽 / 全渠道成效 / Meta 測試素材 / Meta 常態素材 / KOL 表現＋授權金. **W34 onward, the last label changes to "本週 KOL 表現 (含授權金)"** (see the W34+ header CTA note above) — don't carry the old "KOL 表現＋授權金" label forward.

> **KOL calculator moved out as of W34 (decided 2026-08-20, finalized 2026-08-23).** The "KOL 第二波授權金談判計算機" section (`#kol-calc`, its nav link, the `const LIC_ROW_DATA = {...}` block, and the `initLicCalc()` IIFE) is **no longer part of the weekly report template starting with Week 34**. It now lives permanently on its own page — see Step 6 below and "Standalone `/all` page" in the HTML structure reference. `2026W33/hulken_week33_report.html` still has it embedded (left as-is per the user's explicit request, since it was already published) — don't backport the removal to W33, and don't carry the `#kol-calc` section forward when building W34+ from a template that still has it.
>
> **W34+ also adds a header CTA button linking to the standalone page (finalized 2026-08-23).** In the second `.header-inner` row (the one holding `.title-block`), add a sibling `<a class="kol-header-btn" href="https://hulkenjp.pages.dev/all" target="_blank" rel="noopener">完整成效 & KOL 授權計算機 ↗</a>` — a gold-gradient pill button (see CSS below), `align-self:center` so it sits next to the title/sub text (below the week-picker row, beside the title block — not under the date picker). This replaces the old in-report calculator as the way users reach the license-fee tool. There is **no other CTA** for it — no separate card/description block anywhere else on the page (an earlier design draft had one at the bottom of the `#kol` section; the user asked for it removed), and the nav bar must NOT also carry a separate "KOL 授權金計算機 ↗" external link (an earlier draft had one; it duplicated the header button and was removed per user feedback). Nav label for the KOL section also changes: "KOL 表現＋授權金" → **"本週 KOL 表現 (含授權金)"** (wherever it appears — nav link, section `<h2>`, and any cross-reference in hint text). CSS for the button:
> ```css
> .kol-header-btn{display:inline-flex;align-items:center;gap:6px;flex:0 0 auto;padding:10px 18px;border-radius:10px;background:linear-gradient(135deg, var(--brand-gold), #c79b3f);color:#fff;font-size:13px;font-weight:700;text-decoration:none;white-space:nowrap;box-shadow:0 3px 10px rgba(169,130,46,0.3);transition:transform .1s, box-shadow .15s;align-self:center;}
> .kol-header-btn:hover{transform:translateY(-1px);box-shadow:0 5px 14px rgba(169,130,46,0.38);}
> @media (max-width:640px){.kol-header-btn{align-self:flex-start;}}
> ```

**Images:** ad creative thumbnails are NOT embedded as base64 — they're referenced as relative paths `../AD Images/<Row>.jpg`, where `<Row>` is extracted from the ad name via the trailing `-<digits>` pattern. If the user adds new creative screenshots this week, they go into `AD Images/` at the project root, named `<Row>.jpg`, and no report file needs to change for them to show up — just make sure that folder gets pushed (see Step 5).

> Known quirk, not a bug to fix proactively: `2026W31/hulken_week31_report.html` is ~1.5MB because it predates the relative-path image approach and still has base64-embedded images baked in. `2026W32/hulken_week32_report.html` (94KB) uses the lighter approach and is the pattern to follow for all future weeks. Don't "fix" W31 unless the user asks — it's already published.

### Step 4 — Update the root redirect
`index.html` at the project root is a **static, unchanging** file — it fetches `manifest.json` at runtime and redirects to whatever week that points to. Every week, after building the new report, update `manifest.json` (small file, project root):

```json
{
  "latestFolder": "2026W33",
  "latestFile": "hulken_week33_report.html",
  "updated": "2026-08-23"
}
```

Do this automatically as part of finishing a week's build — don't wait for the user to ask.

### Step 5 — Give the user the push commands (Claude never runs `git push` itself)
The user runs all git commands locally themselves — always give a ready-to-paste command block, never run push on their behalf.

**Hard rule, explicitly requested by the user — every single git command block, every time, must:**
1. Start with `cd "/Users/leo_zen/Documents/Claude/Projects/Hulken Weekly Report"` (the full absolute path, quoted — never a relative path, never assume the shell is already there, never omit it because "you already cd'd earlier in the conversation").
2. Be copy-paste-ready as one block — the user wants to paste it without thinking ("無腦貼上"), not assemble commands from separate instructions.

**Every push command block must also explicitly `git add` the new week folder, the `AD Images` folder, `manifest.json`, and `all.html`** (and `index.html` if it changed) — don't just say `git add .`, since a blanket add is fine here (nothing sensitive lives outside the gitignored patterns) but being explicit avoids accidentally missing a folder if the user only copy-pastes part of it. `all.html` changes every week from W33 onward (see Step 6), so include it by default unless the user says it wasn't touched that week. Standard block:

```bash
cd "/Users/leo_zen/Documents/Claude/Projects/Hulken Weekly Report"
git add 2026W33 "AD Images" manifest.json index.html all.html
git commit -m "Add W33 weekly report"
git push
```

> **`kol.html` → `all.html` rename (2026-08-23).** The standalone page was renamed from `kol.html` (served at `/kol`) to `all.html` (served at `/all`) — see Step 6 and "Standalone `/all` page" below for what changed content-wise. `kol.html` had never been shared/exposed to anyone, so it was retired outright rather than kept as a redirect. If `kol.html` is still tracked in git from an earlier push, the first push after this rename must also remove it: add `git rm kol.html` to the command block (harmless no-op if it was never committed). Don't reintroduce `kol.html` — the file itself has been moved to `_to_delete/` locally per the usual convention for files the user wants gone.

If the user reports a push error, check these known causes before anything else:
- **`RPC failed; HTTP 400` / unexpected disconnect** — fixed by running once: `git config http.postBuffer 524288000` and `git config http.version HTTP/1.1`, then retry `git push`. This isn't a permissions issue.
- **`Permission denied to <wrong-account>`** — means the wrong GitHub account is cached in credentials. Do NOT suggest adding that account as a collaborator (violates the account-isolation rule above). Instead have the user generate a fine-grained PAT for `leo4help` scoped only to `hulkenjp`, with **Contents: Read and write** permission (this is the specific permission that's easy to forget — token creators often add unrelated permissions like "Repository security advisories" instead), and set it via `git remote set-url origin https://leo4help:<TOKEN>@github.com/leo4help/hulkenjp.git` (repo-scoped, doesn't touch global git credentials).
- After a successful push, confirm on GitHub itself (`https://github.com/leo4help/hulkenjp`) that the new folder and images actually show up — a misleading "Everything up-to-date" can print even after a failed transfer.

### Step 6 — Refresh the standalone `/all` page (added W33 as `/kol` on 2026-08-20; broadened to all-creative `/all` and finalized 2026-08-23)

`all.html` at the project root is a **separate, standalone page** — not part of the week-by-week report chain — published at `https://hulkenjp.pages.dev/all` (Cloudflare Pages' default clean-URL routing serves `/all.html` for a request to `/all`; see "Hosting / Cloudflare setup" below). It exists because the KOL license-fee negotiation calculator no longer lives inside each week's report (see the note in Step 3) — it now has one canonical home instead, alongside a full-scope Lifetime performance table. It contains two things:

- **`#kol-lifetime`** ("Lifetime 全素材表現＋KOL 授權金") — a table covering **all Meta creative** (原廠 ＋ KOL, i.e. `AD_Channel=='Meta AD'` — excludes Google/PMax/Shopping-ad — with `goal not in ['-','CPC']`), computed over the **full all-time `ad_data`** (no time-window filter), grouped per-`NameRow`, with the WoW `%Δ` columns removed (lifetime has no "previous period" to compare against). **This is broader than the weekly report's own `#kol` table**, which stays KOL-only and single-week — don't confuse the two or try to make them match row-for-row. Columns: Name-Row (with thumbnail), 原廠標記 (tag badge, via the same `tagBadge()` used by the weekly report's Meta 常態素材 table), 花費金額 (JPY), CPA, ROAS, CTR, CVR, CPM. Rendered from `const kolLifetimeRows = [...]` (137 rows as of 2026-08-23: ~68 KOL + ~69 原廠 — counts drift week to week as new creative launches) via `computeKolAggregate()` / `renderKolLifetimeTable()` / `renderKolSummary()` (internal function/variable names kept as `kol*` for historical continuity even though the table is no longer KOL-only — don't rename them mid-project, it's cosmetic).
  - Each row carries `isKOL` (bool) and `tag` (raw `原廠標記` value, may be `null`) plus raw components (`mediaCost, lic, revenue, clicks, impressions, purchases`) so the client can recompute weighted aggregates for any filtered subset — **never average the pre-computed per-row ratios**, always re-derive from summed raw components (see `computeKolAggregate()`).
  - Only KOL rows (`isKOL:true`) carry a non-zero `lic` (attributed license fee); their 花費金額 cell shows the attributed-license sub-line and their ROAS cell shows the license-fee-excluded `mediaRoas` sub-line. 原廠 rows show neither sub-line — they have no license fee.
  - **Two-layer filter, above the table:** (1) a category toggle — three mutually-exclusive pill buttons "全部 / KOL / 非 KOL" (`#kolCatAll` / `#kolCatKol` / `#kolCatNonKol`), default 全部 — narrows the row universe first; (2) the existing searchable multi-select dropdown (`#kolFilter`) narrows further by name within whatever category is active. Switching category clears the name selection (selected names may not exist in the new category). Both layers drive the table, the **Summary card** (`#kolSummaryGrid`, tiles: 篩選素材數/花費金額/CPA/ROAS/CTR/CVR/CPM, recomputed live via `computeKolAggregate(getFilteredKolRows())`), and the table's heat-color min/max scaling. The grand/total row reads "Grand total" only when category=全部 AND no names are individually selected; otherwise "Filtered total". Empty-state and grand rows span 8 columns (not 7 — remember the added 原廠標記 column).
  - Design note for future changes: the category filter is deliberately a single-select segmented toggle, not three independent checkboxes, because the three categories are mutually exclusive/partitioning (a row is either KOL or not) — independent checkboxes would allow logically ambiguous states (e.g. all three checked, or none). If asked to add more categories later, keep this same segmented-toggle pattern rather than reverting to checkboxes.
- **`#kol-calc`** ("KOL 第二波授權金談判計算機") — the same calculator markup/CSS/JS that used to be embedded in the weekly report, just relocated here, **unchanged and still KOL-only** (it explicitly rejects lookups where `isKOL===false`). The Lifetime table above broadened to all creative; this calculator did not — don't extend it to 原廠 rows. Still driven by `const LIC_ROW_DATA = {...}` and the `initLicCalc()` IIFE.

**Every week, after finishing the main report, also refresh `all.html`:**
1. Recompute `kolLifetimeRows` — for each `NameRow` in Meta creative with spend: media rows are `goal not in ['-','CPC']` restricted to `AD_Channel=='Meta AD'`, license "ghost" rows are `goal=='-'` (also Meta-only), both over the full combined `ad_data` (historical cache + current Bridge, no window filter). Per row: `mediaCost/purchases/revenue/clicks/impressions` summed from media rows, `lic` summed from ghost rows, `cost=mediaCost+lic`, `roas=revenue/cost`, `mediaRoas=revenue/mediaCost`, `cpa=cost/purchases`, `ctr=clicks/impressions*100`, `cvr=purchases/clicks*100`, `cpm=mediaCost/impressions*1000`, `isKOL=mode(sub.isKOL)`, `tag=mode(sub.原廠標記.dropna())` (or `null` if none). Same formulas as the weekly `kolRows` table, just unwindowed and un-restricted to KOL.
2. Recompute `LIC_ROW_DATA` exactly as done for the calculator in prior weeks (same per-Row `B`/`C`/`activeDays`/`firstWave` methodology as before it moved) — KOL rows only.
3. Update the header's "最後更新：YYYY/MM/DD（W&lt;N&gt; 資料）" chip (`#lastUpdatedChip`) and the calculator hint's `<b id="calcAsofText">` date to the new week's end date.
4. `AD_IMG_DIR` in `all.html` is `'AD Images/'` (no `../` prefix) since this page lives at the project root, not inside a week subfolder — don't copy the `../AD Images/` path from the weekly report template by mistake.
5. **Apply the `NAME_ALIASES` merge before grouping by `NameRow`** (found + fixed 2026-08-23): one ad's raw `廣告名稱` in the source data has its entire naming string duplicated back-to-back with no separator (`...products_R:25A:原廠-Wakazo_B:輪播_..._R:25_Z:`), which the NameRow regex parses into a garbled `A:原廠-Wakazo-25A:原廠-Wakazo` — really the same ad as `A:原廠-Wakazo-25` (Row 25), just fragmented. Before grouping, do `ad['NameRow'] = ad['NameRow'].replace({'A:原廠-Wakazo-25A:原廠-Wakazo': 'A:原廠-Wakazo-25'})` (see `NAME_ALIASES` dict at the top of `compute_all_lifetime.py`). It's a historical-only glitch (dates 2026-01-01 to 2026-06-24, already fully in the past), so it never affects a single week's own report — only `all.html`'s all-time aggregation. Merged row count is 136 (68 KOL + 68 原廠) as of 2026-08-23, not 137 — don't be surprised if the count looks "off by one" against an earlier session's notes. If a similar duplicated-name glitch turns up for a different ad in the future, add it to the same `NAME_ALIASES` dict rather than special-casing it elsewhere.

Include `all.html` in the same push as the week's report (see Step 5's `git add` list above).

---

## Project structure (current, as of Week 33)

```
Hulken Weekly Report/
├── 2026W31/
│   ├── hulken_week31_report.html      (published; ~1.5MB legacy base64-image version)
│   └── Halken JP_Mastersheet.xlsx     (gitignored, not pushed)
├── 2026W32/
│   ├── hulken_week32_report.html      (published; lightweight relative-image version)
│   ├── Halken JP_Mastersheet.xlsx     (gitignored)
│   └── Hulken_Claude_Bridge.xlsx      (gitignored)
├── 2026W33/
│   ├── hulken_week33_report.html      (published; last week to embed #kol-calc — see Step 3 note)
│   └── Hulken_Claude_Bridge.xlsx      (gitignored)
├── all.html                             ← standalone page, published at /all (clean URL), refresh every week — see Step 6 (renamed from kol.html 2026-08-23; kol.html itself moved to _to_delete/, never published)
├── AD Images/                          ← pushed to GitHub, referenced by relative path from report HTML (and by all.html, bare path — see Step 6.4)
│   └── <Row>.jpg  (e.g. 100.jpg, 101.jpg, ...)
├── _cache/                             (gitignored — historical data cache)
│   ├── ad_data_historical_cache.pkl.gz
│   ├── ad_data_cache_meta.json
│   └── build_cache.py
├── _to_delete/                         (gitignored — staging area for files the user wants removed; device_bash on this bridge can't delete files directly, so anything to discard gets moved here for the user to delete themselves)
├── index.html                          ← static redirect, reads manifest.json, don't hand-edit weekly
├── manifest.json                       ← update this every week (see Step 4)
├── .gitignore                          (*.xlsx, _cache/, _to_delete/, .DS_Store, Mastersheet_Tab_Guide.md)
├── Mastersheet_Tab_Guide.md             (gitignored — internal data-reading instructions, read every week)
└── CLAUDE.md                           (this file)
```

> As of 2026-08-16: the two stray `Xnip*.jpg` screenshots in `AD Images/` (accidental saves) and the `HulkenJP - AD Report - Google 簡報.pdf` at project root (an old collaboration example, never meant to be pushed) have both been deleted by the user locally. If either resurfaces in a future `git status`/`git add`, don't push it — flag it to the user instead of assuming it's intentional.

---

## Report HTML structure reference

- CSS custom properties define the brand palette (`--brand`, `--brand-gold`, `--tan`, etc.) — reuse them, don't hardcode new colors.
- `.week-picker` / `.week-menu` / `.meta-chip` — the top-right week dropdown, driven entirely by the `WEEKS` array via `initWeekPicker()`.
- `.beta-badge` — small gold "BETA" pill, applied via `isBeta:true` on a `WEEKS` entry (both in the dropdown list and, for the current week, next to the static toggle-chip text).
- `.kpi-card.hero` — the ROAS tile gets special gold-gradient styling since ROAS is the headline metric across the whole report; keep that treatment when adding new weeks.
- Nav section IDs, W34 onward: `#overview`, `#channels`, `#meta-test`, `#meta-creative`, `#kol` (no more `#kol-calc` — see Step 3 note). W33's file still has all six; don't use it as the nav-ID reference for W34+.
- Image lightbox (`openLightbox`/`closeLightbox`) and thumbnail fallback (`onerror` → "缺圖" placeholder) already handle missing images gracefully — if an `AD Images/<Row>.jpg` is missing, the page still works, it just shows a placeholder.

### Standalone `/all` page

`all.html` (project root; renamed from `kol.html` 2026-08-23 — see Step 6) reuses the weekly report's full CSS block, its `fmtInt`/`fmt2`/`fmtPct1`/`money` helpers, thumbnail/lightbox functions, `sortRows`/`sortableHead`/`bindSortHandlers`/`heatBg`, and `tagBadge()` — kept compatible on purpose so the two pages look and behave similarly. It differs from the weekly report in: no week-picker (single simplified `#lastUpdatedChip` instead), a 2-item nav (`#kol-lifetime`, `#kol-calc`) plus a link back to the main report, `AD_IMG_DIR = 'AD Images/'` (bare, no `../`), no `deltaChip` (unused — lifetime table has no WoW deltas), and its own two-layer filter UI (`.cat-filter` segmented toggle + `.ms-filter` searchable multi-select) with a live-recomputing Summary card (`.summary-card`) that the weekly report doesn't have. Unlike the weekly report's `#kol` table, `tagBadge()` **is** used here since the Lifetime table spans all creative, not just KOL. See Step 6 for the weekly refresh checklist and the full column/filter spec.

---

## Hosting / Cloudflare setup (reference — shouldn't need to touch this weekly)

- **Cloudflare account:** "HulkenJP" account under `leo4help@gmail.com` login (kept separate from the user's other Cloudflare account for a different client — same isolation principle as the GitHub accounts).
- **Cloudflare Pages project:** `hulkenjp`, connected to `leo4help/hulkenjp` on branch `main`, auto-deploys on every push — no action needed after `git push`, just allow ~1-2 min for the new content to appear at `https://hulkenjp.pages.dev`.
- **Clean URLs:** Cloudflare Pages' default "clean URLs" setting serves `/all.html` for a request to `/all` (and would do the same for any other `<name>.html` at the project root) — this is why `all.html` needs no server config to appear at `https://hulkenjp.pages.dev/all`. If it ever stops resolving, check Pages project → Settings → Builds & deployments → "Build output" clean URL toggle before assuming something else broke.
- **Zero Trust team domain:** `lucky-sun-db7c.cloudflareaccess.com`, Free plan (50 seats).
- **Access Application:** protects `hulkenjp.pages.dev`, Policy "HulkenJP Only" → Allow, `Emails ending in @wakazocorp.com`, Session Duration 30 days.
- **Login method:** One-Time PIN (email code) — added under **Integrations → Identity providers** (this was surprisingly hard to find in Cloudflare's current nav; if it moves again, use the Quick Search (⌘K) in the Zero Trust dashboard rather than guessing the sidebar).
- If the user ever reports the login screen showing "Sign in with Cloudflare" instead of an email box, the One-Time PIN identity provider got removed or "Accept all available identity providers" got turned off on the Application — check **Access controls → Applications → hulkenjp.pages.dev → Login methods**.

---

## Open items / things to double check with the user (not urgent, don't act unilaterally)

- `_to_delete/` has three old files (`hulken_kol_license_calculator.html`, `hulken_week31_report_copy_for_edit.html`, `kol.html` — the last one moved here 2026-08-23 when it was superseded by `all.html`, never published) waiting for the user to manually delete from Finder (the device bridge cannot delete files on the user's machine).
- After the next successful push, confirm `https://hulkenjp.pages.dev/all` resolves correctly and `https://hulkenjp.pages.dev/kol` is gone (should now 404 or fall through, since `kol.html` is no longer in the repo) — first time this rename is going live.
