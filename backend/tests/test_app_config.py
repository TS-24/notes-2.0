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
