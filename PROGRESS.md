# Notes 2.0 — Progress Log

Working context for whoever picks this up next. Read this before touching the
UI; a lot of what looks like odd code here is load-bearing, and the reasons are
recorded in [Traps](#traps-do-not-re-litigate-these).

Companion documents:

- [DESIGN.md](DESIGN.md) — the visual and navigation direction. Its §12 tracks
  what is applied and what is still outstanding.
- [README.md](README.md) — what the app is, the API, and setup.

Last updated: 2026-08-03 · branch `dev` (`prod` and `master` are still at
`fce0475`, two sessions behind — nothing here has been promoted)

---

## 1. What this app is

A notes app with a vocabulary-study angle. Two surfaces, one object:

- **`/` — the note.** The most recently touched note, set as a full-page hero.
  Live and editable. This is the landing page.
- **`/notes` — the library.** The same note, wrapped in a box, with the grid of
  every other note beneath it. `?open=<id>` says which note is open.

Double clicking the note toggles between the two, in both directions. That
gesture is the only navigation — there is no sidebar, nav bar, or exit link.

---

## 2. Stack and how to run it

| Piece | What |
| --- | --- |
| Frontend | React Router v7 (SSR), TypeScript, Tailwind v4, framer-motion |
| Backend | FastAPI, SQLAlchemy, Alembic |
| DB | Postgres 15 |
| Orchestration | `docker compose` — `frontend`, `backend`, `db` |

```bash
docker compose up -d --build
```

Frontend on `:3000`, API on `:8000`. The backend entrypoint runs
`alembic upgrade head` before uvicorn, gated on the db healthcheck.

**There is no Node on the host.** Typecheck and build through Docker:

```bash
docker run --rm -v "$PWD/notes2.0":/app -w /app node:20-alpine sh -c "node_modules/.bin/react-router typegen && node_modules/.bin/tsc"
```

To add a dependency without touching the host's `node_modules`:

```bash
docker run --rm -v "$PWD/notes2.0":/app -w /app node:20-alpine npm install --package-lock-only --save <pkg>
```

The committed `backend/venv` is broken — do not try to use it. Run backend work
in the container.

---

## 3. Architecture — the part that matters

### The persistent note surface

`/` and `/notes` are **children of a layout route**. React Router keeps a parent
mounted while its children change, so the note survives navigation between the
two pages. This is the single most important structural fact in the app.

```
layout("routes/workspace.tsx")   ← owns the note surface; never unmounts
├── index  "routes/home.tsx"     ← landing mode (renders null)
└── route  "notes"               ← library mode (renders the grid)
```

Because the title and body are literally the same DOM nodes on both pages,
opening a note is not a page swap — a box animates in around text that stays
put. Every difference between the two modes (padding, background, shadow,
min-height, type size) is a value on that one element.

**Do not** try to make the two pages *resemble* each other with matching start
values. That approach was built, tried, and deleted — see
[Traps](#traps-do-not-re-litigate-these).

### Files

| File | Role |
| --- | --- |
| `app/routes.ts` | Route config; the layout wrapper lives here |
| `app/routes/workspace.tsx` | Layout route. Loads the note list once, picks the focused note, touches it on open, renders the surface + `<Outlet/>` |
| `app/workspace/note-surface.tsx` | **The** note. Modes `page` / `boxed`. Auto-height fields, save-on-blur, double-click toggle |
| `app/workspace/word-roller.tsx` | Chevrons above/below the caret's **unit** + slot-machine roll. Holds the climb, and the widened unit span, across re-locates |
| `app/notes/notegrid.tsx` | The library grid (CSS columns), note cards, ghost `+` card, vocabulary dialog |
| `app/routes/notes.tsx` | The action for **every** note mutation. No loader — reads the list from the layout |
| `app/app.css` | Design tokens: paper/ink/rose palette, Playfair + EB Garamond |
| `app/lib/api.server.ts` | Server-only typed API client. The browser never calls the backend directly |
| `app/routes/api.word-ladder.tsx` | Loader-only resource route feeding the roller. Outside the layout on purpose — a lookup inside it would revalidate the note list on every chevron click |
| `backend/app/services/vocab.py` | The ladder: unit detection, WordNet candidates, frequency ordering. Pure apart from calling the ranker. The only backend logic with tests (36) |
| `backend/app/services/ranker.py` | The judge: scores a candidate in its sentence with a masked LM. Loads torch lazily, and returns `None` rather than raising when the model is missing |
| `backend/app/crud/word_ladder.py` | Cache. Resolves the unit **before** the key is computed — see the trap |

### Data flow

- One loader (the layout's) fetches the note list. Children read it with
  `useRouteLoaderData("routes/workspace")`.
- All mutations post to `/notes`'s action with an `intent`:
  `create` · `update` · `togglePin` · `touch` · `delete`.
- After any action React Router revalidates the layout loader, so the UI follows
  the database with no manual refetching.

### Backend

- `notes.updated_at` (migration `b1d4e7a90c25`) drives "which note is the
  landing note". `list_notes` orders by `updated_at DESC, id DESC`.
- `POST /api/notes/{id}/touch` bumps it. **Needed** because an empty PATCH
  changes no attributes, so SQLAlchemy's `onupdate` never fires — opening a
  note has to touch it explicitly.

### The word ladder

`GET /api/vocab/ladder?sentence=…&caret=N` — a **caret**, not a word, because
the thing to replace is not always the word under it. The response carries the
`start`/`end` it resolved to, so the caller knows what to underline and swap.

```
caret ─▶ unit          longest known phrase, else the word, article folded in
      ─▶ candidates    WordNet synonyms of the chosen senses
      ─▶ ranker        which of them read correctly in this sentence
      ─▶ rungs         survivors, ordered by word frequency
```

Two environment switches, both defaulting on/standard:

| Variable | Default | Effect |
| --- | --- | --- |
| `LADDER_RANKING` | `on` | `off` skips the model entirely: dictionary-only ladders, cached per word, no torch loaded |
| `MLM_MODEL` | `distilbert-base-uncased` | Baked into the image at build time |

Cached in `word_ladders`, keyed `(word, context_hash)`. The hash is empty when
ranking is off — a dictionary ladder depends on nothing but the word, so it
should stay cached under it.

---

## 4. Traps (do not re-litigate these)

Each of these cost real time. They are all commented at the site too.

1. **masonic cannot handle a shrinking list.** Its positioner probes indices
   past the end and throws (`undefined` in `itemKey`, then "Invalid value used
   as weak map key"). The old code worked around it with
   `key={ids.join("-")}`, which remounted every card and killed the reflow
   animation. **Removed entirely** — the grid is now CSS `columns-[280px]`,
   which server-renders and never remounts its cards.

2. **framer `layoutId` does not link across a React Router navigation.** The
   loader is async, so the removal and the addition land in different commits
   and framer discards the measurements. This is *why* the layout route exists.

3. **framer suppresses `initial`/`animate` on the element leading a shared
   `layoutId`,** and ignores later `animate` changes on it. Drive those
   properties with CSS transitions or state-toggled classes instead.

4. **`text-align` cannot be tweened.** Any alignment that differs between two
   animated states snaps the words sideways mid-transition. Both modes are
   centred for exactly this reason.

5. **Form controls do not inherit `text-align`.** Setting `text-center` on a
   parent leaves the textarea computing `start`. Put it on the field.

6. **Never trust a zero-width measurement.** `scrollHeight` on an unlaid-out
   textarea reports the text wrapped one character per line — this once made
   the hero title 603px tall and pushed the body off screen. Both
   `useAutoHeight` and `word-roller` guard on `clientWidth === 0`.

7. **`scrollIntoView` is fooled by framer transforms.** On the first frame the
   panel is parked at its old position, so it measures as already visible and
   refuses to scroll. Walk `offsetTop` instead — it is layout based.

8. **Distinguishing the first click of a double click** needs
   `event.detail > 1` guarding, not a plain flag. The second mousedown
   otherwise overwrites whatever the first recorded.

9. **Outside-click-to-dismiss must ignore elements with their own meaning.**
   A mousedown on a note card used to close the open note *and* let the card
   navigate, racing two navigations for one gesture. It now skips
   `[data-note-card], button, a`.

10. **Textarea word positions need a mirror element** — a hidden div copying the
    field's box and typography exactly, with the target word in a measurable
    span. Copy width, font, letter-spacing, line-height, `text-align`, padding
    and borders, or the mirror's line breaks will not match the field's.

11. **The in-app browser pauses between tool calls.** It sometimes reports
    `window.innerWidth: 0` while rendering correctly, and — worse — it stops
    advancing the clock: `requestAnimationFrame` never fires, `setInterval` gets
    ~4 ticks in 2.4s, and a CSS transition sits frozen at its *start* value
    (inline `font-size: 1.875rem`, computed still `52px`, indefinitely). A
    screenshot forces a frame, which is why state sometimes only appears after
    one. **You cannot measure animation smoothness or time anything in this
    browser.** Assert on settled state; verify motion by reasoning about the
    code, and say so rather than claiming it was observed.

12. **A controlled `<textarea>` drops the caret to the end when its value
    changes.** Restoring it in `requestAnimationFrame` runs *before* React
    commits, so the restore is silently undone. The chevrons then vanish
    mid-climb because the caret is no longer inside the word. Use a layout
    effect (`pendingCaret` in `note-surface.tsx`) — after the DOM updates,
    before paint. This was invisible while the roller rolled a word to itself.

13. **`useFetcher()` keeps only the newest response.** The caret crosses words
    faster than the network answers, so a slow reply for a word you have already
    left lands on the word you are on now — and if a guard rejects it, the state
    machine deadlocks and the chevrons never enable. Give each lookup its own
    fetcher with `useFetcher({ key })`. It doubles as a cache: revisiting a unit
    costs no request.

14. **State that must agree has to change in the same batch.** Committing a roll
    advanced the climb while the measured span still described the old word; for
    one render the climb looked like it belonged elsewhere and was discarded, so
    a climb could never pass its first rung. `setSpan` and `setClimb` now move
    together.

15. **`wordAtCaret` only ever finds one word, and will shrink a unit back.**
    Once the span is widened to "a model" or "gave up", every caret move
    recomputes it as "model"/"gave", the climb loses its anchor and **down** dies
    after one press. `word-roller` holds the unit in a ref and keeps it while
    the caret is inside it and the text still reads as it was left.

16. **Word frequency cannot separate archaic from merely rare.** A frequency
    *floor* looks like the obvious way to drop WordNet junk, and it is backwards:
    "shew" scores 2.46, above both "obfuscate" (2.28) and "felicitous" (1.86).
    Any floor cuts good rungs and keeps the junk. Only `zipf == 0` — no signal at
    all — is safe to filter on.

17. **Word frequency cannot separate an idiom from two adjacent words either.**
    "run through" scores 5.34 against "give up" at 5.63, because `wordfreq`
    estimates a phrase from its parts. So there is no frequency test for "is this
    really a phrasal verb here". The ranker decides it instead, by scoring the
    phrase's synonyms against the bare word's.

18. **A masked LM can *score* words it cannot *say*.** One `[MASK]` emits one
    token, and the ~30k WordPiece vocabulary has no single token for the rare
    words this feature exists to offer — `felicitous` is `fe ##lic ##ito ##us`,
    and 7 of 15 sampled hard words split while every plain word survived. So
    generation is structurally biased against the rare end of the ladder.
    Scoring a candidate you already hold has no such limit. **This asymmetry is
    the whole reason the architecture is dictionary-proposes / model-ranks.**

19. **Fluency is not synonymy, and per-word filtering cannot fix it.** "This is a
    bad problem" reads perfectly, so scoring loose candidates by fit lets "bad"
    through as a synonym for "big". Score *senses as groups*: a sense is a set of
    words meaning the same thing, and the wrong set reads badly together even
    when one member reads fine alone.

20. **Do not normalise the ranker by word frequency.** Pointwise mutual
    information is the textbook correction for "common words score well
    everywhere" — and it made this worse, because it rewards rarity and the
    ladder already climbs toward rarity. The two compound: "running through the
    park" went straight back to offering "escaping". Raw fit is correct *because*
    difficulty is applied separately, afterwards.

21. **Resolve the unit before computing a cache key.** Which unit the caret is in
    depends on the sentence — "running through" is the unit in "…through the
    supplies" and not in "…through the park". Keying on the raw longest match
    serves one sentence's answer to the other, and it looks like the ranker is
    broken when it is not.

22. **A shared Postgres volume remembers migrations from other branches.** Switch
    to a branch that lacks a revision the DB is stamped with and the backend will
    not start: `Can't locate revision identified by …`. Downgrade *before*
    switching, or restore the file temporarily, mount the host tree into the
    image (`COPY . .` means a `compose run` will not see your working copy), and
    `alembic downgrade` with the real password from `.env`.

23. **Docker Desktop on macOS has no GPU passthrough.** Anything model-shaped in
    this container is CPU-only whatever you install, so pin the CPU torch wheel
    (`--extra-index-url https://download.pytorch.org/whl/cpu`) or pip drags in
    gigabytes of unusable CUDA.

---

## 5. Conventions

- **Enter commits, Shift+Enter is a newline.** Everywhere.
- Escape also saves and closes; nothing discards.
- Saves only submit when the text actually changed.
- Animation: tweens, never springs (springs wobble even at `bounce: 0`).
  `NOTE_LAYOUT_TRANSITION` in `note-surface.tsx` is the shared curve.
- Serif everywhere: Playfair Display (display) + EB Garamond (body).

---

## 6. Timeline

**Expanding note editor.** Double-click a card to expand it. Started as a fixed
overlay dialog; reworked to an in-flow block so the other notes reflow around
it. Fixed content warping during the morph with `layout="position"` scale
correction.

**Design direction.** Wrote `DESIGN.md` — editorial rather than dashboard,
serif, whitespace over rules, a Starry-Night line-art ornament layer, and a
navigation philosophy (Apple / Google Maps / Dynamic Island). Then applied the
typography and palette: serif fonts, warm paper tokens, borderless cards.

**Sidebar removed** outright, along with `app-sidebar.tsx`, `welcome.tsx` and
the `SidebarProvider` wrapper.

**Landing page** built as a live hero of the last-studied note, editable in
place, double-click to open it in the grid.

**masonic → CSS columns**, after masonic proved unable to handle the grid
shrinking when a note opens.

**The restructure.** Repeated "it still jumps" reports traced to a single root
cause: `/` and `/notes` were separate routes, so nothing survived navigation and
every transition was two elements imitating each other. Rebuilt around the
layout route above. Added `updated_at` + `touch` so the landing note follows
what you actually opened.

**The word ladder.** The vocabulary the roller was waiting for. WordNet supplies
synonyms but has no notion of formality, so frequency provides the missing axis:
rare words read as formal and difficult, common ones as plain. A word's ladder
is its synonyms ordered by how common they are, with the word itself on its own
rung — up is rarer, down is plainer, and the climb is anchored to the word you
started from so pressing down walks back exactly the way you came. Built in
`app/services/vocab.py`, cached in `word_ladders`, served from
`GET /api/vocab/ladder`, and read by the roller through a loader-only resource
route. See [§7](#7-open-items) for where the quality actually stands.

**Word roller.** Chevrons above and below the caret's word; clicking rolls the
word like a slot reel. It runs on
**both** fields — title and body — from the same component; the title just
needed the same tightly fitting relative wrapper the body already had.

The reel masks the live word with an opaque strip, so it has to know what it is
sitting on. That colour is not constant: the landing page is bare `paper` and
the boxed note is `paper-raised`, and hardcoding the latter left a visible patch
on `/`. `note-surface` now passes the surface colour down. The reel also copies
the field's own typography — sitting outside the textarea, it otherwise
inherited the wrapper's type and rendered the display-face title at body size.

**Units, not words.** Replacing the caret's word is the wrong unit surprisingly
often. "give up" means something neither of its words does and has a ladder
neither can reach; an article has to travel with the word it attaches to, or
"an example" becomes "an model". Two findings drove this: **33% of WordNet's
lemma names are multi-word** (68,082 of 206,978) and were all being discarded by
a `"_"` filter, and `similar_tos()` — the adjective satellite clusters — was
never followed, which had left "big" with two candidates where it has 88. The
caret now resolves to a unit: longest known phrase else the word, lemmatised so
"gave up" finds `give_up`, with the tense restored at the **head** for verb
phrases and the **tail** for noun compounds. (Getting that backwards produced
"businesses firm" for "business firms".)

**The generative experiment — tried and abandoned.** Before the current design,
the masked LM was used the obvious way round: blank the word out of its sentence
and ask what fits. It genuinely solved disambiguation — "a ML model" drew
*project, design, code* while "a model in Paris" drew *director, professional* —
but it destroyed meaning, because fill-mask proposes what *fits the slot*, not
what means the same: `big → small`, `use → know, take, love`, `good → public`.
It also cut off the rare end of the ladder for the tokenizer reason in trap 18.
Latency was never the problem (~40–70ms). The branch was closed as
[#14](https://github.com/TS-24/notes-2.0/pull/14); its torch/transformers
plumbing was kept. **Do not re-attempt generation** — the failure is structural,
not a matter of prompting or thresholds.

**The inversion.** The same model, used as a judge instead. WordNet proposes
(no vocabulary ceiling — it is a dictionary) and the model ranks (no synonymy
needed — it only compares). That is `ranker.py`. It fixed the wrong-sense
problem the ladder shipped with, and the same instrument settles which *unit*
the caret is in:

```
"She was running through the park."      → going, running, leading, passing
"We were running through the supplies."  → using up, eating up, wiping out
```

Three approaches were tried and rejected on the way, all recorded as traps
19–21: per-word fluency filtering, taking only the single winning sense, and PMI
frequency normalisation.

---

## 7. Open items

Ordered by how likely they are to bite.

0. **Acronyms and jargon have no ladder at all, and ranking cannot give them
   one.** `ML` resolves to *millilitre*; `API` and `GPU` have no WordNet entry
   whatsoever. This is a *lexicon* problem, not a ranking problem — the
   candidate isn't in the box, so nothing downstream can surface it. Two fixes,
   in order of cost: (a) a guard that declines on tokens the frequency corpus
   does not know, so the roller says nothing instead of offering `MILLILITRE` —
   cheap, and worth doing regardless; (b) an open-vocabulary fallback (hosted
   LLM, or PPDB for phrases) called *only* on lexicon misses and cached forever,
   which converges to almost no calls because a person's jargon is small and
   repetitive.

1. **Some noun senses still do not discriminate.** `model` returns the
   *example/exemplar* reading in both "a ML model" and "a model in Paris", which
   is worse than the plain dictionary's *framework* for the first. Verbs
   discriminate well (`running` is correct in both park and supplies); nouns are
   the weak spot. Suspect the sense-group mean in `ranker.rank_senses` favours
   senses made of common words — but note that the obvious correction for that,
   dividing out word frequency, was tried and made things worse (trap 20). Try
   scoring senses by their gloss instead of by their members.

2. **The ranker costs 400–800ms on a cache miss** and ~1GB of image for torch
   and the weights. Both are per-deployment rather than per-keystroke — a unit
   is cached after its first look — but the first press on a new sentence is
   visibly slower than the 460ms roll. `LADDER_RANKING=off` reverts to
   dictionary-only if that trade stops being worth it.

3. **The ghost `+` writes an empty `Untitled` note on click**, before anything
   is typed. Abandon it and it lingers — and because it is then the
   most-recently-updated note, it *takes over the landing page*. Fix: delete the
   note on close when it is still empty.

4. **Closing a note leaves a dead end.** Done / Escape / click-away drop you on
   the bare library with no note to double-click and no exit link, so the only
   way back to `/` is the browser's back button. Decide between: make those
   actions also return to `/`, or give the bare library its own quiet exit.

5. **Vocabulary analysis is not wired up.** `notegrid.tsx` still calls
   `http://127.0.0.1:8000/api/analyze/vocabulary` **directly from the browser** —
   the last place that bypasses the server-only API client — and the endpoint
   does not exist. See the `TODO(step 6)` in that file.

6. **Dark mode does not exist.** The paper ramp is light-only and `app.css`
   pins `color-scheme: light`.

7. **The ornament layer (DESIGN.md §6) is unbuilt.** Needs real SVG line art;
   it is specified but has no assets.

8. **`components/ui/*` is unmigrated** — still shadcn defaults, off the design
   tokens.

9. **`/analytics` and `/settings` are outside the workspace layout** and
   un-migrated. `/settings` is a placeholder.

9a. **`backend/venv` cannot run the app — rebuild it when off a metered
   connection.** The interpreter is fine (3.12.13) but only 16 packages are
   installed, and `fastapi`, `uvicorn`, `SQLAlchemy`, `alembic` and `pytest` are
   not among them: `venv/bin/python -c "import main"` dies on
   `ModuleNotFoundError: No module named 'fastapi'`. It is the scratch env for
   `app/services/run_once.py` (the only importer of `wn` and `defusedxml`,
   neither of which belongs in `requirements.txt`), not a stale backend env.
   Fix is `venv/bin/pip install -r requirements.txt`, which
   pulls torch and transformers, so it is a large download — deferred on
   purpose, not forgotten. The `psycopg2-binary` pin against the venv's
   `psycopg` 3 is *not* a conflict: SQLAlchemy resolves the bare `postgresql://`
   URL in `app/db/database.py:12` to psycopg2, and `run_once.py` uses psycopg 3
   on its own. See SAFETY-UPDATES.md.

10. ~~**The root `.gitignore` is UTF-16 encoded.**~~ **Fixed.** Both ignore files
   are UTF-8 now and 5,914 files were dropped from the index: `backend/venv/`
   (5,807), `notes2.0/.git.bak/` (101), the 5 stray `__pycache__` files outside
   the venv, and `.env`. All of them are still on disk; only the tracking is
   gone. `.env.example` is the template now.

   **Two things to know.** First, `.env` remains in git history and this repo is
   public, so treat that Postgres password as burned — it is a throwaway pointing
   at `localhost`, but do not reuse it. Removing it properly means a history
   rewrite (`git filter-repo`), which was not done. Second, and this is the trap:
   **an editor that saves as UTF-16 will silently do it again.** `file .gitignore`
   must say ASCII or UTF-8. It is worth checking after any edit to that file,
   because git gives you no error at all — the patterns simply stop matching.

---

## 8. Verification habits that paid off

- Typecheck in Docker, then `docker compose up -d --build frontend`, then drive
  the real app in the browser. Several bugs here were invisible in the source.
- Check the database directly after any mutation:
  `curl -s localhost:8000/api/notes | python3 -m json.tool`.
- Read the console after UI changes — two crashes were only visible there.
- **Test against a scratch note, not the user's notes.** Create one via
  `POST /api/notes`, drive it, `DELETE` it afterwards. Learned the hard way:
  driving the roller on note 10 left three rolled words saved into it
  (`Demo→Demonstration`, `model→framework`, `wanted→required`) and they were
  only caught by inspecting the API at the end. Restoring meant reconstructing
  the original text from an earlier transcript, which is luck, not process.
- Check the database directly after any mutation, and again before you finish:
  `curl -s localhost:8000/api/notes | python3 -m json.tool`.
- The backend restarts when you `compose up --build frontend`, because frontend
  depends on it. A page load during that window fails with `ECONNREFUSED` and
  looks like a code bug. Check `compose ps` uptime before believing it.
