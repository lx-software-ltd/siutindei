# Plan: a family guide built on kinds and topics

**Status**: Approved. The owner answered the seven scoping questions and
five follow-up questions on 13 Nov 2026 (see "Decisions"), and
approved the four red slices the same day with one change
(decision 13).
**Zone**: mixed. Workstreams A and F are green (`apps/public_www/**`,
`docs/**`). Workstreams D and H are yellow. Workstream I is yellow
in the backend and green in the public site. Workstreams B, C, E, and
G each have a red slice (`backend/db/**` or `shared/**`) and are
yellow or green around it. Each red slice needs the owner's explicit
approval in chat before any write.

The evidence is in `docs/research/family-guide-kinds-and-topics.md`.
Read it first. It holds the code map this plan relies on.

## How to hand this plan to an agent

- One workstream is one session and one pull request. Start each
  session with: "Implement workstream X of
  `docs/plans/family-guide-kinds-and-topics.md`. Read the plan and the
  research memo first."
- Follow "Order of work". A later workstream assumes the earlier ones
  have merged.
- For a workstream with a red slice, the agent lists the red files in
  chat and waits. "Red slices that need approval" lists them all, so
  the owner can approve them in one message.
- Tests come first in every yellow slice. Each workstream names the
  tests to add and the commands that prove it.
- If the code no longer matches the memo's map, stop and say so. Do
  not patch around it.
- Revision numbers below are the next free ones today. Use the next
  free number at the time of writing the migration.

## Decisions

The owner's answers, 13 Nov 2026.

1. **Audience: both.** A parent who does not know what to do this
   weekend, and a parent planning the child's week or month.
2. **Rollout: Stanley, then the rest of the Southern District, then
   all of Hong Kong.** The taxonomy must work city-wide, so tutoring
   and exam preparation stay in.
3. **Money: later.** Once traffic is proven, providers may pay to be
   listed or bumped. Nothing is sold now. See "Non-goals" for the rule
   this plan records so that it stays possible later without breaking
   trust. The site itself says only that it is free (decision 9).
4. **Verification: the owner checks listings personally.**
5. **Ages: 0 to 18.**
6. **Nurseries and kindergartens: the owner asked for a
   recommendation.** Recommended and encoded here: keep them as their
   own short list with monthly or yearly fees, linked from the hub.
   They are never in default results, the wizard's topics, or the
   weekend view. Primary, secondary, and international schools are
   hidden.
7. **Faith-based children's groups: in.**

The owner's answers to the follow-up questions, also 13 Nov 2026.

8. **The gate for opening an area: confirmed.** An area is ready when
   at least 80% of its classes and camps are complete and at least
   50% of its organisers are parent-verified. Workstream H builds it.
9. **The site says it is free, and nothing more about money.** The
   about page says Siu Tin Dei is free. No public copy mentions paid
   placement, sponsorship, or paying for a position, now or as a
   future possibility. Workstream A applies this.
10. **An old check is flagged, and the badge stays.** A check older
    than 12 months raises a warning for the owner in the admin
    console. The public badge and its date do not change or drop.
11. **Members-only clubs: confirmed.** The club's own entry is hidden
    in a hidden category. A programme the club opens to non-members
    stays listed.
12. **The Flutter app: out of this plan.** The owner is not planning
    the app in the short term. See "Non-goals" for the one thing that
    still touches the app's folder.
13. **Schools and members-only clubs keep their own categories.** There
    is no "Not listed" root. Primary, secondary, and international
    schools keep their categories under a "Schools" root, and
    members-only clubs get a "Members-only clubs" root. Both roots are
    hidden from public search with a per-category flag,
    `hidden_from_public`. An organisation whose activities all sit in
    hidden categories is rejected with the existing reason
    `not_relevant`. The rejection records why; the hidden flag does
    the hiding, because the review gate (`ORG_REVIEW_GATE_ENABLED`) is
    off by default.

Also agreed, from the "push back" list the owner accepted:

- Cut schools and members-only clubs. Keep playgroups and
  school-run camps that are open to everyone.
- Restaurants appear only as checked family facts, as a pilot in
  Stanley, beside the classes and never as a headline category.
- More categories is not the fix. Checking is the scarce resource. A
  new area opens only when the open ones show real times and prices.
- The parent-checked badge and any future paid placement stay
  separate. This is a rule for whoever builds on the site. It is not
  public copy (decision 9).

## Mission and position

Use these words as the source for copy. Workstream A applies them.

- **Mission.** The complete, parent-checked guide to everything a
  family can do near home, one neighbourhood at a time.
- **Promise.** Every option we can find, the free and the tiny
  included. A parent checks listings in person and the checked ones
  say so, with the date. It is free to use and free to be listed.
- **Audience.** Parents of children aged 0 to 18 who live in the
  neighbourhood: planning the week and the term, or stuck for
  something to do this weekend.
- **Not.** A booking site, a school finder, a restaurant directory, a
  review site, or a city-wide list that is thin everywhere.

On money, public copy says the site is free and stops there
(decision 9).

## Goal

1. Every listing has a **kind** that decides what its card and page
   show, and class and camp listings also have a **topic**.
2. The wizard asks what the parent is looking for before it asks for
   a topic, and covers ages 0 to 18.
3. Camps and workshops can carry dates. Places show opening hours and
   facilities instead of class times and a class price.
4. Schools above kindergarten and members-only clubs leave the public
   catalogue without being deleted. They stay in categories named for
   what they are, and their organisations are rejected as not
   relevant (decision 13).
5. The site says only what is true: which listings a parent checked
   and when, and which areas are covered.
6. The owner can see, per area, whether the listings are good enough
   to open the next area.

## Non-goals

- Booking, payments, or accounts for parents.
- Paid listings, bumping, or sponsorship. Recorded rule for when that
  comes: a paid placement is labelled, sits in its own slot, and never
  changes the parent-checked badge, the kind, the topic, or the
  default order. Workstream A writes that rule into
  `docs/architecture/decisions.md`. It is a rule for builders. The
  site does not mention it (decision 9).
- The Flutter app (`apps/siutindei_app/**`). No Dart change, no new
  screen, and no parity work. The one exception is the copied asset
  `apps/siutindei_app/assets/home_wizard/home_wizard_choices.json`:
  the sync script writes it and CI's sync check compares it, so
  workstream E refreshes it. The app's parser reads keys by name and
  keeps working, because the new file keeps `searchAge` and only adds
  keys.
- Dropping or expiring the public badge after a period of time
  (decision 10).
- Opening a new area. `SEARCH_AREA_SCOPE` stays on Stanley until the
  gate in workstream H says otherwise.
- A restaurant directory, food ratings, or menus.
- Parties and venue hire. Likely a later kind.
- Parent reviews beyond what exists.
- New API Gateway routes. The API stack is at 494 of CloudFormation's
  500 resources. Every API change here extends an existing route.
