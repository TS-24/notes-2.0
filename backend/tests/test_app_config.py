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


class TestTheLadderIsGone:
    """
    The word ladder and its hosted ranker were removed, so the surface they
    exposed has to go with them.

    Read off `/openapi.json` rather than off a route table. `app.routes` holds
    six entries and `api_router.routes` nine `_IncludedRouter` objects, because
    this FastAPI flattens an included router only when the schema is built — so
    a check written against either passes whatever is mounted. The schema is
    also the honest target: it is the surface a caller actually sees.

    A status code would not do either. The endpoint took a token but scoped
    nothing by it, so a leftover would serve WordNet to anyone holding any
    account, and a 404 assertion would pass just as well against a route that
    had merely started refusing.
    """

    def test_no_route_serves_a_ladder(self, client):
        paths = client.get("/openapi.json").json()["paths"]

        assert not [path for path in paths if "ladder" in path], sorted(paths)

    def test_the_vocabulary_analysis_it_shared_code_with_survives(self, client):
        # `difficulty` moved out of the ladder's service rather than going with
        # it. This is the endpoint that would notice if it had been taken too.
        paths = client.get("/openapi.json").json()["paths"]

        assert "/api/analyze/vocabulary" in paths

    def test_the_deployment_asks_for_no_hosted_model_token(self):
        # `ranker.py` was the only thing that ran on the deployment's own
        # credentials. Everything else that reaches a model runs on a key the
        # reader supplied, so nothing should import the client any more.
        import importlib.util

        assert importlib.util.find_spec("app.services.ranker") is None
