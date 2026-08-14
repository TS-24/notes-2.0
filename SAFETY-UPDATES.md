# Safety updates — active log

Running record of secret, credential and environment checks on this repo. Append
a dated entry each time you run one. Do not rewrite old entries: a check that was
clean in the past and dirty now is the signal worth keeping.

Every claim here should be a command someone else can re-run. If an entry has no
command output behind it, mark it unverified.

---

## 2026-08-04

Full sweep of env files, ignore rules and the backend venv. Repo is public and
`.env` is in history, so the standing rule below still applies.

### Standing: the Postgres password in git history is burned

`.env` was tracked before `bf9d899` and this repo is public. Commit `03786d2`
rotated the password and dropped the hardcoded fallback, but **the old value is
still reachable in history** — removing it properly needs `git filter-repo`,
which has not been done. It is a throwaway pointing at `localhost`. Never reuse
it anywhere.

### Env files — clean

| Check | Result |
|---|---|
| `.env` tracked? | No. Ignored by `.gitignore:7`. |
| `.env` permissions | `-rw-------` (600, owner only). |
| `.env` contents | Four Postgres vars plus `DATABASE_URL`. No API keys, no tokens. |
| `.env.example` tracked? | Yes, correctly — placeholders are `change-me`. |

```
$ git ls-files | grep -Ei 'env|venv'
.env.example
backend/alembic/env.py

$ git check-ignore -v .env backend/venv
.gitignore:7:.env	backend/.env
.gitignore:15:venv/	backend/venv

$ ls -l .env
-rw-------@ 1 tshin  staff  302 Aug  3 12:25 .env
```

Nothing sensitive is tracked. `alembic/env.py` is an Alembic source file, not a
dotfile — the grep matches its name only.

### Ignore-file encoding — clean

The UTF-16 trap (PROGRESS.md §4) recurs silently: git reports no error, the
patterns just stop matching. Re-check after **any** edit to a `.gitignore`.

```
$ git ls-files '*.gitignore' | xargs file
.gitignore:          ASCII text
notes2.0/.gitignore: ASCII text
```

Both ASCII. Good.

### `backend/venv` — ignored, but cannot run the app

Correctly untracked (`.gitignore:15`) and the interpreter works (Python
3.12.13), so this is a **hygiene pass, not a safety failure**. It is unusable
for running the backend:

```
$ backend/venv/bin/python -c "import main"
ModuleNotFoundError: No module named 'fastapi'
```

Only 16 packages are installed. `fastapi`, `uvicorn`, `SQLAlchemy`, `alembic`
and `pytest` are all absent. It is the scratch env for
`app/services/run_once.py` — the only importer of `wn` and `defusedxml` — not a
stale backend env.

Deferred to PROGRESS.md §7 item 9a: rebuilding means
`venv/bin/pip install -r requirements.txt`, which pulls torch and transformers.
Skipped deliberately while on a metered connection.

### `requirements.txt` — left alone, deliberately

Unchanged. It describes what the Docker image installs (`Dockerfile:4,11`) and
nothing else, which is the right scope for it.

Two edits were considered and both rejected:

- **A full `pip freeze` of the venv.** The freeze has no fastapi, uvicorn,
  SQLAlchemy or alembic, so it would have broken the image build outright.
- **Additively declaring the venv's extras** (`wn`, `defusedxml`, and an
  `nltk` bump to 3.10.0). Tempting, but those are `run_once.py`'s dependencies,
  and that script is now ignored scratch — putting its deps in the app's
  production manifest would ship packages the image has no use for, and pin
  `nltk` to whatever a throwaway venv happened to have.

**Rule this settles:** `requirements.txt` tracks the app. Scratch scripts bring
their own environment and are not entitled to a line in it.

**Resolved — both drivers are wanted, there is no conflict.** The manifest pins
`psycopg2-binary==2.9.12` while the venv has `psycopg` 3.3.4, which looks like a
clash and is not one. `app/db/database.py:12` passes a bare `postgresql://` URL
to `create_engine`, and SQLAlchemy resolves that scheme to psycopg2, so the pin
is correct for the app. `run_once.py:1` imports psycopg 3 directly for itself.

### `app/services/run_once.py` — ignored as scratch

A one-shot WordNet loader, never wired into the app. Now matched by
`.gitignore` rather than committed. Two notes for anyone who finds it:

- Line 5's connection string is the literal placeholder `"postgresql://..."`.
  No credential in it, which is the only reason ignoring it is safe rather than
  merely convenient.
- It has no `__main__` guard, so *importing* it runs the full load against
  whatever `psycopg.connect` resolves to. Do not import it to "see what it
  does."
