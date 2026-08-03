# Notes 2.0 📝

A note-taking app built around one idea: **the words in your notes should be able to move.**

You write a note the way you would in any notes app. Then, standing on any word, you press a
chevron and roll it up or down a *difficulty ladder* — `going` → `running` → `leading` →
`passing` → `extending` — and the word is replaced in place. Up is rarer and more formal, down
is plainer. It is vocabulary practice on your own writing rather than on someone else's flashcards.

Making that work is most of what this repo is. A dictionary (WordNet) knows what a word's
synonyms are but not which one belongs in the sentence in front of it. A language model knows
the opposite. So neither one does the job alone: **the dictionary proposes and a masked language
model ranks.**

## 🌟 Features

**Working today**

- **The word ladder** — put the caret in any word and chevrons appear above and below it. Click
  one and the word rolls like a slot reel to the next rung. The climb is anchored to the word you
  started from, so pressing down walks back exactly the way you came.
- **Units, not words** — what gets replaced is not always the word under the caret. `give up` has
  a ladder neither of its words can reach, and an article travels with the word it attaches to so
  `an example` becomes `a model` rather than `an model`. The API resolves a caret to a span.
- **Sense disambiguation in context** — the same word in two sentences gets two different ladders:

  ```
  "She was running through the park."      → going, running, leading, passing
  "We were running through the supplies."  → using up, eating up, wiping out
  ```

- **One continuous note surface** — the landing page *is* your most recently touched note, live
  and editable. Double-click it and a box animates in around text that never moves, revealing the
  library of every other note beneath. Double-click again to go back. That gesture is the only
  navigation: there is no sidebar and no nav bar.
- **Persistence** — notes, pinning, and word definitions are stored in PostgreSQL through a
  FastAPI backend, with the whole ladder computation cached so a repeat lookup costs no model time.