- Removing the legacy category roots or the legacy fallback. See
  "Open questions".

## The model in one page

### Kinds

`activities.kind`, one value per activity. The word "kind" is internal.
Parents see the labels.

| Kind | Label | What it is | The card shows | Complete when |
| --- | --- | --- | --- | --- |
| `class` | Classes and clubs | Runs every week: a class, club, team, or playgroup | Ages, weekly times, price, free trial | A weekly time, a price, and an age range that is not a catch-all |
| `camp` | Camps and workshops | Has dates: a holiday camp, a course, a one-day workshop | Ages, dates, daily hours, price | A session that has not ended, and a price |
| `place` | Places to play | Somewhere to turn up: playground, beach, indoor play, library, pool | Place type, opening hours, cost, facilities | A map pin. Hours and cost are optional |
| `preschool` | Nurseries and kindergartens | Full-time or half-day care and schooling under 6 | Ages, fee per month or year | Not in default results |
| `eat` | Eat with kids | A place to eat that works with children. Pilot | Family facts, opening hours | Shown only when parent-checked |

Rules:

- The API returns every kind when the caller sends no `kind`, so
  existing callers keep working. The public site asks for
  `class,camp,place` by default.
- A catch-all age range is one with a lower bound of 0 and an upper
  bound of 18 or more. Clients do not print it. For a class or camp it
  is a data gap (workstream H).
- Price per class is a class fact. It is never computed or shown for
  the other kinds.

### Topics and fixed roots

The category tree keeps its table and gains new rows. A category under
a fixed root decides the kind. A category under a topic allows `class`
or `camp`.

Topics. Roots with `show_in_wizard = true`, no leaves to start with.
A topic gets leaves later only when one area has at least five
listings for a leaf.

| Id suffix | Wizard id | English | Chinese (zh-HK) |
| --- | --- | --- | --- |
| `…1301` | `baby-toddler` | Baby and toddler | 嬰幼兒及親子 |
| `…1302` | `sports` | Sports | 運動 |
| `…1303` | `water` | Swimming and water sports | 游泳及水上活動 |
| `…1304` | `art` | Art and making | 藝術及手作 |
| `…1305` | `performing` | Music, dance and drama | 音樂、舞蹈及戲劇 |
| `…1306` | `languages` | Languages | 語言 |
| `…1307` | `stem` | STEM and coding | STEM 及編程 |
| `…1308` | `tutoring` | Tutoring and exam preparation | 補習及應試 |
| `…1309` | `community` | Outdoors, scouts and community | 戶外、童軍及社區 |

Fixed roots. `show_in_wizard = false`. Protected the way Pending
categorisation is: no rename, re-parent, delete, or wizard flag.

| Id suffix | English | Chinese (zh-HK) | Effect |
| --- | --- | --- | --- |
| `…1401` | Places to play | 遊樂好去處 | kind `place` |
| `…1402` | Nurseries and kindergartens | 幼兒中心及幼稚園 | kind `preschool` |
| `…1403` | Eat with kids | 親子餐廳 | kind `eat` |
| `…1404` | Schools | 學校 | hidden from public search |
| `…1405` | Members-only clubs | 會員制會所 | hidden from public search |

Leaves under the fixed roots:

| Id suffix | Parent | English | Chinese (zh-HK) |
| --- | --- | --- | --- |
| `…1411` | Places to play | Playground and park | 遊樂場及公園 |
| `…1412` | Places to play | Beach and countryside | 沙灘及郊野 |
| `…1413` | Places to play | Indoor play | 室內遊樂場 |
| `…1414` | Places to play | Pool, pitch and court | 泳池及運動場地 |
| `…1415` | Places to play | Library | 圖書館 |
| `…1416` | Places to play | Museum and heritage | 博物館及古蹟 |
| `…1421` | Nurseries and kindergartens | Nursery and childcare | 幼兒中心及託兒 |
| `…1422` | Nurseries and kindergartens | Kindergarten | 幼稚園 |
| `…1213` | Schools | Primary school (existing row, re-parented) | 小學 |
| `…1214` | Schools | Secondary school (existing row, re-parented) | 中學 |
| `…1215` | Schools | International and prep schools (existing row, re-parented) | 國際及預備學校 |

Every id is `c1111111-1111-1111-1111-11111111NNNN` with the suffix
shown. "Eat with kids" and "Members-only clubs" have no leaves.

Hidden categories. `activity_categories.hidden_from_public` is a new
boolean, default false, set true on `…1404` and `…1405`. Public search
leaves out an activity whose category or any ancestor is hidden. An
admin can set it on any category except Pending, which public search
already leaves out. An activity in a hidden category raises no review
blocker. Faith-based groups, scouts, and
community-centre programmes sit under `community`. The Chinese names
need a native check before they ship (see "Open questions").

### Old rows to new rows

Workstream C moves every reference from an old row to a new one with
this table, then deletes the old rows. The recheck then refines.

| Old id suffix | Old name | New id suffix |
| --- | --- | --- |
| `…1201` | Early years and schools (group) | `…1422` |
| `…1202` | Learning and tutoring (group) | `…1308` |
| `…1203` | Arts and performance (group) | `…1305` |
| `…1204` | Sports and movement (group) | `…1302` |
| `…1205` | Play and outdoors (group) | `…1411` |
| `…1206` | Culture (group) | `…1416` |
| `…1207` | Community and support (group) | `…1309` |
| `…1211` | Kindergarten and nursery | `…1422` |
| `…1212` | Day crèche and childcare | `…1421` |
| `…1213` | Primary school | kept, moved under `…1404` |
| `…1214` | Secondary school | kept, moved under `…1404` |
| `…1215` | International and prep schools | kept, moved under `…1404` |
| `…1221` | Tutoring centre | `…1308` |
| `…1222` | Language classes | `…1306` |
| `…1223` | STEM and coding | `…1307` |
| `…1224` | Parent and family education | `…1309` |
| `…1231` | Music lessons | `…1305` |
| `…1232` | Dance and ballet | `…1305` |
| `…1233` | Visual arts | `…1304` |
| `…1234` | Drama | `…1305` |
| `…1241` | Sports centre | `…1414` |
| `…1242` | Swimming pool | `…1414` |
| `…1243` | Sports grounds and courts | `…1414` |
| `…1244` | Martial arts and boxing | `…1302` |
| `…1245` | Cycling | `…1302` |
| `…1251` | Playground and park | `…1411` |
| `…1252` | Indoor playhouse | `…1413` |
| `…1253` | Beach and countryside | `…1412` |
| `…1261` | Public library | `…1415` |
| `…1262` | Museum and exhibition | `…1416` |
| `…1263` | Heritage and performing-arts venue | `…1416` |
| `…1271` | Community centre | `…1309` |
| `…1272` | Special needs support | `…1309` |

