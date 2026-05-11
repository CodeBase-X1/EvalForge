<div align="center">

<img src="docs/assets/evalforge-banner.png" alt="EvalForge Banner" width="100%" />

# ⚒️ EvalForge

### Stop writing test cases by hand.

**EvalForge mines your production traffic and auto-generates a complete eval suite for your AI agent.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-7289da)](https://discord.gg/evalforge)
[![Stars](https://img.shields.io/github/stars/evalforge/evalforge?style=social)](https://github.com/evalforge/evalforge)

[**Quick Start**](#-quick-start) • [**How It Works**](#-how-it-works) • [**Demo**](#-demo) • [**Docs**](docs/) • [**Contributing**](CONTRIBUTING.md)

</div>

---

## The Problem

You built an AI agent. Before you ship an update, you want to test it. But test it against **what**?

You need an *eval dataset* — a collection of real questions with correct answers so you can measure if your agent is getting better or worse.

**Building this dataset is painful:**

- ✍️ Writing test cases by hand takes weeks
- 🎯 You might write the wrong test cases (not what real users actually ask)
- 📏 You have no idea if your rubric (scoring criteria) is correct
- 😬 Most small teams just skip evals entirely and pray

**Here's the thing:** If you have a production AI agent, you already have thousands of real user interactions sitting in your traces. EvalForge turns that gold mine into a complete eval dataset — automatically.

---

## ✨ How It Works

```
Your production traces in Phoenix (thousands of real conversations)
        ↓
EvalForge fetches them via Phoenix MCP
        ↓
Groups similar failures together
("these 50 cases all fail on pricing questions")
        ↓
For each failure cluster, generates:
  • Representative test questions
  • What the correct answer should be
  • A scoring rubric (how to judge good vs bad answers)
        ↓
Exports a complete eval dataset + LLM-as-judge config
        ↓
You can now run evals before every deployment ✅
```

---

## 🎬 Demo

> **2000 production traces → complete eval suite in under 3 minutes**

![EvalForge Demo](docs/assets/demo.gif)

**What EvalForge found in the demo:**

| Cluster | Failure Rate | Test Cases Generated |
|---|---|---|
| 💳 Billing questions | 83% | 12 cases |
| ❌ Cancellation flow | 71% | 10 cases |
| 💰 Pricing questions | 58% | 10 cases |
| ✨ Feature questions | 12% | 8 cases |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [Arize Phoenix](https://phoenix.arize.com/) running with production traces
- Google Gemini API key ([get one free](https://aistudio.google.com/))

### Installation

```bash
# Clone the repo
git clone https://github.com/evalforge/evalforge.git
cd evalforge

# Install dependencies
pip install -e ".[dev]"

# Copy and fill in your config
cp .env.example .env
```

### Configure

```bash
# .env
GEMINI_API_KEY=your_key_here
PHOENIX_ENDPOINT=http://localhost:6006   # or your hosted Phoenix URL
PHOENIX_API_KEY=your_phoenix_key         # if using Arize cloud
```

### Run

```bash
# Analyze your last 500 traces and generate an eval suite
evalforge run --traces 500 --output ./my_evals

# Or use the web UI
evalforge ui
```

That's it. EvalForge will output:

```
my_evals/
├── eval_dataset.csv       ← ready to use immediately
├── judge_rubric.json      ← LLM-as-judge config
├── report.html            ← visual breakdown
└── clusters/
    ├── billing.json
    ├── cancellation.json
    └── pricing.json
```

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────┐
│              PHOENIX (Arize)                         │
│    Thousands of production traces stored here        │
│    Each trace = one user conversation                │
└──────────────────────┬──────────────────────────────┘
                       │ EvalForge reads via Phoenix MCP
                       ↓
┌─────────────────────────────────────────────────────┐
│           STEP 1: TRACE FETCHER                      │
│  • Pulls last N traces from Phoenix                  │
│  • Extracts: input, output, latency, score           │
│  • Filters for low-quality traces (failures)         │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│           STEP 2: FAILURE CLUSTERER                  │
│  • Embeds each trace (Gemini embeddings)             │
│  • Groups similar failures together                  │
│  • Labels each cluster: "billing", "cancel", etc.   │
│  • Ranks clusters by failure rate                    │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│           STEP 3: EVAL GENERATOR (Gemini)            │
│  For each failure cluster, Gemini generates:         │
│  • 10 representative test questions                  │
│  • Ideal expected answers                            │
│  • Scoring rubric (what makes a good answer)         │
│  • LLM-as-judge prompt template                      │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│           STEP 4: EVAL RUNNER                        │
│  • Runs the eval dataset against your current agent  │
│  • Scores using LLM-as-judge (Gemini)               │
│  • Produces report: pass rate, failure breakdown     │
│  • Exports as CSV / JSON / Phoenix dataset           │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│              OUTPUT                                  │
│  eval_dataset.csv  ← ready to use immediately       │
│  judge_rubric.json ← LLM-as-judge config            │
│  report.html       ← visual breakdown               │
└─────────────────────────────────────────────────────┘
```

---

## 🧩 Key Concepts

<details>
<summary><b>What is an Eval Dataset?</b></summary>

A spreadsheet, basically. Three columns:

| Input Question | Expected Answer | Scoring Rubric |
|---|---|---|
| "What is refund policy?" | "7-10 business days" | Must mention specific days |
| "How do I cancel?" | "Go to Settings > Cancel" | Must give exact steps |
| "Is there a free trial?" | "Yes, 14 days" | Must say yes and duration |

When you update your agent, you run it against all these inputs and score how many it gets right.

</details>

<details>
<summary><b>What is LLM-as-a-Judge?</b></summary>

Instead of checking answers manually, you ask Gemini to score them.

```
"Here is the question, here is the ideal answer,
 here is what our agent said. Score it 1-10 and explain why."
```

Gemini scores it automatically. Run this on 1000 examples in seconds.

</details>

<details>
<summary><b>What is Clustering?</b></summary>

Grouping similar things together. EvalForge looks at thousands of traces and says:

- "These 200 traces are all about billing — and the agent fails 60% of them"
- "These 150 traces are about cancellation — agent fails 80% of them"
- "These 300 traces are about features — agent does great here"

Now you know exactly where to focus your evals.

</details>

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Agent Orchestration | [Google ADK](https://google.github.io/adk-docs/) |
| Trace Source | [Arize Phoenix](https://phoenix.arize.com/) via MCP |
| LLM | [Google Gemini](https://ai.google.dev/) |
| Embeddings | Gemini Embeddings / sentence-transformers |
| Clustering | scikit-learn (KMeans + DBSCAN) |
| UI | FastAPI + HTMX |
| Export | CSV, JSON, Phoenix Datasets |

---

## 📦 Project Structure

```
evalforge/
├── evalforge/
│   ├── agent/              # Google ADK agent + orchestration
│   │   ├── agent.py        # Main EvalForge agent
│   │   └── tools.py        # Agent tools
│   ├── core/
│   │   ├── fetcher.py      # Phoenix MCP trace fetcher
│   │   ├── clusterer.py    # Embedding + clustering logic
│   │   ├── generator.py    # Gemini eval generation
│   │   └── runner.py       # Eval runner + LLM-as-judge
│   ├── ui/
│   │   ├── app.py          # FastAPI web app
│   │   └── templates/      # HTML templates
│   └── exporters/
│       ├── csv_exporter.py
│       ├── json_exporter.py
│       └── phoenix_exporter.py
├── tests/
├── docs/
├── examples/
│   └── customer_support/   # Full working example
├── pyproject.toml
└── README.md
```

---

## 🤝 Contributing

EvalForge is built for the community. Contributions are very welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Good first issues:**
- [ ] Add support for LangSmith traces
- [ ] Add OpenAI as judge model option
- [ ] Add Slack notification on eval completion
- [ ] Improve cluster labeling accuracy

---

## 🗺️ Roadmap

- [x] Phoenix MCP integration
- [x] Gemini-powered eval generation
- [x] Clustering + failure analysis
- [x] LLM-as-judge scoring
- [x] Web UI
- [ ] LangSmith support
- [ ] Langfuse support
- [ ] GitHub Actions integration
- [ ] VS Code extension
- [ ] Eval versioning + history

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

<div align="center">

**If EvalForge saves you time, give it a ⭐ — it helps others find it.**

[Report Bug](https://github.com/evalforge/evalforge/issues) • [Request Feature](https://github.com/evalforge/evalforge/issues) • [Join Discord](https://discord.gg/evalforge)

</div>
