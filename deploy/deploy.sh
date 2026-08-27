#!/bin/sh
# The only thing the deploy key is allowed to run.
#
# This lives on the server at /srv/restyle/deploy.sh and is named as a forced
# command in the deploy user's authorized_keys (see authorized_keys.example
# beside this file). That is what makes the key in GitHub's secrets narrow: it
# cannot open a shell, cannot read .env, cannot run anything but this. What it
# would otherwise be is a credential for arbitrary root-adjacent access to the
# machine holding everyone's notes, sitting in a web UI.
#
# The sha to deploy arrives in SSH_ORIGINAL_COMMAND, because a forced command
# replaces whatever the client asked for and puts the original there.

set -eu

# Ranges like [a-f] are collation-dependent: under most non-C locales they also
# match A-F, which made the check below accept an uppercase sha. Git shas are
# lowercase and so are the published tags, so this is belt and braces with the
# explicit enumeration in the case statement.
LC_ALL=C
export LC_ALL

ROOT=/srv/restyle
FILES="-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.deploy.yml"

TAG="${SSH_ORIGINAL_COMMAND:-}"

# The one place a value from outside reaches a command line, so it is checked
# rather than trusted: exactly forty lowercase hex characters and nothing else.
# Without this, the argument is an injection point into every command below.
case "$TAG" in
	"" | *[!0123456789abcdef]*)
		echo "refusing: expected a 40-character commit sha" >&2
		exit 1
		;;
esac
if [ "${#TAG}" -ne 40 ]; then
	echo "refusing: expected a 40-character commit sha" >&2
	exit 1
fi

cd "$ROOT"
export TAG

# What is running now, so a failure below has something to name. Absent on the
# very first deploy, which is why it is not an error.
PREVIOUS=$(cat "$ROOT/DEPLOYED" 2>/dev/null || echo "none")
echo "Deploying $TAG (previous: $PREVIOUS)"

# Pull first and separately. A failed pull should leave the running stack
# untouched rather than take it down and then discover the image is not there.
# shellcheck disable=SC2086
docker compose $FILES pull

# shellcheck disable=SC2086
docker compose $FILES up -d

# The stack is up; that is not the same as the app answering. Give it a moment
# to migrate and boot, then ask. entrypoint.sh runs alembic before uvicorn, so
# the first response can be some way off.
i=0
until [ "$i" -ge 30 ]; do
	# shellcheck disable=SC2086
	if docker compose $FILES exec -T backend python -c \
		"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)" \
		2>/dev/null; then
		echo "$TAG" >"$ROOT/DEPLOYED"
		echo "Deployed $TAG"
		# Keep a week of images so a rollback does not have to re-pull.
		docker image prune -f --filter "until=168h" >/dev/null 2>&1 || true
		exit 0
	fi
	i=$((i + 1))
	sleep 2
done

# Deliberately not an automatic rollback. Rolling back on its own would hide
# which deploy broke and could flap between two bad images; what the operator
# needs here is to be told, loudly, with the sha that was working.
echo "FAILED: $TAG is up but not answering /health after 60s" >&2
echo "Roll back with: TAG=$PREVIOUS (re-run the deploy workflow with that sha)" >&2
exit 1
