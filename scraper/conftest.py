"""Configuration pytest partagée."""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests nécessitant une base PostgreSQL active (docker compose up -d db)",
    )
