# Notes 2.0 — Progress Log

Working context for whoever picks this up next. Read this before touching the
UI; a lot of what looks like odd code here is load-bearing, and the reasons are
recorded in [Traps](#traps-do-not-re-litigate-these).

Companion documents:

- [DESIGN.md](DESIGN.md) — the visual and navigation direction. Authoritative
  over `agent.md` §3, which still describes the old look.
- [README.md](README.md) — setup.

Last updated: 2026-07-31 · branch `feature/api-endpoints-review`

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
| `app/workspace/word-roller.tsx` | Chevrons above/below the caret's word + slot-machine roll |
| `app/notes/notegrid.tsx` | The library grid (CSS columns), note cards, ghost `+` card, vocabulary dialog |
| `app/routes/notes.tsx` | The action for **every** note mutation. No loader — reads the list from the layout |
| `app/app.css` | Design tokens: paper/ink/rose palette, Playfair + EB Garamond |
| `app/lib/api.server.ts` | Server-only typed API client. The browser never calls the backend directly |

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

11. **The in-app browser's JS context sometimes reports `window.innerWidth: 0`**
    while rendering the page correctly, which makes every measurement nonsense.
    If numbers look absurd, open a fresh tab before believing them.

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

**Word roller.** Chevrons above and below the caret's word; clicking rolls the
word like a slot reel. Replacement word is currently the same word. It runs on
**both** fields — title and body — from the same component; the title just
needed the same tightly fitting relative wrapper the body already had.

The reel masks the live word with an opaque strip, so it has to know what it is
sitting on. That colour is not constant: the landing page is bare `paper` and
the boxed note is `paper-raised`, and hardcoding the latter left a visible patch
on `/`. `note-surface` now passes the surface colour down. The reel also copies
the field's own typography — sitting outside the textarea, it otherwise
inherited the wrapper's type and rendered the display-face title at body size.

---

## 7. Open items

Ordered by how likely they are to bite.

1. **The ghost `+` writes an empty `Untitled` note on click**, before anything
   is typed. Abandon it and it lingers — and because it is then the
   most-recently-updated note, it *takes over the landing page*. Fix: delete the
   note on close when it is still empty.

2. **Closing a note leaves a dead end.** Done / Escape / click-away drop you on
   the bare library with no note to double-click and no exit link, so the only
   way back to `/` is the browser's back button. Decide between: make those
   actions also return to `/`, or give the bare library its own quiet exit.

3. **Vocabulary analysis is not wired up.** `notegrid.tsx` still calls
   `http://127.0.0.1:8000/api/analyze/vocabulary` **directly from the browser** —
   the last place that bypasses the server-only API client — and the endpoint
   does not exist. See the `TODO(step 6)` in that file.

4. **Dark mode does not exist.** The paper ramp is light-only and `app.css`
   pins `color-scheme: light`.

5. **The ornament layer (DESIGN.md §6) is unbuilt.** Needs real SVG line art;
   it is specified but has no assets.

6. **`components/ui/*` is unmigrated** — still shadcn defaults, off the design
   tokens.

7. **`/analytics` and `/settings` are outside the workspace layout** and
   un-migrated. `/settings` is a placeholder.

8. **`agent.md` §3 contradicts DESIGN.md** (it asks for gradients). It should be
   replaced with a pointer to DESIGN.md.

---

## 8. Verification habits that paid off

- Typecheck in Docker, then `docker compose up -d --build frontend`, then drive
  the real app in the browser. Several bugs here were invisible in the source.
- Check the database directly after any mutation:
  `curl -s localhost:8000/api/notes | python3 -m json.tool`.
- Read the console after UI changes — two crashes were only visible there.
- Restore test data afterwards. Notes created or edited while testing are the
  user's real notes.
