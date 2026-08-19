# Restyle ✍️

**Restyle** is a note-taking app built around one idea: **the words in your notes should be able
to move.**

You write a note the way you would in any notes app. Then, standing on any word, you press a
chevron and roll it up or down a *difficulty ladder* — `going` → `running` → `leading` →
`passing` → `extending` — and the word is replaced in place. Up is rarer and more formal, down
is plainer. It is vocabulary practice on your own writing rather than on someone else's flashcards.

Making that work is most of what this repo is. A dictionary (WordNet) knows what a word's
synonyms are but not which one belongs in the sentence in front of it. A language model knows
the opposite. So neither one does the job alone: **the dictionary proposes and an embedding
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

  **This needs `HF_TOKEN`.** It is the one feature here that does not work out of the box: with
  no credentials the ranker is skipped and both sentences return the same dictionary-ordered
  ladder. See [Environment switches](#the-ladder-endpoint).

- **One continuous note surface** — the landing page *is* your most recently touched note, live
  and editable. Double-click it and a box animates in around text that never moves, revealing the
  library of every other note beneath. Double-click again to go back. That gesture is the only
  navigation: there is no sidebar and no nav bar.
- **Vocabulary analysis** — the words in a note (or in every note at once) that are worth
  learning, with definitions. Dismissing one records it as known, per reader, so the list shrinks
  as you work through it instead of showing you the same words forever.
- **Persistence** — notes, pinning, and word definitions are stored in PostgreSQL through a
  FastAPI backend, with the whole ladder computation cached so a repeat lookup costs no model time.

See [Project status](#-project-status) for what does not work yet.

## 🏗️ Architecture (Monorepo)

```
restyle/
├── frontend/                  # Frontend (React Router v7 + Vite, SSR)
│   ├── Dockerfile             # Multi-stage; the compose image runs react-router-serve
│   └── app/
│       ├── routes.ts          # Route config; the layout wrapper lives here
│       ├── routes/            # workspace (layout), home, notes, analytics,
│       │                      #   menu.tsx (served at /settings),
│       │                      #   api.word-ladder (resource route)
│       ├── workspace/         # note-surface.tsx, word-roller.tsx
│       ├── notes/             # notegrid.tsx — the library grid
│       ├── components/ui/     # shadcn/ui primitives, unmodified
│       ├── hooks/             # use-mobile.ts
│       ├── lib/api.server.ts  # Server-only typed API client
│       └── app.css            # Design tokens: paper/ink/rose, Playfair + EB Garamond
├── backend/                   # API + persistence (FastAPI + SQLAlchemy)
│   ├── main.py                # App entrypoint: CORS, /health, router wiring
│   ├── entrypoint.sh          # Runs `alembic upgrade head`, then uvicorn
│   ├── app/
│   │   ├── api/               # Routers: users, notes, word_definitions, vocab,
│   │   │                      #   analyze, known_words; deps.py holds the current user
│   │   ├── crud/              # Database operations, incl. the ladder cache
│   │   ├── db/                # SQLAlchemy models, session factory, dev seed
│   │   ├── schemas/           # Pydantic request/response models
│   │   └── services/          # vocab.py (the ladder), ranker.py (the judge),
│   │                          #   analysis.py (difficult-word extraction)
│   ├── alembic/               # Database migrations
│   └── tests/                 # 64 tests: ladder, ranker, analysis, known words
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

**Frontend (`frontend/`)**
- **Framework:** React Router v7 (SSR), React 19, Vite
- **Language:** TypeScript
- **Styling:** Tailwind CSS v4, with `shadcn/ui` and Base UI components
- **Animations:** Framer Motion (tweens, never springs — see `DESIGN.md` §10)
- **Type:** Playfair Display (display) + EB Garamond (body), via Fontsource

**Backend (`backend/`)**
- **Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL 15 via SQLAlchemy 2.0 ORM, migrations with Alembic. The migrations
  are also SQLite-safe (batch mode), which is what the test suite runs against
- **Lexicon:** NLTK's WordNet (synonyms, senses, adjective satellites), `lemminflect`
  (lemmatisation and re-inflection), `wordfreq` (the difficulty axis)
- **Ranking:** a hosted sentence-embedding model via `huggingface_hub`, used to pick the sense
  that belongs in the sentence. Optional — without credentials the ladder falls back to the
  dictionary's own ordering

### Data model

Five tables. A user owns many notes; notes and word definitions are linked many-to-many through a
`note_word` association table, so one definition is shared across every note that uses the word.
`word_ladders` is a standalone cache, keyed on the surface form and a hash of the sentence.
`known_words` is per user rather than global, because "difficult" is a fact about a reader and not
about a word.

```
User ──< Note >──note_word──< WordDefinition          WordLadder
 └──< KnownWord
```

Deleting a user cascades to their notes. Deleting a note or a word only removes the link between
them, never the row on the other side.

## 🔌 API

All routes are prefixed with `/api`. Interactive docs are served at `/docs` once running.

Every route requires a signed-in account. Send `Authorization: Bearer <token>` from a script, or
let the cookie the API sets carry it in a browser. Registration is invite-only, so the way in is
a code issued from the CLI — see [Your first account](#your-first-account).

Anything owned by a user answers **404 rather than 403** when it belongs to someone else. 403
would be more precise and worse: it confirms the row exists, which turns the id space into a
directory of other people's writing.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness check (not under `/api`) |
| `GET` | `/api/vocab/ladder` | **The ladder.** Takes `sentence` and `caret`; returns the rungs plus the `start`/`end` of the unit it resolved to |
| `POST` | `/api/analyze/vocabulary` | The words worth learning in a body of text, with definitions. Takes `title` and `content` (capped at 1,000,000 characters, since the analytics page sends every note joined together). Words the user has marked known are left out |
| `POST` | `/api/words/known` | Mark words as already known, up to 500 per request. Returns 204 with no body — the caller has already removed the card and has nothing to do with a response |
| `POST` | `/api/auth/register` | Create an account against a single-use invite code. 400 on a bad or spent code, 409 if the email is taken |
| `POST` | `/api/auth/login` | Exchange an email and password for a token. One message for a wrong password and an unknown email alike, so the endpoint cannot be used to find out who has an account |
| `POST` | `/api/auth/logout` | Clear the API's cookie. Tokens are stateless, so this stops this browser sending one rather than invalidating it |
| `GET` | `/api/users/me` | The signed-in account |
| `PATCH`/`DELETE` | `/api/users/me` | Update or delete your own account. Deleting takes your notes and known words with it |
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
curl -s -H "Authorization: Bearer $TOKEN" \
  "localhost:8700/api/vocab/ladder?sentence=She%20was%20running%20through%20the%20park.&caret=10"
```
```json
{ "word": "running through", "pos": "v",
  "rungs": ["going through", "working through", "using up", "running through", "eating up",
            "eating", "wiping out"],
  "origin_index": 3, "start": 8, "end": 23, "id": 52 }
```

That is the response with no `HF_TOKEN` set, so the rungs are in the dictionary's own order and
`running through` has been resolved as a single phrasal unit — note that `start`/`end` span 8–23,
not just the word under the caret at 10. With a token the same call returns the rungs re-ranked
for the sentence.

The caller sends a **caret**, not a word, because the unit to replace is not always the word under
it. The resolved span comes back as `start`/`end` so the caller knows what to swap. The whole
ladder arrives in one response rather than a rung at a time: the roller's animation is 460ms, and
a network round trip inside it would stall the reel.

Environment switches:

| Variable | Default | Effect |
| --- | --- | --- |
| `LADDER_RANKING` | `on` | `off` skips the model entirely: dictionary-only ladders, cached per word |
| `HF_TOKEN` | unset | Credentials for the hosted ranker. Unset behaves like `LADDER_RANKING=off`, and is checked before any request so a token-less install never pays a timeout to discover it |
| `HF_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | The embedding model the ranker calls |

## 🚀 Getting Started

### Docker (the supported path)

```bash
docker compose up -d --build
```

Frontend on `http://localhost:3700`, API on `http://localhost:8700`, PostgreSQL on `5700`. Those
host ports are a block chosen not to collide with anything else on the machine; each is overridable
(`FRONTEND_PORT`, `BACKEND_PORT`, `POSTGRES_PORT`) and only the host side moves, so the containers
still listen on 3000, 8000 and 5432 internally. The backend entrypoint runs
`alembic upgrade head` before uvicorn, gated on the database healthcheck.

Configuration comes from `.env` at the repo root, which is gitignored. Copy the template first:

```bash
cp .env.example .env      # then fill in POSTGRES_PASSWORD
```

It sets `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` and `DATABASE_URL`,
plus the three optional ranker switches (`HF_TOKEN`, `HF_MODEL`, `LADDER_RANKING`). Those three
have to go in this file to reach the container: `docker-compose.yml` forwards exactly the
variables it names into the backend's environment, and nothing else in `.env` crosses that
boundary. Setting `HF_TOKEN` only in your shell does nothing under compose.

Inside the compose network the frontend reaches the API at `http://backend:8000` and the backend
reaches the database at host `db`, since containers don't share the host's loopback — so
`DATABASE_URL` uses `db` under compose and `localhost` outside it.

> **Note:** the inline defaults in `docker-compose.yml` differ from the template — compose falls
> back to user and password `postgres`. Since compose reads `.env`, the file wins; just don't rely
> on the inline defaults.

### Your first account

Registration is invite-only and there is no admin UI, so the first code comes from the CLI:

```bash
docker compose exec backend python -m app.cli issue-invite     # prints a code
```

Register with it at `/login`'s sign-up form or straight against the API, or skip the invite
entirely and create the account from the same CLI, which is already the privileged path:

```bash
docker compose exec backend python -m app.cli create-user --email you@example.com
```

Notes written before there were accounts belong to a seeded `dev@example.com`. Move them across
once, then that user is gone:

```bash
docker compose exec backend python -m app.cli adopt-dev-data --email you@example.com
```

`list-invites` shows every code and whether it has been spent.

### Working on the frontend without Node on the host

Typecheck and build through Docker:

```bash
docker run --rm -v "$PWD/frontend":/app -w /app node:20-alpine \
  sh -c "node_modules/.bin/react-router typegen && node_modules/.bin/tsc"
```

Add a dependency without touching the host's `node_modules`:

```bash
docker run --rm -v "$PWD/frontend":/app -w /app node:20-alpine \
  npm install --package-lock-only --save <pkg>
```

### Tests

```bash
docker compose exec backend python -m pytest tests/ -q
```

```
................................................................         [100%]
64 passed in 2.88s
```

The suite runs against SQLite, so it needs neither Postgres nor a Hugging Face token: the ranker
is mocked. That is also why it is fast. For the same reason it runs fine outside Docker, from any
virtualenv with `requirements.txt` installed:

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

### Running outside Docker

A stale `backend/venv/` may still be sitting on disk from before it was untracked; **its
interpreter does not work**. Ignore it and build your own:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8700
```

```bash
cd frontend && npm install && npm run dev     # http://localhost:5173
```

Loaders and actions call the backend server-side through `app/lib/api.server.ts`, which reads
`API_URL` and falls back to `http://localhost:8700` — so start the API first. Because the browser
never calls the backend directly, there is no CORS to configure for this path.

## 📌 Project status

The ladder, the note surface, persistence, and vocabulary analysis are wired end to end. What is
not:

- **There is no password reset and no way to change a password.** Losing one means a new account
  or an `UPDATE` by hand. Registration being invite-only is what makes that survivable for now.
- **A token cannot be revoked.** There is no refresh flow and no revocation table, so signing out
  clears the cookie but a token already copied elsewhere stays valid until it expires, up to seven
  days. Rotating `JWT_SECRET` invalidates every session at once, which is the only lever there is.
- **Acronyms and jargon have no ladder.** `ML` resolves to *millilitre*; `API` and `GPU` have no
  WordNet entry at all. This is a lexicon gap, not a ranking one, so nothing downstream can fix
  it — it needs either a guard that declines on unknown tokens or an open-vocabulary fallback.
- **Noun senses still discriminate poorly.** Verbs are reliable; `model` returns the
  *example/exemplar* reading in both "a ML model" and "a model in Paris".
- **The ranker needs the network.** It calls a hosted model, so a cache miss costs a round
  trip and an offline install has no ranking at all — the ladder still works, but wrong-sense
  rungs come back ("escape" for "run"). Ranking by embedding similarity is also a weaker signal
  than the masked language model it replaced: it asks whether a substitution preserves the
  sentence's meaning, not whether it is grammatical.
- **Dark mode does not exist**, and the ornament layer in `DESIGN.md` §6 is specified but unbuilt.
- **The old `.env` is still in git history.** The tracked copy is gone and `.env` is ignored now,
  but this repo is public, so the Postgres password that was in it is permanently exposed. It has
  been rotated, and `DATABASE_URL` no longer has a hardcoded fallback, so the leaked value is dead.
  No history rewrite was done.

`PROGRESS.md` carries the full open-items list and 23 documented traps that cost real time — read
it before touching the UI. Note that it still describes the local `torch` ranker that was replaced
by the hosted one; the README above is current, `PROGRESS.md` is not.