The five legacy roots (Workshop, Class, Outdoor activity, Indoor fun,
Sport) and Pending categorisation are not touched.

### Facts

`activities.facts` is a JSON object of booleans. `true` means a parent
saw it. `false` means a parent saw that it is missing. An absent key
means nobody checked. Keys allowed per kind, version 1:

| Kind | Keys |
| --- | --- |
| `place` | `toilets`, `changing_table`, `shade`, `fenced`, `stroller_access`, `water_play`, `lifeguard`, `parking`, `food_nearby` |
| `eat` | `high_chairs`, `kids_menu`, `changing_table`, `stroller_access`, `room_to_run`, `outdoor_seating` |
| `class`, `camp` | `drop_in`, `parent_stays`, `sen_friendly`, `lunch_included` (`camp` only) |
| `preschool` | none |

Only an admin writes `kind`, `facts`, and the verified fields. Manager
payloads have them stripped, the way `parent_verified` is stripped in
`backend/src/app/api/admin_resource_organization.py` today.

## Order of work

| Step | Workstream | Zone | Depends on | Parents see |
| --- | --- | --- | --- | --- |
| 1 | A. Honest words | green | nothing | Copy that matches the data |
| 2 | B. Kind, facts, and the checked date | red + yellow | approval | Nothing yet |
| 3 | C. Topics, fixed roots, and the school cut | red + yellow | B | Schools gone |
| 4 | D. Search API | yellow | B, C | Nothing yet |
| 5 | E. Wizard and age groups | red + green + yellow | C, D | New first question, ages 0 to 18 |
| 6 | F. Cards and pages by kind | green | D | The right facts on each card |
| 7 | H. Checks and the area gate | yellow | B, C | Nothing. The owner sees what to fix |
| 8 | G. Dates for camps and workshops | red + yellow + green | B, D, F | Camps with dates |
| 9 | I. Eat with kids pilot | yellow + green | B, D, F | A food layer on the Stanley map |

H touches different files from E and F and can run beside them.

## Red slices that need approval

| Workstream | Path | Change |
| --- | --- | --- |
| B | `backend/db/alembic/versions/0065_activity_kind_facts.py` | Add `activities.kind`, `activities.facts`, `organizations.parent_verified_at`. Backfill `kind` |
| C | `backend/db/alembic/versions/0066_family_guide_taxonomy.py` | Add `activity_categories.hidden_from_public`, insert topics and fixed roots, re-parent the three school leaves, move references, delete the other old groups and leaves, reject school-only organisations, add import aliases |
| E | `shared/home_wizard/home_wizard_choices.json` | Version 3: `kinds`, nine topics, five age groups |
| G | `backend/db/alembic/versions/0067_schedule_dates.py` | Add `activity_schedule.starts_on` and `ends_on`, replace the schedule unique constraint |

No change to `backend/infrastructure/**`, deploy workflows, or
`scripts/deploy/**`. `SEARCH_AREA_SCOPE` is a GitHub variable the
owner changes by hand.

## Workstream A: honest words

Green. `apps/public_www` and `docs/architecture/decisions.md`. Ship it
first. It needs nothing else.

1. **Remove the claim that every listing is checked.** It is in
   `smallWorld.subtitle` and `seo.activities.descriptionTemplate` in
   `apps/public_www/src/content/en.json` and `zh-HK.json`. Search both
   files for other copies.
2. **Stop implying Hong Kong-wide coverage.** `hero.subtitle`,
   `seo.fallbackDescription`, `seo.search.description`, and
   `discovery.pageTitle` name Hong Kong with no area. Name the open
   area, or say "starting in Stanley".
3. **Say what the badge means.** Keep the label "Parent-Verified"
   (家長認證). Add an explainer string next to it on the activity page
   and on the about page: a Siu Tin Dei parent visited or spoke to
   this organiser and confirmed the details. The date is added in
   workstream F.
4. **About page.** In `pages.about`, change the summary to "classes,
   camps, and places to play", and add two sections:
   - "How listings are checked": most listings start from public
     sources, a parent then checks them one organiser at a time, and
     the checked ones carry the badge.
   - "Free for families and organisers": Siu Tin Dei is free to use
     and free to be listed on. Say that and stop. No sentence about
     paid placement, sponsorship, or paying for a position, as a
     present fact or a future one (decision 9).
5. **Record the mission and the paid-placement rule** in
   `docs/architecture/decisions.md` under a new heading, using
   "Mission and position" and the rule under "Non-goals". That file
   is for builders. None of it goes into the locale files.

Proposed copy. Edit freely. Keep both languages in step.

| Key | English | Chinese (zh-HK) |
| --- | --- | --- |
| `hero.subtitle` | Children's activities near home, starting in Stanley. | 住家附近的兒童活動，由赤柱開始。 |
| `smallWorld.subtitle` | Siu Tin Dei lists every class, camp, and place to play we can find near you, the free and the tiny included. A local parent checks them one by one, and the checked ones carry a badge. | 小天地整理你家附近找得到的每一個課程、營會及遊樂好去處，免費的、小型的都不遺漏。本地家長逐一查證，查證過的會有標記。 |
| `seo.activities.descriptionTemplate` | Classes, camps, and places to play for children in {placeFull}, with ages, times, prices, and organiser contacts. Listings a local parent has checked carry a badge. | 小天地 Siu Tin Dei 整理{placeFull}的兒童課程、營會及遊樂好去處，列出適合年齡、時間、收費及主辦機構聯絡方法。經本地家長查證的活動會有標記。 |
| new `activityDetail.parentVerifiedExplainer` | A Siu Tin Dei parent visited or spoke to this organiser and confirmed the details. | 小天地的家長曾到訪或聯絡這間機構，並確認了資料。 |
| new `pages.about.sections` entry, heading | Free for families and organisers | 家長和機構都免費 |
| new `pages.about.sections` entry, paragraph | Siu Tin Dei is free to use, and listing a class, camp, or place to play is free. | 小天地免費使用，刊登課程、營會或遊樂好去處亦不收費。 |

Tests first: add a content test under `apps/public_www/tests` that
fails while either locale file contains "checked by local parents
before" or "上架前都經本地家長審核", that fails if either locale
file contains "paid placement", "sponsor", "贊助", or "付費" (none
is present today), and that asserts both locales define the same
keys for the strings above.

Done when: `npm run lint`, `npm run typecheck`, and `npm test` pass in
`apps/public_www`, and the home, about, and hub pages read correctly
in both languages in a browser at port 3100.

## Workstream B: kind, facts, and the checked date

Red migration, then yellow backend and admin web.

### B1. Migration `0065_activity_kind_facts` (red)

- `activities.kind`: `TEXT NOT NULL DEFAULT 'class'`, with CHECK
  `activities_kind_check` allowing `class`, `camp`, `place`,
  `preschool`, `eat`. Text with a CHECK, not a PostgreSQL enum, so a
  later kind is one constraint change. Add an index on `kind`.
