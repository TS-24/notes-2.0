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
- **AI chats** — a second card sits at the right of the library, the twin of the `+` that starts a
  note, and it opens a conversation in the same box an open note sits in. Finishing one asks the
  model to summarise it in three parts: what it was about and its topics, what you kept asking,
  and what the answers concentrated on. That summary becomes what the chat's card shows in the
  library, because nobody rereads a transcript.

  **This needs your own API key.** Add a provider (Anthropic or OpenAI) and a key on `/settings`;
  it is encrypted at rest and never sent back to the browser. Without one, chats refuse politely
  and tell you where to go. There is no shared or built-in key.
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
- **Database:** Neon (hosted PostgreSQL 18) via SQLAlchemy 2.0 ORM, migrations with Alembic. The migrations
  are also SQLite-safe (batch mode), which is what the test suite runs against
- **Lexicon:** NLTK's WordNet (synonyms, senses, adjective satellites), `lemminflect`
  (lemmatisation and re-inflection), `wordfreq` (the difficulty axis)
- **Ranking:** a hosted sentence-embedding model via `huggingface_hub`, used to pick the sense
  that belongs in the sentence. Optional — without credentials the ladder falls back to the
  dictionary's own ordering

### Data model

A user owns many notes; notes and word definitions are linked many-to-many through a
`note_word` association table, so one definition is shared across every note that uses the word.
`word_ladders` is a standalone cache, keyed on the surface form and a hash of the sentence.
`known_words` is per user rather than global, because "difficult" is a fact about a reader and not
about a word.

```
User ──< Note >──note_word──< WordDefinition          WordLadder
 ├──< KnownWord
 ├──< Chat ──< ChatMessage
 └──1 ProviderCredential
```

Plus `invite_codes` and `revoked_tokens`, which belong to registration and sign-out rather than to
the reading path.

Deleting a user cascades to their notes, known words, chats and stored credential. Deleting a note
or a word only removes the link between them, never the row on the other side.

A chat holds its own summary in four columns written together, with `summarized_at` as the single
test for "finished" — a separate status column would be a second fact to keep in step, and the two
would eventually disagree. `ProviderCredential` is **one row per user**, not one per provider:
picking a different provider is a change of mind, not a second credential.

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
| `GET` | `/api/notes` | List notes, newest-touched first. `?search=` matches the title; `?skip=` / `?limit=` page. Scope is always the signed-in account, never a parameter |
| `GET`/`PATCH`/`DELETE` | `/api/notes/{id}` | Read, partially update, or delete a note |
| `POST` | `/api/notes/{id}/touch` | Bump `updated_at`. Needed because an empty `PATCH` changes no attributes, so SQLAlchemy's `onupdate` never fires — opening a note has to touch it explicitly |
| `POST`/`DELETE` | `/api/notes/{id}/words/{word_id}` | Link or unlink a word and a note |
| `POST` | `/api/words` | Create a word definition |
| `GET` | `/api/words` | List definitions, or look one up with `?word=` |
| `GET`/`PATCH`/`DELETE` | `/api/words/{id}` | Read, partially update, or delete a definition |
| `GET`/`PUT`/`DELETE` | `/api/settings/provider` | The AI provider credential. `GET` never returns the key — only `key_hint`, its last four characters, plus the providers you could pick. `PUT` replaces whatever was there; `DELETE` forgets it and is not an error when there is nothing to forget |
| `POST` | `/api/chats` | Start an empty conversation. Deliberately does **not** require a key: the refusal belongs on the first message, not on the button that opens the page you are being told to configure |
| `GET` | `/api/chats` | List conversations, newest-touched first |
| `GET`/`DELETE` | `/api/chats/{id}` | Read one conversation with its turns and summary, or delete it and its turns |
| `POST` | `/api/chats/{id}/messages` | Say something and get the reply. Returns the whole chat, so there is one shape for "here is the conversation now" rather than a delta to splice. **409** if no usable key is on file or the chat is already finished; **502** if the provider would not answer |
| `POST` | `/api/chats/{id}/summarize` | Finish the conversation and write the three-part summary. **400** if nothing has been said. Running it again re-summarises, which is the retry path when the first attempt was poor |

`PATCH` bodies only need the fields being changed; omitted fields are left untouched.

### Chats and your API key

Chats run on a provider account you own. The key is stored encrypted with Fernet, under a key
derived from `JWT_SECRET` by HKDF — so there is no extra environment variable to set, and one
consequence worth knowing: **rotating `JWT_SECRET` makes every stored key undecryptable.** That is
already the documented way to sign everyone out. An unreadable key reads as "no key on file"
rather than an error, so the remedy is the same either way: paste it again.

Nothing sends the key back down. `GET /api/settings/provider` returns four characters of it, and a
provider error that quotes the key back has it scrubbed out before the 502 leaves the backend.

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

