"""
Mock Phoenix server for the customer support example.

Serves realistic-looking traces at /v1/spans so you can run EvalForge
without a real Phoenix instance.

Run with:
    python mock_phoenix.py
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# ── Synthetic trace data ──────────────────────────────────────────────────────

TRACE_TEMPLATES = [
    # Billing failures (high failure rate)
    {
        "cluster": "billing",
        "inputs": [
            "When will I get my refund?",
            "I was charged twice, what do I do?",
            "How long does a refund take?",
            "My invoice shows the wrong amount",
            "Can I get a refund for last month?",
            "I cancelled but still got charged",
            "What payment methods do you accept?",
            "How do I update my billing info?",
        ],
        "outputs": [
            "I'm not sure about refund timelines.",
            "Please contact support for billing issues.",
            "I don't have information about that.",
            "You'll need to check with our billing team.",
        ],
        "failure_rate": 0.75,
    },
    # Cancellation failures
    {
        "cluster": "cancellation",
        "inputs": [
            "How do I cancel my subscription?",
            "I want to cancel my account",
            "How do I stop my subscription?",
            "Can I pause instead of cancel?",
            "What happens to my data if I cancel?",
            "Is there a cancellation fee?",
        ],
        "outputs": [
            "To cancel, go to Settings.",
            "I'm not sure how to cancel.",
            "Please contact support to cancel.",
            "You can cancel from your account page.",
        ],
        "failure_rate": 0.60,
    },
    # Pricing questions (medium failure rate)
    {
        "cluster": "pricing",
        "inputs": [
            "How much does the pro plan cost?",
            "What's included in the free tier?",
            "Is there a discount for annual billing?",
            "Do you offer student pricing?",
            "What's the difference between plans?",
        ],
        "outputs": [
            "Our pricing starts at $29/month.",
            "I don't have current pricing information.",
            "Please check our pricing page.",
            "The pro plan is $49/month.",
        ],
        "failure_rate": 0.45,
    },
    # Feature questions (low failure rate — agent does well here)
    {
        "cluster": "features",
        "inputs": [
            "Does your product support SSO?",
            "Can I export my data?",
            "Is there an API available?",
            "Do you have a mobile app?",
            "Can I integrate with Slack?",
            "Does it work with Zapier?",
        ],
        "outputs": [
            "Yes, we support SSO via SAML 2.0.",
            "You can export your data as CSV or JSON.",
            "Yes, we have a REST API with full documentation.",
            "We have iOS and Android apps.",
            "Yes, our Slack integration is available in the app store.",
        ],
        "failure_rate": 0.10,
    },
]


def generate_traces(n: int = 100) -> list[dict]:
    traces = []
    now = datetime.now(tz=timezone.utc)

    for i in range(n):
        template = random.choice(TRACE_TEMPLATES)
        is_failure = random.random() < template["failure_rate"]
        score = random.uniform(0.0, 0.45) if is_failure else random.uniform(0.6, 1.0)

        trace_id = str(uuid.uuid4()).replace("-", "")
        span_id = str(uuid.uuid4()).replace("-", "")[:16]
        timestamp = now - timedelta(hours=random.randint(0, 72))

        traces.append(
            {
                "id": span_id,
                "traceId": trace_id,
                "startTime": timestamp.isoformat(),
                "latencyMs": random.uniform(200, 3000),
                "statusCode": "OK",
                "attributes": {
                    "input.value": random.choice(template["inputs"]),
                    "output.value": random.choice(template["outputs"]),
                    "openinference.span.kind": "CHAIN",
                },
                "spanAnnotations": [{"score": round(score, 3), "label": "quality"}],
                "project": {"name": "customer-support-agent"},
            }
        )

    return traces


class MockPhoenixHandler(BaseHTTPRequestHandler):
    _traces = generate_traces(200)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/healthz":
            self._respond(200, {"status": "ok"})

        elif parsed.path == "/v1/spans":
            params = parse_qs(parsed.query)
            limit = int(params.get("limit", ["100"])[0])
            traces = self._traces[:limit]
            self._respond(200, {"data": traces})

        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass  # suppress default logging


if __name__ == "__main__":
    server = HTTPServer(("localhost", 6006), MockPhoenixHandler)
    print("Mock Phoenix running at http://localhost:6006")
    print("Press Ctrl+C to stop")
    server.serve_forever()
