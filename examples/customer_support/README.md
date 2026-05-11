# Customer Support Agent — EvalForge Example

This example shows how to use EvalForge with a customer support AI agent.

## What's in this example

- `mock_phoenix.py` — A mock Phoenix server that returns realistic customer support traces
- `agent.py` — A simple customer support agent (the thing being evaluated)
- `run_evalforge.py` — End-to-end script that runs EvalForge on the mock traces

## Run it

```bash
# From the repo root
cd examples/customer_support

# Start the mock Phoenix server
python mock_phoenix.py &

# Run EvalForge against it
python run_evalforge.py
```

## What you'll see

EvalForge will:
1. Fetch 100 mock traces from the local Phoenix server
2. Find ~3-4 failure clusters (billing, cancellation, pricing, etc.)
3. Generate 30-40 eval cases with rubrics
4. Save everything to `./output/`

This is a great way to understand EvalForge before connecting it to your real Phoenix instance.