Frontend on `http://localhost:3700`, API on `http://localhost:8700`. Those host ports are a block
chosen not to collide with anything else on the machine; each is overridable (`FRONTEND_PORT`,
`BACKEND_PORT`) and only the host side moves, so the containers still listen on 3000 and 8000
internally. The backend entrypoint runs `alembic upgrade head` before uvicorn.

The database is **Neon**, not a container, so compose runs two services rather than three and
there is no local volume holding your data.

Configuration comes from `.env` at the repo root, which is gitignored. Copy the template first:

```bash
cp .env.example .env      # then fill in DATABASE_URL
```

It sets `DATABASE_URL`, the two host ports and the two secrets,
plus the three optional ranker switches (`HF_TOKEN`, `HF_MODEL`, `LADDER_RANKING`). Those three
have to go in this file to reach the container: `docker-compose.yml` forwards exactly the
variables it names into the backend's environment, and nothing else in `.env` crosses that
boundary. Setting `HF_TOKEN` only in your shell does nothing under compose.

Inside the compose network the frontend reaches the API at `http://backend:8000`. The database is
reached over the internet at the Neon host in `DATABASE_URL`, so the same URL works inside and
outside compose.

Use Neon's **direct** endpoint rather than the `-pooler` one. `entrypoint.sh` runs both
`alembic upgrade head` and uvicorn from this single variable, and migrations don't survive
PgBouncer's transaction pooling. Point dev and prod at different Neon **branches**.

> **Note:** `docker-compose.yml` used to assemble `DATABASE_URL` itself from `POSTGRES_*`, which
> silently overrode whatever `.env` said. It now passes `DATABASE_URL` straight through and fails
> to start if it is unset, so there is no way to end up pointed somewhere you didn't choose.

### Your first account

Registration is invite-only and there is no admin UI, so the first code comes from the CLI:

```bash
docker compose exec backend python -m app.cli issue-invite     # prints a code
```

Then register at `/register` with that code, or skip the invite entirely and create the account
from the same CLI, which is already the privileged path — it prompts for the password rather than
taking it as a flag, so it stays out of your shell history:

```bash
docker compose exec backend python -m app.cli create-user --email you@example.com
```

Notes written before there were accounts belong to a seeded `dev@example.com`. Move them across
once, then that user is gone:

```bash
docker compose exec backend python -m app.cli adopt-dev-data --email you@example.com
```

`list-invites` shows every code and whether it has been spent.

### Deploying

There is a production overlay. It is applied on top of the base file, never
instead of it:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

It publishes **only** Caddy, on 80 and 443. The base file exposes both
services on host ports, which is right on your own machine and wrong on a
public one. (The database is no longer among them: it lives on Neon, behind
Neon's own TLS and access control, rather than in a published container.)
Caddy terminates TLS
and obtains the certificate itself, which needs `DOMAIN` set to a name that
resolves to the machine, and both ports reachable so the ACME challenge can be
answered.

`ENVIRONMENT=production` comes with it, which turns off `/docs` and marks the
session cookie `Secure`. That flag is why the TLS is not optional: browsers
silently drop a `Secure` cookie sent over plain http, so without https login
appears to succeed and no session ever exists.

Nothing deploys automatically. CI publishes images to
`ghcr.io/ts-24/restyle-{backend,frontend}`, tagged `dev` and by commit sha; the
sha tag is the one worth pulling, since `dev` moves.

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
........................................................................ [100%]
243 passed in 10.62s
```

The suite runs against SQLite, so it needs neither Postgres nor any API key: the ranker is mocked,
and so is every provider call the chat feature makes. That is also why it is fast. For the same
reason it runs fine outside Docker, from any virtualenv with `requirements.txt` installed:

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

Because `conftest.py` builds the schema with `Base.metadata.create_all`, the suite never runs a
migration and a broken one would pass every test. CI's `migrations` job is the only thing that
catches that, and it round-trips upgrade → downgrade → upgrade against real Postgres.

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

- **No chat has spoken to a real model yet.** The plumbing is verified to the provider boundary
  and no further: with a deliberately invalid key it reaches Anthropic and returns a real 401, so
  decryption, client construction, the request and the error path all work — but an actual reply
  and an actual three-part summary have not been observed, because there was no key to observe
  them with. The OpenAI default model id is likewise unverified; the settings form lets you
  correct it in one field.
- **Chat replies arrive whole, not streamed.** A long answer is a long wait with nothing on screen
  but "Thinking…".
- **A finished chat is closed.** Summarising it refuses further turns, because a summary that no
  longer describes its conversation is worse than no summary.

- **There is no password reset and no way to change a password.** Losing one means a new account
  or an `UPDATE` by hand. Registration being invite-only is what makes that survivable for now.
- **There is no refresh flow.** Signing out revokes the token it was given, and only that one, so
  other sessions on the same account keep working — but a token nobody signs out stays valid for
  its full seven days. Rotating `JWT_SECRET` still invalidates every session at once.
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

`PROGRESS.md` carries the full open-items list and 34 documented traps that cost real time — read
it before touching the UI. It is current as of PR #34.
