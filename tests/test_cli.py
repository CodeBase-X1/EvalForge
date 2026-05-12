"""Tests for the CLI."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from evalforge.cli import app

runner = CliRunner()


class TestCli:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "evalforge" in result.output
        assert re.search(r"\b\d+\.\d+\.\d+\b", result.output)

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "ui" in result.output
        assert "status" in result.output

    def test_run_help(self):
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--traces" in result.output
        assert "--output" in result.output

    def test_ui_help(self):
        result = runner.invoke(app, ["ui", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.output

    def test_status_help(self):
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0

    def test_run_fails_without_api_key(self):
        """run command should exit with error if GEMINI_API_KEY is not set."""
        import os
        from unittest.mock import patch

        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = runner.invoke(app, ["run", "--traces", "10"])
        assert result.exit_code == 1
        assert "GEMINI_API_KEY" in result.output
