"""
Tests for what the app exposes depending on its environment (main.py).

The interactive docs list every route, including the auth ones, to anyone who
reaches the host. That is exactly what you want while building and exactly
what you do not want in front of the internet, so the switch is worth a test:
it is the kind of setting that gets flipped back by accident and produces no
error when it is wrong.
"""

import importlib

import pytest


def build_app(monkeypatch, environment: str):
    """Re-import main with ENVIRONMENT set, since it is read at import time."""
    monkeypatch.setenv("ENVIRONMENT", environment)
    import main

    return importlib.reload(main).app


class TestDocsExposure:
    def test_development_serves_the_docs(self, monkeypatch):
        app = build_app(monkeypatch, "development")

        assert app.docs_url == "/docs"
        assert app.openapi_url == "/openapi.json"

    def test_production_serves_no_docs_and_no_schema(self, monkeypatch):
        app = build_app(monkeypatch, "production")

        # The schema matters as much as the page: /openapi.json is the same
        # map in a form that is easier to read.
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.openapi_url is None

    def test_anything_that_is_not_development_is_treated_as_production(self, monkeypatch):
        # Fail closed: a typo in the variable must not serve the docs.
        app = build_app(monkeypatch, "staging")

        assert app.openapi_url is None


@pytest.fixture(autouse=True)
def _restore_main(monkeypatch):
    """Leave main importable in its default state for every other test."""
    yield
    monkeypatch.setenv("ENVIRONMENT", "development")
    import main

    importlib.reload(main)


class TestTheLexiconIsGone:
    """
    The word ladder, its ranker, and the vocabulary analysis were all removed,
    so the surface they exposed has to go with them and the backend has to
    carry no lexicon at all.

    Read off `/openapi.json` rather than off a route table. `app.routes` holds
    six entries and `api_router.routes` nine `_IncludedRouter` objects, because
    this FastAPI flattens an included router only when the schema is built — so
    a check written against either passes whatever is mounted. The schema is
    also the honest target: it is the surface a caller actually sees.

    A status code would not do either. The ladder endpoint took a token but
    scoped nothing by it, so a leftover would serve WordNet to anyone holding
    any account, and a 404 assertion would pass just as well against a route
    that had merely started refusing.
    """

    def test_no_route_serves_a_lexicon(self, client):
        paths = client.get("/openapi.json").json()["paths"]

        stale = [
            path
            for path in paths
            if any(word in path for word in ("ladder", "analyze", "vocab", "/words"))
        ]
        assert not stale, sorted(paths)

    def test_the_services_behind_them_are_gone(self):
        import importlib.util

        for module in ("app.services.ranker", "app.services.vocab", "app.services.analysis"):
            assert importlib.util.find_spec(module) is None, module

    def test_no_lexicon_package_is_installed(self):
        # The point of the removal is the image and the resident memory, not
        # the routes: measured like-for-like, the backend image went 808MB to
        # 498MB and its resident memory 330MB to 60MB. A route can go while the
        # dependency stays, and that would buy nothing.
        #
        # `textstat` and `lemminflect` are here because they are how it nearly
        # did buy nothing: textstat requires nltk and pyphen, so dropping the
        # direct dependencies left both in the built image while this test —
        # reading a virtualenv they had been uninstalled from — still passed.
        import importlib.util

        for package in ("wordfreq", "nltk", "pyphen", "textstat", "lemminflect"):
            assert importlib.util.find_spec(package) is None, package

    def test_a_note_still_carries_no_words_field(self, client):
        created = client.post("/api/notes", json={"title": "T", "content": "c"})
        assert created.status_code == 201, created.text

        assert "words" not in created.json()

    def test_the_neighbours_still_serve(self, client):
        # Notes and chats share the app and the session but not a line of the
        # lexicon. If either broke, the removal reached too far. `/health` is
        # not checked here: it is declared on `main.app`, and the fixture
        # builds a bare app carrying only `api_router`.
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/notes" in paths
        assert "/api/chats" in paths

        assert client.get("/api/notes").status_code == 200
        assert client.get("/api/chats").status_code == 200
