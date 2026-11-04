# open-radars-manaus: design

Date: 2026-11-04. Owner: João (jvitorcosta). Drafted in car-cyberdeck; moves into the new repo's
`docs/` when the repo is created, leaving a short pointer here.

## Intent

Manaus has no public list of where its speed cameras, electronic speed bumps (lombadas eletrônicas) and
red-light cameras actually stand. IMMU publishes addresses only, the news reports counts, and
OpenStreetMap has a handful of nodes with no direction. The CarDeck needs exact points with a heading
and a limit, and so would anyone else building a map, an app or a study.

`open-radars-manaus` is a public open-data repository that holds that list, keeps it current with
community help, and publishes tagged releases. The owner's own words: the repo provides the data for
other users; how they use it is out of scope. The CarDeck becomes one consumer among others: it only
downloads finished releases.

## Goals

- One authoritative, hand-reviewed list of fixed enforcement points in Manaus: position, direction of
  travel the point enforces, speed limit, kind, a short label, where it came from and when it was last
  confirmed.
- Easy to use without our tools: a plain CSV and a GeoJSON anyone can open in a map.
- Easy to contribute to, in Portuguese first: people can report a new camera or a mistake through an
  issue form without knowing git, or send a PR.
- Contributions are explicitly welcome, and the repo says so up front.
- Every change is checked automatically; only the owner merges; releases are tagged and versioned so a
  consumer can pin one.
- The tooling that builds the list lives here, next to the data: fetching the sources, auto-placing
  IMMU addresses, the review map, validation and the GeoJSON build.

## Non-goals

- How consumers use the data (apps, alerts, devices): out of scope.
- Cities other than Manaus. The layout should not prevent adding one later, but nothing is built for it.
- An API, a website or a hosted map beyond what GitHub already gives (file view, releases, raw files).
- Pushing to the CarDeck or talking to any device. That stays in car-cyberdeck.

## Anti-goals (a failure even if it works)

- **Mobile enforcement.** No police checkpoints, blitz locations, mobile radars or anything that moves.
  Only fixed, public enforcement points. A PR or issue adding one is closed.
- **Personal data.** No plates or faces in photos, and never raw position traces from anyone's car.
  A CarDeck mark is turned into a point on the road before it leaves the owner's PC.
- **Unconfirmed guesses in the data.** An auto-placed point is a guess until a human confirmed it on
  the review map. Guesses live only on the review map and in `placed.json` (git-ignored); `radars.csv`
  holds confirmed points only.
- **Detector territory.** The data describes where public infrastructure is. Nothing in the repo
  detects radar signals or encourages it (CTB art. 230 III bans detectors; GPS against a list is not
  one).

## The data

### `data/radars.csv` — the source of truth, the only file edited by hand

Same columns as today's car-cyberdeck `data/cameras.csv`, so the CarDeck reads it unchanged:

```
id,kind,lat,lon,heading,limit,label,source,checked
```

| Column | Meaning |
|--------|---------|
| `id` | `mao-NNNN`, four digits, assigned in order, never reused (see "Ids" below) |
| `kind` | `speed`, `bump` (lombada eletrônica) or `redlight` (avanço de sinal; a camera that also checks speed is `speed`) |
| `lat`, `lon` | WGS84, 6 decimals, on the carriageway the point enforces |
| `heading` | 0..359, the direction of travel being enforced (degrees from north). Required: a point without direction would alert both lanes |
| `limit` | km/h, 1..199, empty when unknown; always empty for `redlight` |
| `label` | short Portuguese description in today's `Street · District` style, e.g. `Av. Prof. Nilton Lins 900 · Flores`. The tools match points by the words after `·`. No commas, no quotes |
| `source` | where the point first came from: `immu`, `osm`, `survey`, `car`, `community`. It stays when the point is confirmed (a confirmed IMMU guess keeps `immu`). Today's `immu-survey` becomes `survey` |
| `checked` | date (YYYY-MM-DD) a human last confirmed it on the review map or on the street. Required: every row is confirmed |

