# Integrations

## Trace Sources

### Arize Phoenix (supported)

EvalForge reads traces from Phoenix via its REST API.

```bash
# Start Phoenix locally
pip install arize-phoenix
python -m phoenix.server.main serve

# Point EvalForge at it
PHOENIX_ENDPOINT=http://localhost:6006
```

For Arize Cloud:
```bash
PHOENIX_ENDPOINT=https://app.phoenix.arize.com
PHOENIX_API_KEY=your_key_here
```

### LangSmith (coming soon)

Track progress: [GitHub Issue #X]

### Langfuse (coming soon)

Track progress: [GitHub Issue #X]

---

## LLM Providers

### Google Gemini (default)

Used for embeddings, cluster labeling, eval generation, and judging.

```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-pro
```

### OpenAI (coming soon)

Will support GPT-4o as judge and text-embedding-3-small for embeddings.

---

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/eval.yml
name: Run Evals

on:
  push:
    branches: [main]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install evalforge
      - run: evalforge run --traces 200 --output ./eval-results
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          PHOENIX_ENDPOINT: ${{ secrets.PHOENIX_ENDPOINT }}
      - uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: eval-results/
```

---

## Export Formats

### CSV (`eval_dataset.csv`)

Ready to import into spreadsheets, Notion, or other eval tools.

```
case_id,cluster_label,input,expected_output,rubric
c1,billing,"What is the refund policy?","7-10 business days","[...]"
```

### JSON (`eval_dataset.json`)

Full structured data including rubric weights and source trace IDs.

### Judge Rubric (`judge_rubric.json`)

Map of cluster → judge prompt template. Use this in your own eval pipeline:

```python
import json

rubric = json.load(open("judge_rubric.json"))
billing_prompt = rubric["billing_questions"]["judge_prompt_template"]

# Fill in actual_output at runtime
prompt = billing_prompt.replace("{actual_output}", agent_response)
```

### Phoenix Dataset (coming soon)

Push the eval dataset back to Phoenix as a dataset for tracking over time.
