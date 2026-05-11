# Changelog

All notable changes to EvalForge will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
EvalForge uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned
- LangSmith trace source support
- Langfuse trace source support
- GitHub Actions integration
- VS Code extension
- Eval versioning and history

## [0.1.0] — 2024-01-01

### Added
- Phoenix MCP trace fetcher
- Embedding-based failure clustering (Gemini + sentence-transformers fallback)
- Auto-detection of optimal cluster count via silhouette score
- Gemini-powered eval case generation (questions + expected answers + rubrics)
- LLM-as-a-judge scoring with Gemini
- CSV, JSON, and HTML report exporters
- FastAPI + HTMX web UI with live pipeline status
- Google ADK agent orchestration
- CLI (`evalforge run`, `evalforge ui`, `evalforge status`)
- Customer support example with mock Phoenix server