Plain CSV, UTF-8, LF, no quoting (labels can't hold commas or quotes), rows sorted by id. One point per
direction: a camera covering both directions is two rows with opposite headings.

### Ids

- `data/retired.txt` lists every removed id, one per line, with the date and a reason. Removing a row
  means adding its id there. CI checks that every id on `main` is still in the CSV or in
  `retired.txt`, and that no retired id is back in the CSV.
- A new id is the next number after the highest id in the CSV and `retired.txt` together.
- Contributors mostly use the issue forms and the owner adds the rows. A contributor's PR takes the
  next free id; when two open PRs pick the same one, the second fails CI after the first merges and is
  rebased with the next number.

### `data/radars.geojson` — generated, never edited

A FeatureCollection of Points with every CSV column as a property (`limit` as a number or null).
Built by the tools from the CSV and committed, so it is always next to the CSV in every release.
CI fails when the committed GeoJSON doesn't match the CSV.

### Releases

- Calendar versions: `YYYY.MM.N` (e.g. `2026.11.0`, then `2026.11.1` for a second release that month).
- A release is a git tag plus a GitHub Release with two assets: `radars.csv` and `radars.geojson`,
  copies of the files in `data/` at that tag.
- `CHANGELOG.md` has an entry per release: added, moved, changed, removed points by id.
- The owner cuts releases (by hand, with a helper command that builds the assets). Consumers pin a
  version or take the latest.

### Licences

- Data (`data/`): **ODbL 1.0**. Parts come from OpenStreetMap, so credit
  "© OpenStreetMap contributors" in the README and in the release notes.
- Code (`tools/`, CI): **MIT**, copyright the owner, like car-cyberdeck.

## The tooling

Moves out of car-cyberdeck (`tools/cameras.py`, `tools/camera_place.html`, `tools/test_cameras_tool.py`,
`tools/testdata/immu_inforadar.html`, `cam_test.csv`, `cam_bad.csv`) into this repo, minus the device
parts. Python 3, standard library only (as today), with pytest tests.

| Command | What it does |
|---------|--------------|
| `fetch` | reads the IMMU page and the OSM nodes, compares them with the CSV, prints new / gone / limit unknown. Edits nothing |
| `check` | `fetch` with exit 1 when anything is new or gone. The owner runs it locally (monthly routine); no scheduled CI calls the sources |
| `place` | auto-places the unplaced points (below), shows the CSV's existing rows next to them on the review map, serves it locally |
| `place --apply placed.json` | merges the saved review map into the CSV: an item with an `id` updates that row (moved, new limit, new `checked` date); an item without one is appended with a new id. Only confirmed items are applied |
| `validate` | the CSV rules (below); what CI runs |
| `geojson` | rebuilds `data/radars.geojson` from the CSV |
| `release VERSION` | checks a clean tree, validates, copies the release assets into `dist/`, prints the changelog lines to fill in |

### Auto-placing an IMMU address

1. Geocode the address with Nominatim (bounded to Manaus, 1 request/s, a proper User-Agent naming the repo).
2. Snap to the nearest OSM carriageway with a matching street name (Overpass), on the side the IMMU
   "sentido" names when the road is split into two one-way ways.
3. Take the heading from that way's direction at the snapped point.
4. Show it as a guess on the review map, so the reviewer sees it was not placed by a human.

When any step fails the point lands at the geocoded spot (or the city centre) with no heading, and the
reviewer places it by hand. Nothing is ever confirmed automatically and a guess never enters the CSV;
an IMMU point that was guessed but not confirmed is still "new" for `fetch`.

### The review map

Today's `camera_place.html`: drag each pin onto its road, set the arrow, limit and label, then save
`placed.json`. Added: the CSV's existing points are shown too and can be edited or re-confirmed (they
keep their id in `placed.json`); guesses look different from confirmed points; a "confirm" control is
the only way to set `checked` (today's date). Uses OSM tiles with attribution, served from `127.0.0.1` like today.

### Validation rules (`validate`, run by CI)

Today's `validate()` rules that are about the data itself:

- header exactly as above; 9 columns per row; no quotes
- `kind` in the three values; `lat`/`lon` in range **and inside the Manaus bounding box**
  (`-3.25,-60.15` to `-2.90,-59.80`)
- `heading` 0..359 required; `limit` empty or 1..199, empty for `redlight`; ASCII digits only
- `id` matches `mao-\d{4}`, unique; rows sorted by id; the `retired.txt` rules above
- `checked` a valid date, not in the future; `source` in the list above
- label ≤ 27 bytes is a **warning**, not an error (the CarDeck cuts labels there; other consumers don't care)
- GeoJSON matches the CSV

The CarDeck's device limits (96 rows, 6144 bytes) are **not** rules here: they are one consumer's limits
and are checked in car-cyberdeck before a push.

## Contributing

- `README.md` in Portuguese first, then an English section: what the data is, the ground rules (fixed
  points only, no personal data), how to download a release, the licences and OSM credit, and a clear
  "Contribuições são bem-vindas" with the two ways to help.
- `CONTRIBUTING.md` (PT then EN): the ground rules, how to fill a row, how to confirm a point, how a PR
  is checked, that the owner merges.
- Issue forms in Portuguese with English in brackets:
  - **Informar um radar [Report a camera]**: kind, address or map link, direction, limit, when seen,
    optional photo (with the no plates / no faces rule next to the upload).
  - **Algo errado [Something's wrong]**: which id, what is wrong (moved, gone, wrong limit or direction).
- A PR template with the checklist: fixed point, no personal data, `validate` passes, GeoJSON rebuilt.
- Labels: `novo-ponto`, `correção`, `precisa-verificar`.
- Branch protection on `main`: CI must pass; only the owner merges.

GitHub metadata: description "Radares, lombadas eletrônicas e câmeras de avanço de sinal em Manaus:
dados abertos"; topics `radares`, `manaus`, `dados-abertos`, `openstreetmap`.

## First data

The first release holds what is confirmed at that point. car-cyberdeck's `data/cameras.csv` is empty
(header only), so nothing migrates. Known sources today: the IMMU page (20 points,
addresses only), 7 Av. do Turismo survey points at 60 km/h, 4 OSM nodes (60, 60, 60, 80). The news
reports 34 cameras since February 2026, so IMMU lags; community reports fill the gap. The repo can be
published with an empty list and no release yet; `2026.11.0` is cut once the owner has confirmed points.

## car-cyberdeck afterwards (consumer only)

- `tools/cameras.py` shrinks to device work:
  - `push [--release VERSION]` downloads `radars.csv` from that GitHub Release (latest when omitted),
    applies the deck's own rules (today's full `validate`, including 96 rows / 6144 bytes), then
    `POST /cam/list`. `--file PATH` pushes a local CSV instead (for testing a PR before release).
  - `import-car` reads `GET /cam/marks` into a git-ignored marks file on the PC. The owner then runs
    the data repo's `place --from file` on it, confirms each point on the review map (dragged onto the
    camera's spot), and commits the result there. Raw marks never leave the PC; `import-car --clear`
    clears the deck's marks afterwards.
  - `fetch`, `check`, `place`, the IMMU and OSM code, the place page and their tests leave.
- `data/cameras.csv` is removed; the README and the camera-alerts spec point to open-radars-manaus.
- The deck firmware is unchanged: same CSV format, same `/cam/list`.
- Order: the data repo is built first. The car-cyberdeck trim follows in the same plan, on the
  `feat/camera-alerts` branch (not merged yet, and it is where `cameras.py` lives). Until the first
  release exists, the deck gets points with `push --file`.

## Decided by the owner

- The repo exists for other people's use; their use is out of scope.
- Contributions accepted, and communicated.
- Portuguese first, English too.
- Name `open-radars-manaus`.
- All list-building tooling moves to the data repo; the CarDeck only consumes released data.

## My calls (owner to check)

- CSV columns unchanged; GeoJSON generated and committed.
- ODbL data, MIT code; calendar versioning.
- The CSV holds confirmed points only; guesses stay on the review map.
- The review map edits existing rows by id as well as adding new ones.
- Retired ids in `data/retired.txt`, checked by CI.
- `check` runs locally, not as a scheduled GitHub Action.
- Labels keep the `Street · District` style; `immu-survey` becomes `survey`.
- Device limits stay out of the data repo's rules; Manaus bounding box is a rule.
- `import-car` only fetches the marks; the data repo's own review map places them (no second copy of
  the page in car-cyberdeck), and no PR is opened automatically.
- The new repo starts from a fresh copy of the tool files (their history stays in car-cyberdeck); the
  first commit message says where they came from.
- The car-cyberdeck trim is part of this plan, after the data repo, on `feat/camera-alerts`.

## Left to the builder

- Module layout inside `tools/`, the CI workflow details (GitHub Actions, Python version), how the
  release helper formats the changelog, and how the review map marks guesses visually.

## Before anything public

- Creating the GitHub repo, pushing, and setting branch protection are outward-facing: the owner
  confirms each.
- Commit author email: the owner's personal Gmail (owner, 2026-11-04), set in the new repo's local git
  config before the first commit.