- `activities.facts`: `JSONB NOT NULL DEFAULT '{}'`, with CHECK
  `jsonb_typeof(facts) = 'object'`.
- `organizations.parent_verified_at`: `TIMESTAMPTZ NULL`, with CHECK
  that it is null unless `parent_verified` is true. Leave it null for
  organisations already verified. The real date is not known, and a
  made-up one would be a false claim.
- Backfill `kind` from the current leaves: `place` for categories
  `…1205`, `…1206`, `…1241` to `…1243`, `…1251` to `…1253`, and
  `…1261` to `…1263`; `preschool` for `…1211` and `…1212`. Then, among
  the rest, `camp` where the name matches
  `\m(camps?|workshops?|holiday course)\M` (case-insensitive) or
  contains 夏令營, 冬令營, 日營, 工作坊, or 暑期班. Everything else
  stays `class`.
- Downgrade drops the three columns.
- Seed assessment: defaults cover the existing rows in
  `backend/db/seed/seed_data.sql`. State that in the revision
  docstring and the pull request.
- Update `docs/architecture/database-schema.md`.

### B2. Backend (yellow)

Tests first: `tests/test_listing_kinds.py` (new),
`tests/test_org_listing_status.py`, and the admin activity and
organisation resource tests.

- Models: `kind` and `facts` on `Activity`
  (`backend/src/app/db/models/activity.py`), `parent_verified_at` on
  `Organization` (`backend/src/app/db/models/organization.py`).
- New `backend/src/app/services/listing_kinds.py`: the kind values,
  the fact keys per kind, `validate_facts(kind, facts)` (unknown key
  or non-boolean value is a validation error), and `guess_kind(name)`
  with the same patterns as the backfill.
- `backend/src/app/api/admin_resource_activity.py`: accept and return
  `kind` and `facts`. Admin only. Changing `kind` drops fact keys the
  new kind does not allow.
- `backend/src/app/api/admin_resource_organization.py`: return
  `parent_verified_at`. Setting `parent_verified` to true stamps it
  with the server time unless the admin sends a date, which may not
  be in the future. Setting it to false clears it. Sending
  `parent_verified: true` again with a date is how a re-check is
  recorded.
- Catalog versions must carry the new fields, or a restore loses
  them: `backend/src/app/services/catalog_version_payload.py`,
  `catalog_version_shape.py`, and `catalog_version_match.py`, plus
  `apps/admin_web/src/components/admin/catalog-version-snapshot.ts`.
- Imports: add `kind` and `facts` to `ALLOWED_ACTIVITY_FIELDS` in
  `backend/src/app/api/admin_imports_allowed.py`. When a file sends no
  `kind`, use `guess_kind`. Check the three-way merge in
  `backend/src/app/services/import_merge.py` keeps an admin's edit to
  `kind` and `facts`.
- `docs/api/admin.yaml` and `docs/api/partner.yaml`: add the fields.
  Run `npm run generate:api` in `apps/admin_web`.

### B3. Admin web (yellow)

- `apps/admin_web/src/components/shared/activities-panel.tsx`: a
  "Listing kind" select and a "Checked facts" group of three-state
  toggles (yes, no, not checked) for the keys of the chosen kind.
  Follow the `admin-crud-screen` skill.
- `apps/admin_web/src/components/shared/organizations-panel.tsx` and
  `organizations/organization-form-utils.tsx`: show "Checked on" next
  to the verified toggle, with a "Checked today" action.
- Update `apps/admin_web/e2e` mocks to match the OpenAPI change.

Done when: `pytest tests/test_alembic_revision_contract.py
tests/test_listing_kinds.py` and the touched resource tests pass;
`alembic upgrade head` then the seed file run clean on the local
database; `python3 scripts/check_openapi_routes.py` passes;
`npm run lint` and `npm run typecheck` pass in `apps/admin_web`; an
admin can set a kind, a fact, and a checked date in the browser and
see them after reload.

## Workstream C: topics, fixed roots, and the school cut

Red migration, yellow backend, then a recheck the owner runs.

### C1. Migration `0066_family_guide_taxonomy` (red)

One column and data. In one transaction:

1. Add `activity_categories.hidden_from_public BOOLEAN NOT NULL
   DEFAULT false`.
2. Insert the nine topics, the five fixed roots, and their leaves from
   "Topics and fixed roots", with the same helper shape and
   translation keys as `0040_recheck_taxonomy.py`. Set
   `hidden_from_public` on Schools and Members-only clubs. Re-parent
   `…1213`, `…1214`, and `…1215` under Schools.
3. For every other pair in "Old rows to new rows", move the references:
   `activities.category_id`;
   `category_suggestions.suggested_parent_id`, `maps_to_category_id`,
   `created_category_id`, and `merged_into_category_id`;
   `activity_category_reviews.current_category_id`,
   `proposed_category_id`, and `previous_category_id`. Those review
   and suggestion columns are `ON DELETE SET NULL`, so skipping this
   step silently erases import aliases and review history.
4. Set `kind` from the new position: `place` under `…1401`,
   `preschool` under `…1402`, `eat` under `…1403`. An activity under a
   topic whose kind is `place`, `preschool`, or `eat` becomes `class`.
5. Clear `show_in_wizard` on the seven old groups, then delete the 23
   other old leaves and the seven old groups.
6. Reject every organisation that is not already rejected, has at
   least one activity, and has all its activities in hidden
   categories: `review_status = 'rejected'`, `review_reason =
   'not_relevant'`, `reviewed_by = 'migration:0066'`.
7. Add an import alias for each old name that no longer exists as a
   category name, so a file that still sends "Tutoring centre"
   resolves. An alias is a `category_suggestions` row whose
   fingerprint is the normalised old name and whose
   `merged_into_category_id` is the new row. See `_alias_category_id`
   in `backend/src/app/services/category_suggestions/resolve.py`.
   Skip a name that already has a suggestion row.

Downgrade re-creates the `0040` rows and moves references back, moves
the school leaves back under their old group, and drops the column.
It is lossy where several old leaves merged into one new row: they all
return to the first old leaf in the table. It does not undo the
rejections. Say both in the docstring.
Seed assessment: the seed only inserts the legacy root Sport, so no
seed change.

Before running against production, the owner takes a database
snapshot. See "Rollback".

### C2. Backend (yellow)

Tests first: extend `tests/test_search_category_filter.py`,
`tests/test_category_recheck_followups.py`,
`tests/test_partner_activity_categories.py`,
`tests/test_activity_category_names.py`, and `tests/test_admin_imports.py`.

