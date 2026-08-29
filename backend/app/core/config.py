"""
Auth configuration, read from the environment at import time.

`JWT_SECRET` deliberately has no fallback, for the same reason DATABASE_URL
does not (see db/database.py): a default signing key is not a convenience, it
is a skeleton key. Anyone who can read this file could mint a token for any
account on any deployment that forgot to set the variable. Failing loudly at
import is the only safe behaviour.
"""

import os
from datetime import timedelta

JWT_SECRET = os.environ["JWT_SECRET"]

# HS256 keys shorter than the hash they feed are the weak point of an otherwise
# sound scheme, and PyJWT only warns. A short secret is guessable offline from
# any single token the holder ever sees, so refuse it outright.
if len(JWT_SECRET.encode()) < 32:
    raise RuntimeError(
        "JWT_SECRET must be at least 32 bytes; generate one with "
        "`python -c 'import secrets; print(secrets.token_urlsafe(48))'`"
    )

JWT_ALGORITHM = "HS256"

# One service signs and verifies, so a symmetric key is the right shape. There
# is no refresh flow: the token simply expires and you log in again. A stolen
# token stays valid until then, which is the tradeoff taken in exchange for
# having no revocation table to keep.
ACCESS_TOKEN_TTL = timedelta(days=7)

# Browsers silently drop a Secure cookie sent over plain http, which presents
# as a login that appears to succeed and a session that never exists. So this
# has to follow the environment rather than being hardcoded true.
COOKIE_SECURE = os.environ.get("ENVIRONMENT", "development") != "development"

COOKIE_NAME = "restyle_token"

# --- Password reset -------------------------------------------------------------
#
# A reset link is single-use and short-lived: an hour is long enough to walk
# from the email to the browser and no longer a standing key if the mailbox is
# later compromised.
RESET_TOKEN_TTL = timedelta(hours=1)

# The origin the reset link points at. This server never serves the page — the
# React Router app does — so the link has to name that host explicitly. Same
# default as main.py's CORS origin; set FRONTEND_ORIGIN in the deployed env.
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3700")

# --- Outbound email -----------------------------------------------------------
#
# All optional. With SMTP_HOST unset the mailer logs the message instead of
# sending it, which is what keeps the test suite and a bare `docker compose up`
# working without credentials — see app/services/email.py. Read with .get(), not
# [], because app.core.config is imported before any of these are guaranteed set
# (conftest.py only sets DATABASE_URL and JWT_SECRET).
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", "Restyle <no-reply@localhost>")
# STARTTLS is right for the common submission port 587; a local catcher like
# Mailpit speaks plain, so this can be switched off.
SMTP_STARTTLS = os.environ.get("SMTP_STARTTLS", "true").lower() != "false"