See [Project status](#-project-status) for what does not work yet.

## 🏗️ Architecture (Monorepo)

```
notes-2.0/
├── notes2.0/                  # Frontend (React Router v7 + Vite, SSR)
│   └── app/
│       ├── routes.ts          # Route config; the layout wrapper lives here
│       ├── routes/            # workspace (layout), home, notes, analytics, menu,
│       │                      #   api.word-ladder (resource route)
│       ├── workspace/         # note-surface.tsx, word-roller.tsx
│       ├── notes/             # notegrid.tsx — the library grid
│       ├── lib/api.server.ts  # Server-only typed API client
│       └── app.css            # Design tokens: paper/ink/rose, Playfair + EB Garamond
├── backend/                   # API + persistence (FastAPI + SQLAlchemy)
│   ├── main.py                # App entrypoint: CORS, /health, router wiring
│   ├── entrypoint.sh          # Runs `alembic upgrade head`, then uvicorn
│   ├── app/
│   │   ├── api/               # Routers: users, notes, word_definitions, vocab
│   │   ├── crud/              # Database operations, incl. the ladder cache
│   │   ├── db/                # SQLAlchemy models, session factory, dev seed
│   │   ├── schemas/           # Pydantic request/response models
│   │   └── services/          # vocab.py (the ladder) + ranker.py (the judge)
│   ├── alembic/               # Database migrations
│   └── tests/                 # 36 tests over the ladder logic
├── docker-compose.yml         # frontend + backend + PostgreSQL
├── .env.example               # Config template; copy to .env (which is ignored)
├── DESIGN.md                  # Visual and navigation direction
└── PROGRESS.md                # Working context: architecture, traps, open items
```

### The structural fact worth knowing

`/` and `/notes` are **children of a layout route** (`app/routes/workspace.tsx`). React Router
keeps a parent mounted while its children change, so the note surface survives navigation between
the two pages. The title and body are literally the same DOM nodes in both modes, which is why
opening a note is not a page swap. Every difference between the two (padding, background, shadow,
type size) is a value on that one element.

This is load-bearing. `PROGRESS.md` records why the alternative was built, tried, and deleted.

### Tech Stack

**Frontend (`notes2.0/`)**
- **Framework:** React Router v7 (SSR), React 19, Vite
- **Language:** TypeScript
- **Styling:** Tailwind CSS v4, with `shadcn/ui` and Base UI components
- **Animations:** Framer Motion (tweens, never springs — see `DESIGN.md` §10)
- **Type:** Playfair Display (display) + EB Garamond (body), via Fontsource

**Backend (`backend/`)**
- **Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL 15 via SQLAlchemy 2.0 ORM, migrations with Alembic
- **Lexicon:** NLTK's WordNet (synonyms, senses, adjective satellites), `lemminflect`
  (lemmatisation and re-inflection), `wordfreq` (the difficulty axis)
- **Ranking:** `transformers` + CPU `torch`, running `distilbert-base-uncased` as a scorer

### Data model

Four tables. A user owns many notes; notes and word definitions are linked many-to-many through a
`note_word` association table, so one definition is shared across every note that uses the word.
`word_ladders` is a standalone cache, keyed on the surface form and a hash of the sentence.

```
User ──< Note >──note_word──< WordDefinition          WordLadder
```

Deleting a user cascades to their notes. Deleting a note or a word only removes the link between
them, never the row on the other side.

## 🔌 API

All routes are prefixed with `/api`. Interactive docs are served at `/docs` once running.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness check (not under `/api`) |
| `GET` | `/api/vocab/ladder` | **The ladder.** Takes `sentence` and `caret`; returns the rungs plus the `start`/`end` of the unit it resolved to |
| `POST` | `/api/users` | Create a user (409 if the email is taken) |
| `GET` | `/api/users` | List users (`skip`, `limit`) |
| `GET` | `/api/users/me` | The seeded development user |
| `GET`/`PATCH`/`DELETE` | `/api/users/{id}` | Read, partially update, or delete a user |
| `POST` | `/api/notes` | Create a note (404 if the owner doesn't exist) |
| `GET` | `/api/notes` | List notes, newest-touched first, optionally filtered by `?user_id=` |
| `GET`/`PATCH`/`DELETE` | `/api/notes/{id}` | Read, partially update, or delete a note |
| `POST` | `/api/notes/{id}/touch` | Bump `updated_at`. Needed because an empty `PATCH` changes no attributes, so SQLAlchemy's `onupdate` never fires — opening a note has to touch it explicitly |
| `POST`/`DELETE` | `/api/notes/{id}/words/{word_id}` | Link or unlink a word and a note |
| `POST` | `/api/words` | Create a word definition |
| `GET` | `/api/words` | List definitions, or look one up with `?word=` |
| `GET`/`PATCH`/`DELETE` | `/api/words/{id}` | Read, partially update, or delete a definition |

`PATCH` bodies only need the fields being changed; omitted fields are left untouched.

### The ladder endpoint

```bash
curl -s "localhost:8000/api/vocab/ladder?sentence=She%20was%20running%20through%20the%20park.&caret=10"
```
```json
{ "word": "running", "pos": "v", "rungs": ["going", "running", "leading", "passing", "extending"],
  "origin_index": 1, "start": 8, "end": 15, "id": 49 }
```

The caller sends a **caret**, not a word, because the unit to replace is not always the word under
it. The resolved span comes back as `start`/`end` so the caller knows what to swap. The whole
ladder arrives in one response rather than a rung at a time: the roller's animation is 460ms, and
a network round trip inside it would stall the reel.

Two environment switches:

| Variable | Default | Effect |
| --- | --- | --- |
| `LADDER_RANKING` | `on` | `off` skips the model entirely: dictionary-only ladders, cached per word, no torch loaded |
| `MLM_MODEL` | `distilbert-base-uncased` | Baked into the image at build time |

## 🚀 Getting Started

### Docker (the supported path)

```bash
docker compose up -d --build
```

Frontend on `http://localhost:3000`, API on `http://localhost:8000`, PostgreSQL on `5432`. The
backend entrypoint runs `alembic upgrade head` before uvicorn, gated on the database healthcheck.

Configuration comes from `.env` at the repo root, which is gitignored. Copy the template first:

```bash
cp .env.example .env      # then fill in POSTGRES_PASSWORD
```

It sets `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` and `DATABASE_URL`.
Inside the compose network the frontend reaches the API at `http://backend:8000` and the backend
reaches the database at host `db`, since containers don't share the host's loopback — so
`DATABASE_URL` uses `db` under compose and `localhost` outside it.

> **Note:** the inline defaults in `docker-compose.yml` differ from the template — compose falls
> back to user and password `postgres`. Since compose reads `.env`, the file wins; just don't rely
> on the inline defaults.

### Working on the frontend without Node on the host

Typecheck and build through Docker:

```bash
docker run --rm -v "$PWD/notes2.0":/app -w /app node:20-alpine \
  sh -c "node_modules/.bin/react-router typegen && node_modules/.bin/tsc"
```

Add a dependency without touching the host's `node_modules`:

```bash
docker run --rm -v "$PWD/notes2.0":/app -w /app node:20-alpine \
  npm install --package-lock-only --save <pkg>
```

### Tests

```bash
docker compose exec backend python -m pytest tests/ -q
```

```
....................................                                     [100%]
36 passed in 17.22s
```

### Running outside Docker

A stale `backend/venv/` may still be sitting on disk from before it was untracked; **its
interpreter does not work**. Ignore it and build your own:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000
```

```bash
cd notes2.0 && npm install && npm run dev     # http://localhost:5173
```

Loaders and actions call the backend server-side through `app/lib/api.server.ts`, which reads
`API_URL` and falls back to `http://localhost:8000` — so start the API first. Because the browser
never calls the backend directly, there is no CORS to configure for this path.

## 📌 Project status

The ladder, the note surface, and persistence are wired end to end. What is not:

- **Vocabulary extraction and quiz mode are not connected.** `notegrid.tsx` and `analytics.tsx`
  still call `/api/analyze/vocabulary` and `/api/words/known`, which do not exist — they were
  dropped when the backend was restructured. Both call sites also hardcode
  `http://127.0.0.1:8000` from the browser instead of going through `api.server.ts`, so they are
  the last places that bypass the server-only client. See the `TODO(step 6)` in each file.
- **Acronyms and jargon have no ladder.** `ML` resolves to *millilitre*; `API` and `GPU` have no
  WordNet entry at all. This is a lexicon gap, not a ranking one, so nothing downstream can fix
  it — it needs either a guard that declines on unknown tokens or an open-vocabulary fallback.
- **Noun senses still discriminate poorly.** Verbs are reliable; `model` returns the
  *example/exemplar* reading in both "a ML model" and "a model in Paris".
- **The ranker costs 400–800ms on a cache miss** and ~1GB of image for torch and the weights.
  Both are per-deployment rather than per-keystroke, but the first press on a new sentence is
  visibly slower than the 460ms roll.
- **Dark mode does not exist**, and the ornament layer in `DESIGN.md` §6 is specified but unbuilt.
- **The old `.env` is still in git history.** The tracked copy is gone and `.env` is ignored now,
  but this repo is public, so the Postgres password that was in it should be treated as burned. It
  pointed at a throwaway localhost database and no history rewrite was done.

`PROGRESS.md` carries the full open-items list and 23 documented traps that cost real time — read
it before touching the UI.