- `backend/src/app/db/models/category_suggestion.py`: set
  `WIZARD_GROUP_IDS` to the nine topic ids. Add constants for the five
  fixed roots and a `SYSTEM_CATEGORY_IDS` set (Pending plus the five).
  Add `hidden_from_public` to the `ActivityCategory` model.
  The legacy fallback in `backend/src/app/db/queries.py` keeps working
  with the nine ids. A topic that starts empty (Baby and toddler,
  Swimming and water sports) falls back to the legacy roots until the
  recheck assigns something to it, so run the recheck straight after
  the deploy.
- Protect the fixed roots wherever Pending is protected:
  `backend/src/app/api/admin_resource_activity_category.py`
  (`is_system`, rename, re-parent, wizard flag),
  `backend/src/app/db/repositories/activity_category.py` (delete), and
  `backend/src/app/api/partner_activity_categories.py`. Children of a
  fixed root can still be added, renamed, and deleted.
- Public search hides hidden categories: in `build_search_query`
  (`backend/src/app/db/queries.py`) and in
  `backend/src/app/db/incomplete_search.py`, exclude an activity whose
  category or any ancestor has `hidden_from_public`, next to the
  Pending exclusion. `count_search_activities` in
  `backend/src/app/api/search_page.py` must agree. Partner search
  follows the same rule as public search.
- The admin category resource and the partner category routes return
  `hidden_from_public`; only an admin can change it, and not on
  Pending. Update `docs/api/admin.yaml` and `docs/api/partner.yaml`.
- Kind follows the category. Add `kind_for_category(session,
  category_id, current_kind)` to `listing_kinds.py` and call it
  wherever a category is assigned. In the same places, call
  `reject_if_only_hidden(session, organization_id)`: when the
  organisation has activities, all of them in hidden categories, and
  it is not already rejected, set it rejected with `not_relevant` and
  `reviewed_by = 'system:category'`. Moving an activity back out of a
  hidden category does not undo a rejection. The places are: the
  admin activity resource, import
  upsert, the category-review apply path
  (`backend/src/app/services/category_suggestions/scan_apply.py`,
  `decisions.py`, `reviews.py`), and enrichment apply
  (`backend/src/app/services/enrichment/apply_rows.py`).
- Category model prompts
  (`backend/src/app/services/category_suggestions/prompt.py`): add to
  the recheck note that schools above kindergarten go to the matching
  school leaf, members-only clubs to "Members-only clubs", a
  programme a club opens to non-members goes to its topic, a venue
  anyone can walk into goes under "Places to play", and a class
  taught at a venue goes to its topic. Keep the redaction as is.
- Organisation review: an activity in a hidden category raises no
  blocker. An organisation whose activities are all hidden gets the
  warning `no_listable_activities`, for one that an admin approved
  again by hand. Change both
  `backend/src/app/services/org_review.py` and the SQL mirror in
  `backend/src/app/services/org_review_sql.py`.
- Docs: `docs/architecture/category-suggestions.md` and
  `docs/architecture/database-schema.md`.

### C3. Admin web (yellow)

`apps/admin_web/src/components/shared/activity-categories-panel.tsx`
and `apps/admin_web/src/components/ui/cascading-category-select.tsx`:
show the fixed roots as system rows, a "Hidden from public" toggle
and marker on each category, and the kind a category implies when one
is picked for an activity.

### C4. Owner steps after deploy

Not code. The plan is not done without them.

1. Run a category check with `ignore_current_category` over all
   organisations (Data quality, Categories). Review what does not
   auto-apply.
2. Check the organisations the migration and the recheck rejected as
   not relevant. Keep an organisation that also runs a camp,
   playgroup, or class open to everyone, including a club that takes
   non-members for it: it is not rejected, and only its school or
   club entry sits in a hidden category (decisions 11 and 13).
3. For Stanley, open each class and camp and fix the kind, the ages,
   the real class times, and the price. Workstream H lists them.

Done when: the migration contract test and the tests above pass; on a
database with the `0040` rows and sample activities, upgrade then
downgrade then upgrade leaves every activity on a valid category; a
search for a topic returns its activities and never one under "Not
listed"; importing a file that sends an old label resolves it.

## Workstream D: search API

Yellow. `docs/api/search.yaml` is the contract; update it in the same
pull request. Every change is additive. Follow the
`admin-api-endpoint` skill for the documentation steps. No new route.

Tests first: `tests/test_search_validation.py`,
`tests/test_search_queries.py`, `tests/test_search_handler.py`,
`tests/test_search_public_details.py`, `tests/test_search_incomplete.py`,
`tests/test_catalogue_snapshot.py`, `tests/test_staging_search_store.py`.

New query parameters on `/v1/activities/search`:

- `kind`: comma-separated kinds. Absent means all kinds.
- `age_min` and `age_max`: integers. The filter is range overlap with
  `activities.age_range`, so a class for ages 6 to 8 matches the
  6 to 11 group. Sending `age` together with either is a validation
  error. `age` alone keeps its meaning.
- `verified`: `true` limits results to parent-verified organisations.

New response fields:

- `activity.kind`, `activity.facts` (full view only),
  `activity.category_root_id`, `activity.category_name`, and
  `activity.category_name_translations`. Load the category table once
  per request. Do not query per row.
- `organization.parent_verified_at`.

Files: `backend/src/app/api/search.py` (`parse_filters`),
`backend/src/app/api/search_validation.py`,
`backend/src/app/db/queries.py` (`ActivitySearchFilters`,
`build_search_query`), `backend/src/app/db/incomplete_search.py`,
`backend/src/app/api/search_page.py` (`map_row_to_result`, counts),
`backend/src/app/api/schemas.py` (schemas and card-view trimming),
`backend/src/app/services/staging_search_store.py`,
`backend/src/app/services/staging_search_matching.py`, and
`scripts/codegen/generate_activity_search_staging.py` (emit kinds and
topic ids so the staging fixture exercises them).

One rule changes: a `place` with no weekly entry or no price row is
not "incomplete" in the sense parents care about. It still arrives
through the incomplete phase of `load_search_rows`; clients stop
labelling it as missing details (workstream F). Do not rewrite the
join in this workstream.

The catalogue snapshot (`backend/src/app/services/catalogue_snapshot.py`)
picks the new fields up through the search response. Keep
`SNAPSHOT_SCHEMA_VERSION` at 1, because the fields are additive.
Deploy the backend before the public site build that reads them.

Done when: the tests above pass; `python3
scripts/check_openapi_routes.py` passes; a request with no new
parameter returns the same items as before plus the new fields.

## Workstream E: wizard and age groups

Red for `shared/home_wizard/home_wizard_choices.json`, green for the
public site, yellow for the generator and the copied Flutter asset.
No Dart file changes (decision 12).

### E1. Choices file, version 3 (red)

- `kinds`: a new array kept by hand, the way `ageGroups` is. Entries:
  `class`, `camp`, `place`, and `eat`. Each has `id`, `labels`, a
  short `hint`, `hasTopics` (true for `class` and `camp`), and
  `pilot` (true for `eat`). Clients do not offer a pilot kind until
  workstream I turns it on, so `eat` can sit in the file from the
  start and `shared/**` needs one approval, not two.
