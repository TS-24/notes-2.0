# Notes 2.0 📝

A note-taking app that doubles as a vocabulary builder. You write notes the way you would in
Google Keep; the backend reads them, picks out the words it judges difficult, looks up
definitions, and turns them into flashcard-style quizzes you can mark as "known".

## 🌟 Features

**Working today**

- **Masonry note grid** — a Pinterest-style layout (`masonic`) with pinned notes in their own
  section, backed by browser `localStorage`.
- **Vocabulary extraction & quiz mode** — click a note to see the difficult words it contains
  with definitions, or open quiz mode to step through them one at a time and dismiss the ones
  you already know.
- **Animated UI** — spring-physics transitions throughout (`framer-motion`) on sidebars, note
  expansion, and card hovers.
- **Smart note creation** — a minimal expanding text-bar inspired by modern search interfaces.

**Built but not yet connected** — the persistence layer described under
[Backend](#backend-backend) below. Notes still live in `localStorage`; see
[Project status](#-project-status) for what remains.

## 🏗️ Architecture (Monorepo)

```
notes-2.0/
├── notes2.0/            # Frontend (React Router v7 + Vite)
├── backend/             # API + persistence (FastAPI + SQLAlchemy)
│   ├── main.py          # App entrypoint: CORS, /health, router wiring
│   ├── app/
│   │   ├── api/         # FastAPI routers (users, notes, words)
│   │   ├── crud/        # Database operations
│   │   ├── db/          # SQLAlchemy models + session factory
│   │   ├── schemas/     # Pydantic request/response models
│   │   └── services/    # NLP / vocabulary analysis
│   └── alembic/         # Database migrations
├── docker-compose.yml   # Frontend + PostgreSQL
├── agent.md             # Agent guidelines and architectural notes
└── README.md            # This file
```

### Tech Stack

**Frontend (`notes2.0/`)**
- **Framework:** React Router v7 (Vite), React 19
- **Language:** TypeScript
- **Styling:** Tailwind CSS v4 + `shadcn/ui` and Base UI components
- **Animations:** Framer Motion
- **Layout:** Masonic (masonry grid)

**Backend (`backend/`)**
- **Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL 15 via SQLAlchemy 2.0 ORM, migrations with Alembic
- **NLP / Analysis:** NLTK (`nltk`) and TextStat (`textstat`)

### Data model

Three tables. A user owns many notes; notes and word definitions are linked many-to-many
through a `note_word` association table, so one definition is shared across every note that
uses the word.

```
User ──< Note >──note_word──< WordDefinition
```

Deleting a user cascades to their notes. Deleting a note or a word only removes the link
between them, never the row on the other side.

## 🔌 API

All routes are prefixed with `/api`. Interactive docs are served at `/docs` once running.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness check (not under `/api`) |
| `POST` | `/api/users` | Create a user (409 if the email is taken) |
| `GET` | `/api/users` | List users (`skip`, `limit`) |
| `GET`/`PATCH`/`DELETE` | `/api/users/{id}` | Read, partially update, or delete a user |
| `POST` | `/api/notes` | Create a note (404 if the owner doesn't exist) |
| `GET` | `/api/notes` | List notes, optionally filtered by `?user_id=` |
| `GET`/`PATCH`/`DELETE` | `/api/notes/{id}` | Read, partially update, or delete a note |
| `POST`/`DELETE` | `/api/notes/{id}/words/{word_id}` | Link or unlink a word and a note |
| `POST` | `/api/words` | Create a word definition |
| `GET` | `/api/words` | List definitions, or look one up with `?word=` |
| `GET`/`PATCH`/`DELETE` | `/api/words/{id}` | Read, partially update, or delete a definition |

`PATCH` bodies only need the fields being changed; omitted fields are left untouched.

## 🚀 Getting Started

### 1. Database

The quickest path is the PostgreSQL service in `docker-compose.yml`:

```bash
docker compose up -d db
```

Configuration comes from `.env` at the repo root (`POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`, `POSTGRES_PORT`, and the `DATABASE_URL` the backend reads).

> **Note:** the defaults in `docker-compose.yml` and the values in `.env` differ — compose
> falls back to password `postgres`, while `.env` sets `mysecretpassword`. Since compose reads
> `.env`, the file wins; just don't rely on the inline defaults.

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head            # see the caveat in Project status first
uvicorn main:app --reload --port 8000
```

The API listens on `http://127.0.0.1:8000`, with docs at `http://127.0.0.1:8000/docs`.

### 3. Frontend

```bash
cd notes2.0
npm install
npm run dev
```

Available at `http://localhost:5173`. The frontend calls the backend at
`http://127.0.0.1:8000`, so start the API first if you want vocabulary features to work.

### Running with Docker

`docker compose up` builds the frontend (served on port 3000) alongside PostgreSQL. The
`backend` service is still commented out in `docker-compose.yml`; enabling it also means
pointing `DATABASE_URL` at host `db` rather than `localhost`, since containers don't share the
host's loopback.

## 📌 Project status

The frontend and the backend are each working, but they are not yet talking to each other. Be
aware of the following before picking up work:

- **Notes are still `localStorage`-only.** The persistence API above exists and is tested, but
  nothing in the frontend calls it yet. Wiring the note grid to `/api/notes` is the main
  remaining task.
- **The frontend calls two endpoints that no longer exist.** `notegrid.tsx` and
  `analytics.tsx` post to `/api/analyze/vocabulary` and `/api/words/known`, which were dropped
  when the backend was restructured. Vocabulary and quiz features will fail against the current
  API until these are reimplemented in `app/services/vocab.py` and exposed as routes.
- **The Alembic migrations are stale.** They still describe an older one-to-many schema — they
  give `word_definitions` a `user_id` and `note_id`, and never create the `note_word` table that
  `app/db/models.py` now relies on. `alembic upgrade head` therefore produces a schema the ORM
  cannot use; the migrations need regenerating against the current models.
- **`backend/venv/` is committed to the repo** and its interpreter is not portable across
  machines. Create your own virtualenv as shown above rather than using it. Relatedly, there is
  no `__pycache__` entry in `.gitignore`, so compiled files are tracked.
