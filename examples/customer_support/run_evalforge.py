"""
End-to-end EvalForge example using the mock Phoenix server.

Run mock_phoenix.py first, then run this script.
"""

import asyncio
import os
import sys

# Make sure we can import evalforge from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Set a dummy Gemini key if not set (clustering will use sentence-transformers fallback)
if not os.environ.get("GEMINI_API_KEY"):
    print("Note: GEMINI_API_KEY not set. Using sentence-transformers for embeddings.")
    print("      Cluster labels and eval generation will be skipped.")
    print("      Set GEMINI_API_KEY for the full experience.\n")

from evalforge.agent.agent import run_pipeline


async def main():
    await run_pipeline(
        trace_limit=200,
        output_dir="./output",
        project_name="customer-support-agent",
    )


if __name__ == "__main__":
    asyncio.run(main())
