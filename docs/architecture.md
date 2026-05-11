# EvalForge Architecture

## Overview

EvalForge is a 4-step pipeline that transforms production traces into a complete eval dataset.

```
Phoenix Traces → Cluster Failures → Generate Evals → Export Dataset
```

## Components

### 1. Trace Fetcher (`evalforge/core/fetcher.py`)

Connects to Arize Phoenix via its REST API (`/v1/spans`). Extracts:
- Input text (user question)
- Output text (agent response)
- Score/annotation (quality signal)
- Latency and metadata

**Filtering:** Traces with score below `EVALFORGE_FAILURE_THRESHOLD` (default 0.5) are
considered failures and passed to the clusterer.

### 2. Failure Clusterer (`evalforge/core/clusterer.py`)

Groups similar failing traces together using semantic embeddings.

**Embedding:** Uses Gemini `text-embedding-004` by default. Falls back to
`sentence-transformers/all-MiniLM-L6-v2` if no Gemini API key is set.

**Clustering:** KMeans with L2-normalized embeddings (approximates cosine similarity).
If `num_clusters=0`, auto-detects k by maximizing silhouette score over k=2..sqrt(n).

**Labeling:** Sends 5 representative inputs from each cluster to Gemini and asks for
a short topic label (e.g., "billing_questions", "cancellation_flow").

### 3. Eval Generator (`evalforge/core/generator.py`)

For each cluster, sends a structured prompt to Gemini asking it to generate:
- N representative test questions (varied phrasings, edge cases)
- Ideal expected answers (specific, not vague)
- Scoring rubric (3-5 concrete, checkable criteria)
- Ready-to-use LLM-as-judge prompt template

Uses `response_mime_type: application/json` to get structured output reliably.

### 4. Eval Runner (`evalforge/core/runner.py`)

Runs eval cases against an agent and scores responses using LLM-as-a-judge.

**Scoring:** Sends the question, ideal answer, rubric, and actual answer to Gemini.
Gemini returns a score (0-10) and reasoning.

**Levels:**
- Pass: score ≥ 7
- Partial: score ≥ 4
- Fail: score < 4

**Concurrency:** Runs up to N eval cases in parallel (default 5) using asyncio semaphores.

## Agent Orchestration

The Google ADK agent (`evalforge/agent/agent.py`) wraps the pipeline steps as tools
and orchestrates them conversationally. This lets you run EvalForge interactively
or integrate it into a larger agent workflow.

## Web UI

FastAPI + HTMX (`evalforge/ui/app.py`). The pipeline runs in a background task;
the frontend polls `/api/status` every 1.5 seconds for live updates.

## Data Flow

```
Trace (raw Phoenix span)
  → filtered to failures
  → embedded (Gemini / sentence-transformers)
  → clustered (KMeans)
  → labeled (Gemini)
  → Cluster objects

Cluster
  → prompt to Gemini
  → EvalCase objects (input + expected_output + rubric + judge_prompt)

EvalCase + agent response
  → judge prompt to Gemini
  → EvalResult (score + level + reasoning)

EvalResult[]
  → CSV / JSON / HTML report
```
