"""Tests for configuration loading."""

from __future__ import annotations

import os
from unittest.mock import patch


class TestSettings:
    def test_defaults(self):
        from evalforge.config import Settings

        s = Settings()
        assert s.phoenix_endpoint == "http://localhost:6006"
        assert s.gemini_model == "gemini-2.0-flash"
        assert s.evalforge_trace_limit == 500
        assert s.evalforge_failure_threshold == 0.5
        assert s.evalforge_cases_per_cluster == 10

    def test_env_override(self):
        from evalforge.config import Settings

        with patch.dict(os.environ, {"EVALFORGE_TRACE_LIMIT": "999"}):
            s = Settings()
            assert s.evalforge_trace_limit == 999

    def test_phoenix_endpoint_override(self):
        from evalforge.config import Settings

        with patch.dict(os.environ, {"PHOENIX_ENDPOINT": "http://myhost:9000"}):
            s = Settings()
            assert s.phoenix_endpoint == "http://myhost:9000"

    def test_failure_threshold_range(self):
        from evalforge.config import Settings

        s = Settings()
        assert 0.0 <= s.evalforge_failure_threshold <= 1.0
