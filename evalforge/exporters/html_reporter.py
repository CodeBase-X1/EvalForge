"""Generate a self-contained HTML report from eval results."""

from __future__ import annotations

import json
from pathlib import Path

from evalforge.models import Cluster, EvalResult, PipelineReport, ScoreLevel

_REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>EvalForge Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0f172a; color: #e2e8f0; padding: 2rem; }}
    h1 {{ font-size: 2rem; font-weight: 700; margin-bottom: 0.25rem; }}
    .subtitle {{ color: #94a3b8; margin-bottom: 2rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
             gap: 1rem; margin-bottom: 2rem; }}
    .card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; }}
    .card .value {{ font-size: 2.5rem; font-weight: 700; }}
    .card .label {{ color: #94a3b8; font-size: 0.875rem; margin-top: 0.25rem; }}
    .pass {{ color: #4ade80; }}
    .partial {{ color: #facc15; }}
    .fail {{ color: #f87171; }}
    .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 2rem; }}
    .chart-card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; }}
    .chart-card h2 {{ font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #94a3b8; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b;
             border-radius: 12px; overflow: hidden; }}
    th {{ background: #0f172a; padding: 0.75rem 1rem; text-align: left;
          font-size: 0.75rem; text-transform: uppercase; color: #64748b; }}
    td {{ padding: 0.75rem 1rem; border-top: 1px solid #334155; font-size: 0.875rem; }}
    tr:hover td {{ background: #263148; }}
    .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px;
              font-size: 0.75rem; font-weight: 600; }}
    .badge-pass {{ background: #14532d; color: #4ade80; }}
    .badge-partial {{ background: #713f12; color: #facc15; }}
    .badge-fail {{ background: #7f1d1d; color: #f87171; }}
    .score-bar {{ display: flex; align-items: center; gap: 0.5rem; }}
    .bar {{ height: 6px; border-radius: 3px; background: #334155; flex: 1; }}
    .bar-fill {{ height: 100%; border-radius: 3px; }}
    @media (max-width: 768px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <h1>⚒️ EvalForge Report</h1>
  <p class="subtitle">Run ID: {run_id} &nbsp;·&nbsp; {timestamp} &nbsp;·&nbsp;
     {traces_analyzed} traces analyzed</p>

  <div class="grid">
    <div class="card">
      <div class="value">{eval_cases_generated}</div>
      <div class="label">Eval Cases Generated</div>
    </div>
    <div class="card">
      <div class="value">{clusters_found}</div>
      <div class="label">Failure Clusters Found</div>
    </div>
    <div class="card">
      <div class="value {pass_class}">{pass_rate}</div>
      <div class="label">Overall Pass Rate</div>
    </div>
    <div class="card">
      <div class="value">{avg_score}</div>
      <div class="label">Avg Judge Score (/ 10)</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-card">
      <h2>Failure Rate by Cluster</h2>
      <canvas id="clusterChart"></canvas>
    </div>
    <div class="chart-card">
      <h2>Eval Results Distribution</h2>
      <canvas id="resultChart"></canvas>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Cluster</th>
        <th>Input</th>
        <th>Score</th>
        <th>Result</th>
        <th>Reasoning</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>

  <script>
    const clusterData = {cluster_data};
    const resultData = {result_data};

    new Chart(document.getElementById("clusterChart"), {{
      type: "bar",
      data: {{
        labels: clusterData.labels,
        datasets: [{{
          label: "Failure Rate",
          data: clusterData.values,
          backgroundColor: clusterData.values.map(v =>
            v > 0.7 ? "#f87171" : v > 0.4 ? "#facc15" : "#4ade80"
          ),
          borderRadius: 6,
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          y: {{ beginAtZero: true, max: 1, ticks: {{ format: "percent", color: "#94a3b8" }},
               grid: {{ color: "#1e293b" }} }},
          x: {{ ticks: {{ color: "#94a3b8" }}, grid: {{ display: false }} }}
        }}
      }}
    }});

    new Chart(document.getElementById("resultChart"), {{
      type: "doughnut",
      data: {{
        labels: ["Pass", "Partial", "Fail"],
        datasets: [{{
          data: [resultData.pass, resultData.partial, resultData.fail],
          backgroundColor: ["#4ade80", "#facc15", "#f87171"],
          borderWidth: 0,
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ labels: {{ color: "#e2e8f0" }} }}
        }}
      }}
    }});
  </script>
</body>
</html>
"""

_ROW_TEMPLATE = """\
<tr>
  <td><span class="badge" style="background:#1e3a5f;color:#93c5fd">{cluster}</span></td>
  <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
      title="{input_full}">{input_short}</td>
  <td>
    <div class="score-bar">
      <span>{score:.1f}</span>
      <div class="bar"><div class="bar-fill" style="width:{bar_pct}%;background:{bar_color}"></div></div>
    </div>
  </td>
  <td><span class="badge badge-{level}">{level}</span></td>
  <td style="max-width:400px;color:#94a3b8;font-size:0.8rem">{reasoning}</td>
</tr>
"""


def generate_report(
    report: PipelineReport,
    results: list[EvalResult],
    clusters: list[Cluster],
    path: str | Path,
) -> Path:
    """Generate a self-contained HTML report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Summary stats
    total = len(results)
    passed = sum(1 for r in results if r.level == ScoreLevel.PASS)
    partial = sum(1 for r in results if r.level == ScoreLevel.PARTIAL)
    failed = sum(1 for r in results if r.level == ScoreLevel.FAIL)
    avg_score = sum(r.score for r in results) / total if total else 0
    pass_rate = passed / total if total else 0

    pass_class = "pass" if pass_rate >= 0.7 else ("partial" if pass_rate >= 0.4 else "fail")

    # Cluster chart data
    cluster_data = json.dumps(
        {
            "labels": [c.label for c in clusters],
            "values": [round(c.failure_rate, 3) for c in clusters],
        }
    )
    result_data = json.dumps({"pass": passed, "partial": partial, "fail": failed})

    # Table rows
    rows = ""
    for r in results:
        bar_pct = r.score * 10
        bar_color = "#4ade80" if r.score >= 7 else ("#facc15" if r.score >= 4 else "#f87171")
        rows += _ROW_TEMPLATE.format(
            cluster=r.cluster_label,
            input_full=r.input.replace('"', "&quot;"),
            input_short=r.input[:80] + ("…" if len(r.input) > 80 else ""),
            score=r.score,
            bar_pct=bar_pct,
            bar_color=bar_color,
            level=r.level.value,
            reasoning=r.judge_reasoning[:200],
        )

    html = _REPORT_TEMPLATE.format(
        run_id=report.run_id[:8],
        timestamp=report.timestamp.strftime("%Y-%m-%d %H:%M UTC"),
        traces_analyzed=report.traces_analyzed,
        eval_cases_generated=report.eval_cases_generated,
        clusters_found=report.clusters_found,
        pass_rate=f"{pass_rate:.0%}",
        pass_class=pass_class,
        avg_score=f"{avg_score:.1f}",
        cluster_data=cluster_data,
        result_data=result_data,
        rows=rows,
    )

    path.write_text(html, encoding="utf-8")
    return path