- `activityTypes`: the nine topics, with the wizard ids from "Topics
  and fixed roots". Set the ids by hand in this change. The generator
  keeps an id once a `categoryId` has one.
- `ageGroups`: five groups. `searchAge` stays for old clients.

| Id | `minAge` | `maxAge` | `searchAge` | English | Chinese |
| --- | --- | --- | --- | --- | --- |
| `0-1` | 0 | 0 | 0 | Under 1 | 1歲以下 |
| `1-2` | 1 | 2 | 2 | 1–2 years | 1–2歲 |
| `3-5` | 3 | 5 | 4 | 3–5 years | 3–5歲 |
| `6-11` | 6 | 11 | 8 | 6–11 years | 6–11歲 |
| `12-18` | 12 | 18 | 14 | 12–18 years | 12–18歲 |

Kind labels:

| Id | English | Hint | Chinese | Hint |
| --- | --- | --- | --- | --- |
| `class` | A class or club | Every week | 興趣班或課程 | 每星期上課 |
| `camp` | A camp or workshop | School holidays and one-off days | 營會或工作坊 | 假期及單次活動 |
| `place` | Somewhere to go today | Playgrounds, beaches, indoor play | 今日去邊度玩 | 遊樂場、沙灘、室內遊樂場 |
| `eat` | Somewhere to eat with kids | Checked by a parent | 親子餐廳 | 家長親身試過 |

- `scripts/codegen/generate_home_wizard_choices.py`: copy `kinds`
  through like `ageGroups`. Extend `tests/test_home_wizard_choices.py`.
- Run `bash scripts/codegen/sync-home-wizard-choices.sh`, then
  `--check`. The script also copies the file into
  `apps/siutindei_app/assets/home_wizard/`. Commit that copy, or the
  check fails in CI. Leave the app's code and tests alone:
  `HomeWizardChoices.fromJson` ignores keys it does not read, and its
  test parses its own inline JSON. If `flutter test` fails in CI
  after the copy, stop and say so instead of changing the app.

### E2. Public site (green)

Tests first: `apps/public_www/tests` for `search-params`, the
navigator, and `active-filters`.

- `src/lib/home-wizard/choices.ts`: types for `kinds`.
- `src/lib/activities/search-params.ts`: add `kind` to
  `SearchFiltersState`, the `kind` query parameter, and send
  `age_min` and `age_max` from the chosen group instead of
  `searchAge`. Default kinds when none is chosen: `class,camp,place`.
  Old age ids (`1-3`, `3-6`, `6-12`) and old topic ids in a URL are
  ignored without an error. Production has never served them.
- `src/lib/activities/search-client.ts` and
  `src/lib/activities/search/use-activity-search.ts`: pass the new
  parameters.
- `src/components/sections/hero/search-navigator.tsx`: step order is
  area, neighbourhood, **what are you looking for**, age, topic. The
  topic step shows only when the kind has topics. The first question
  also offers "What's on this weekend", which is a preset and not a
  kind: kinds `class,camp,place` with the existing `day=weekend`
  filter. Check how the incomplete phase of search treats a day
  filter: a place with no stored hours must still appear in this
  preset. Copy for the new step goes in `smallWorld.navigator.steps`
  in both locale files.
- `src/components/sections/search/search-panel.tsx`,
  `search-bar-compact.tsx`, `filter-chip-row.tsx`, and
  `src/lib/activities/active-filters.ts`: a kind control on the
  results page. Price-per-class and free-trial filters show only for
  `class`.
- `src/lib/home-wizard/choice-icons.ts`: map the nine topic ids and
  five age ids to existing art first (`early-years.svg` for
  `baby-toddler`, `learning.svg` for `languages`, `tutoring`, and
  `stem`, `arts.svg` for `art` and `performing`, `play.svg` for
  `water`, `community.svg` for `community`; `baby.png`, `toddler.png`,
  and `child.png` for the ages). New art is a follow-up.

Done when: `pytest tests/test_home_wizard_choices.py` passes; the sync
check passes; `npm run lint`, `npm run typecheck`, and `npm test` pass
in `apps/public_www`; in a browser, each first-question choice leads
to results of that kind, the weekend preset shows weekend listings,
and "Under 1" and "12–18 years" return listings whose age range
overlaps.

## Workstream F: cards and pages by kind

Green. `apps/public_www`. Follow the `public-www-section` skill; the
site stays a static export.

Tests first: `apps/public_www/tests` for `listing-facts`,
`price-format`, `landing-page-data`, `catalogue-snapshot`, the listing
card, the activity detail page, and `llms-txt`.

1. **Types and mapping.** `src/lib/activities/types.ts` and
   `map-listing.ts`: `kind`, `facts`, `categoryRootId`,
   `categoryName`, `categoryNameTranslations`, `parentVerifiedAt`. A
   listing with no `kind` (an old snapshot) is a `class`.
2. **Topic lookup.** Compare the wizard topic with `categoryRootId`,
   falling back to `categoryId`, in `catalogueCategories()` and
   `landingTypeIdForListing()` (`catalogue-snapshot.ts`),
   `categoryLabelForListing()` and `categoryTypeIdForListing()`
   (`listing-facts.ts`), and `activityTypeIdForCategory()`
   (`src/lib/home-wizard/choice-icons.ts`). Today they match only an
   activity assigned to the group itself, which is why staging has no
   type pages. For a `place`, the chip is the category name from the
   API.
3. **Card** (`src/components/sections/listings/listing-card.tsx`):
   - `class`: age chip, topic chip, weekly times, price, free trial.
   - `camp`: age chip, topic chip, price. Dates arrive with G.
   - `place`: place-type chip, "Open" line from the weekly entries
     (they are opening hours for this kind), cost. No age chip. No
     "Details on request" line when hours or cost are absent.
   - `preschool`: age chip, fee per month or year.
   - Never print a catch-all age range, for any kind.
4. **Activity page.** `src/lib/activities/detail-view.ts`,
   `activity-page-data.ts`, and the sections under
   `src/components/sections/activity-detail/`: per-kind key facts
   ("Opening hours" instead of "When" for a place, and no "Ask for
   times" prompt for a place), a "Good to know" list from `facts`, and
   the badge with "Checked {month year}" from `parentVerifiedAt`. With
   no date, show the badge alone. Check `src/lib/seo.ts` and the
   structured data so a place is not described as a course.
5. **Prices.** `src/lib/activities/price-format.ts`:
   `classPriceEquivalent` returns null unless the listing is a
   `class`.
6. **Hub and landing pages.** `landing-page-data.ts`,
   `catalogue-snapshot.ts`,
   `src/app/[locale]/activities/[category]/page.tsx`, and
   `src/components/pages/activities-landing-page.tsx`:
   - The hub groups listings under "Classes and clubs", "Camps and
     workshops", and "Places to play", then links to "Nurseries and
     kindergartens".
   - The `[category]` segment serves a kind page (`classes`, `camps`,
     `places`, `nurseries`) or a topic page (the wizard id). A topic
     page lists `class` and `camp` listings of that topic. The
     three-listing minimum stays.
   - "At a glance" is computed over `class` listings only and skips
     catch-all ages, so it can no longer read "0 to 100 years" or
     quote a kindergarten fee as a class price.
   - A coverage line from the snapshot: how many listings, how many
     checked by a parent, and the newest update.
   - Rewrite `activitiesPage.*` and `seo.activityCategory.*` templates
     in both locales so they do not promise "weekly times" for places.
7. **Search results** (`src/components/pages/search-results-page.tsx`,
   `src/components/sections/search/search-map-list-item.tsx`): the
   same per-kind lines as the card.
8. **`llms.txt` and sitemap** (`src/lib/llms-txt.ts`,
   `src/app/sitemap.ts`): list the kind and topic pages.
9. **Docs.** Describe kinds, topic pages, and the per-kind card in
   `docs/architecture/public-www.md`.

Done when: `npm run lint`, `npm run typecheck`, `npm test`, and the
build-output check (`seo:validate`) pass in `apps/public_www`; in a
browser against the staging fixture, a class, a place, and a
kindergarten each show their own facts on the card and the page, in
both languages; the hub's "At a glance" block shows believable ranges.

## Workstream H: checks and the area gate

Yellow. No new route.

Tests first: `tests/test_org_review.py`, one case for each rule below,
asserting that the Python rules in
`backend/src/app/services/org_review.py` and the SQL mirror in
`backend/src/app/services/org_review_sql.py` agree.

1. **Blockers by kind.**

   | Issue | `class` | `camp` | `place`, `eat` | `preschool` |
   | --- | --- | --- | --- | --- |
   | `missing_pricing` | blocker | blocker | not raised | warning |
   | `missing_schedule` | blocker | blocker | not raised | not raised |

2. **New warnings.** Thresholds are named constants.
   - `catch_all_age`: a class or camp whose range starts at 0 and ends
     at 18 or more.
   - `hours_as_class_times`: a class with entries on six or more days,
     each six hours or longer. Those are opening hours.
   - `class_price_outlier`: a `per_class` or `per_hour` amount above
     HK$1,500. That is usually a term fee.
   - `verification_stale`: `parent_verified_at` older than 365 days,
     or verified with no date. It is a prompt for the owner to check
     again. It never hides the public badge or the listing
     (decision 10).
   - `camp_without_dates`: added by workstream G.
3. **Area readiness.** `/v1/admin/org-review/summary` takes no
   parameter today (`_handle_summary` in
   `backend/src/app/api/admin_org_review.py`). Add an optional
   `area_id` query parameter, validated with the queue's
   `_require_active_area`. When it is sent, the response gains a
   `readiness` block: listings per kind, classes and camps that are
   complete (the "Complete when" column in "Kinds"), organisers that
   are parent-verified, and the two shares. Without it the response is
   unchanged. The gate, confirmed by the owner (decision 8): an area
   is ready when at least 80% of its classes and camps are complete
   and at least 50% of its organisers are verified. Keep the two
   numbers as named constants and return a `ready` boolean beside the
   shares. Update `docs/api/admin.yaml`.
4. **Admin web.** A "Ready to open?" card on Catalog
   (`apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`)
   showing the shares for the chosen neighbourhood, and the new issue
   codes in the queue's issue filter. Update `apps/admin_web/e2e`.
5. **Docs.** `docs/architecture/data-quality.md` gains "Area
   readiness" and the steps to widen `SEARCH_AREA_SCOPE`: the open
   areas still pass the gate, the new area passes it, then the owner
   changes the variable.

Done when: the review tests pass; `python3
scripts/check_openapi_routes.py` passes; `npm run lint` and
`npm run typecheck` pass in `apps/admin_web`; the card shows Stanley's
shares in the browser.

## Workstream G: dates for camps and workshops

Red migration, yellow backend and admin, green public site.

### G1. Migration `0067_schedule_dates` (red)

- `activity_schedule.starts_on` and `ends_on`: `DATE NULL`. They are
  Hong Kong calendar dates. CHECK: both null or both set, and
  `ends_on >= starts_on`.
- A schedule with dates is one session of a camp or workshop. Its
  entries give the daily hours on the weekdays it runs. A one-day
  workshop has `starts_on = ends_on` and one entry.
- `schedule_type` stays `weekly` and `schedule_type_weekly_only` stays.
  The dates bound a weekly pattern. That keeps the API additive: no
  new enum value reaches an old client.
- Replace the unique constraint
  `schedule_unique_activity_location_languages` with a unique index on
  `(activity_id, location_id, languages, starts_on)` declared
  `NULLS NOT DISTINCT` (Aurora PostgreSQL 16.4 supports it; confirm
  the CI and local PostgreSQL version does). An undated schedule
  stays one per activity, location, and language set. A camp can have
  one session per start date.
- Seed assessment: nullable columns, no seed change.
  Update `docs/architecture/database-schema.md`.

### G2. Backend (yellow)

Tests first: `tests/test_admin_schedule_validation.py`,
`tests/test_search_queries.py`, `tests/test_search_incomplete.py`,
`tests/test_search_validation.py`, and the import tests.

- Model and repository: `backend/src/app/db/models/activity.py`,
  `backend/src/app/db/repositories/schedule.py`.
- Admin schedule resource
  (`backend/src/app/api/admin_resource_schedule.py`): accept and
  return the dates, and fix `_ensure_unique_schedule`. Reject an entry
  whose Hong Kong weekday does not occur between `starts_on` and
  `ends_on`. Entries stay stored in UTC as today.
- Search: a session whose `ends_on` is before today in Hong Kong is
  treated as absent, in `build_search_query` and in
  `incomplete_search.py`. A camp with only past sessions therefore
  shows as "dates on request". New parameters `date_from` and
  `date_to` (`YYYY-MM-DD`): a schedule matches when it has no dates or
  its range overlaps. Return `schedule.starts_on` and
  `schedule.ends_on`. Update `docs/api/search.yaml`, the staging
  store, and the fixture generator.
- Sorting stays `time` and `price`. Sorting a camp list by start date
  is done at build time on landing pages. A server-side `date` sort
  touches the cursor and is a follow-up.
- Imports and versions: `admin_imports_allowed.py`,
  `admin_imports_schedule.py`, `import_merge.py`,
  `catalog_version_payload.py`, `catalog_version_shape.py`,
  `catalog_version_match.py`, `docs/imports/admin-import-sample.json`.
- Review: add `camp_without_dates` to `org_review.py` and
  `org_review_sql.py`.
- Website enrichment, last and separable: let the model return
  `kind` for an activity and `starts_on` and `ends_on` for a schedule
  row (`backend/src/app/services/enrichment/prompt.py`, `parse.py`,
  `apply_rows.py`, `row_blockers.py`, `sheet.py`). A date needs a
  quote from the page, like a price does.

### G3. Admin web and public site

- `apps/admin_web/src/components/shared/schedules-panel.tsx` and
  `schedules/schedule-form-utils.ts`: optional date inputs, and
  several dated sessions per activity and venue.
- `apps/public_www/src/lib/activities/schedule-format.ts`: a date
  range formatter for both locales. Card: "21–25 Jul · 09:00–15:00".
  Activity page: a "Dates" section listing the upcoming sessions.
  Camp landing page sorted by next start date. The weekend preset
  sends `date_from` and `date_to` for the coming Saturday and Sunday.

Done when: the tests pass; `alembic upgrade head` then the seed file
run clean; an admin adds two sessions to one camp in the browser; the
public card shows the next session; a session that ended yesterday is
not shown.

## Workstream I: eat with kids pilot

Yellow backend, green public site. No schema change. Stanley only.

1. **Rule in search.** A `kind = eat` row is public only when its
   organisation is parent-verified. Put the rule in
   `build_search_query` and `incomplete_search.py`, with tests in
   `tests/test_search_queries.py`.
2. **Data entry.** The owner adds each place by hand in the admin
   console after visiting: organisation, venue, one activity of kind
   `eat` under "Eat with kids", its facts, and opening hours. No
   import and no enrichment for this kind.
3. **Public site.** The `eat` kind is already in the choices file as
   a pilot (workstream E). The wizard and the results page offer it
   only when the snapshot has at least three such listings. The map
   gets a "Family-friendly food" toggle that adds these pins beside
   the current results. The card shows the facts, including the ones
   a parent found missing ("No high chairs"). A landing page
   `/activities/eat/` appears at three listings.
4. **What it never has.** Food ratings, price bands, menus, or any
   listing the owner has not visited.

Done when: tests pass; an unverified eat listing is absent from
search; a verified one shows its facts on the map and its page.

## Files

By zone, for a quick review of blast radius. Each workstream lists its
own files in full.

- **Red**: three Alembic revisions under `backend/db/alembic/versions/`
  and `shared/home_wizard/home_wizard_choices.json`.
- **Yellow**: `backend/src/app/db/models/**`,
  `backend/src/app/db/queries.py`,
  `backend/src/app/db/incomplete_search.py`,
  `backend/src/app/api/search*.py`, `schemas.py`,
  `admin_resource_*.py`, `admin_imports_*.py`,
  `partner_activity_categories.py`,
  `backend/src/app/services/listing_kinds.py` (new),
  `category_suggestions/**`, `enrichment/**`, `org_review*.py`,
  `catalog_version_*.py`, `staging_search_*.py`,
  `apps/admin_web/src/**`, `docs/api/*.yaml`, and the copied asset
  `apps/siutindei_app/assets/home_wizard/home_wizard_choices.json`.
  Nothing else under `apps/siutindei_app/**` changes.
  `scripts/codegen/**` is not named in `docs/architecture/zones.md`;
  treat it as yellow, because its output lands in `shared/**`.
- **Green**: `apps/public_www/**`, `docs/architecture/**`, tests.

## Invariants this change preserves

- Search responses only gain fields. A request that sends none of the
  new parameters returns the same listings as before, minus those
  in a hidden category.
- Pending categorisation keeps its id and its guards, and public
  search still excludes it.
- The area scope and the review gate behave as today. Partner calls
  stay exempt from the area scope.
- No migration deletes an activity or an organisation. School
  listings are hidden and can be brought back by re-assigning them.
- An import file that sends an old category label still resolves.
  `skip_deleted_organizations` still applies.
- Only an admin can set the verified flag, its date, the kind, and the
  facts.
- `shared/home_wizard/home_wizard_choices.json` stays the one source,
  and the sync check passes.
- The public site stays a static export. No page needs a server.
- English and Traditional Chinese change together.
- Endpoint details live only in `docs/api/*.yaml`.
- No real personal names, phone numbers, emails, or street addresses
  in source, tests, or docs. Model prompts keep redacting contacts.
- No new API Gateway route and no infrastructure change.

## Done when

Per workstream, the commands under its "Done when". For the whole
plan:

- `pytest tests backend` passes, and `pre-commit run ruff-format
  --all-files` leaves no diff.
- `npm run lint`, `npm run typecheck`, and `npm test` pass in
  `apps/public_www`. `npm run lint` and `npm run typecheck` pass in
  `apps/admin_web`.
- `python3 scripts/check_openapi_routes.py`,
  `node scripts/check-lambda-docs.mjs`,
  `bash scripts/codegen/sync-home-wizard-choices.sh --check`,
  `python3 scripts/validate_agent_rules.py`, and
  `bash scripts/check-pii.sh` pass.
- On staging, for Stanley: no school or members-only club in results;
  every card shows the facts of its kind; no card prints a catch-all
  age range; the hub's summary shows believable ranges; the wizard
  offers the first question and five age groups; a type page such as
  `/en/activities/sports/` exists when the topic has three listings.
- The owner has run the recheck and the Stanley clean-up in C4, and
  the readiness card shows Stanley's shares.

## Rollback

- **A, E2, F**: revert the commits and redeploy the public site.
- **D, H, I and the yellow parts of B, C, G**: revert and redeploy
  the backend and the admin console. New response fields disappear;
  the public site treats a listing with no `kind` as a class.
- **B1 and G1**: `alembic downgrade` drops the new columns. Kinds,
  facts, checked dates, and session dates entered since are lost.
  Revert the code that reads them first.
- **C1**: the downgrade is lossy where old leaves merged. Prefer to
  fix forward. Before the upgrade on production, take a database
  snapshot; a full return to the old tree is a restore of the
  category, activity, suggestion, and review tables from it.
- **E1**: restore the previous choices file and run the sync script.

The hooks ask before `alembic downgrade`. That is expected.

## Open questions

The owner answered the questions on the gate, the money sentence, the
age of a check, members-only clubs, and the Flutter app. They are
decisions 8 to 12. What is left blocks no workstream from starting.

1. **Chinese names and copy.** The topic names, kind labels, and copy
   in this plan need a native read before they ship. This applies to
   each workstream that ships Chinese text: A, C, E, and F.
2. **Legacy roots.** How many production activities still sit on
   Workshop, Class, Outdoor activity, Indoor fun, or Sport? When the
   answer is none, a follow-up removes the fallback in
   `backend/src/app/db/queries.py` and the `category_match` handling
   in the clients.
3. **Partners.** Does any partner integration store the seven old
   group ids? If so, tell them before C1 runs.
