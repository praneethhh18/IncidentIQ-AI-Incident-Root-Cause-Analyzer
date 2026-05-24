"""
Demo helper: pushes realistic-looking RecipeAI errors into Datadog so
IncidentIQ has something to react to during the rehearsal.

Why this exists
---------------
RecipeAI (https://recipeai-three.vercel.app) is a third-party site we
don't own, so we can't wire a Datadog SDK into its frontend or backend.
For the demo we simulate the same wire-format Datadog would receive
from a real RecipeAI deployment - the HTTP intake doesn't care whether
the events come from the actual app or from this script, they show up
identically in the Logs Explorer and in IncidentIQ.

Run it once just before clicking Analyze in IncidentIQ. It bursts a
60-second window of related errors that look like a recipe-search
timeout cascade caused by an upstream embedding service.

Usage
-----
    set DD_API_KEY=<your datadog api key>
    set DD_SITE=us5.datadoghq.com            # optional, defaults to us5
    python scripts/demo_emit_recipeai.py     # default scenario
    python scripts/demo_emit_recipeai.py timeout   # named scenario

After it finishes, in IncidentIQ:
  1. Settings -> paste the same Datadog API + App key + site
  2. Dashboard -> Datadog tab -> Service: pick "recipe-ai"
  3. Window: 30 -> click Analyze. Root cause + timeline in ~3 seconds.

The script is intentionally dependency-free (uses only urllib) so the
demo machine doesn't need anything beyond Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# A scripted RecipeAI incident: a recipe-search request starts timing
# out because the embedding service is slow; a fallback kicks in; a
# downstream cart service starts 502-ing because the timeouts back up
# its connection pool. Realistic-looking but entirely fictional.
SCENARIOS: dict[str, list[dict]] = {
    "timeout": [
        {
            "ddsource": "python",
            "service": "recipe-ai",
            "ddtags": "env:prod,version:1.4.2",
            "hostname": "recipeai-web-1",
            "status": "warn",
            "message": (
                "embeddings.client took 1842ms for /v1/embed "
                "(threshold 800ms) - cohere upstream lagging"
            ),
        },
        {
            "ddsource": "python",
            "service": "recipe-ai",
            "ddtags": "env:prod,version:1.4.2",
            "hostname": "recipeai-web-2",
            "status": "error",
            "message": (
                "RecipeSearchTimeout: vector search for 'paneer butter masala' "
                "exceeded 3000ms budget (embeddings=1842ms, faiss=1310ms)"
            ),
        },
        {
            "ddsource": "python",
            "service": "recipe-ai",
            "ddtags": "env:prod,version:1.4.2",
            "hostname": "recipeai-web-1",
            "status": "error",
            "message": (
                "fallback to keyword search succeeded after 2106ms - "
                "users seeing 2.5-3s response times (p95 SLO is 800ms)"
            ),
        },
        {
            "ddsource": "node",
            "service": "recipe-ai-cart",
            "ddtags": "env:prod,version:0.9.7",
            "hostname": "cart-svc-3",
            "status": "warn",
            "message": (
                "connection pool exhausted (32/32) - recipe-ai requests "
                "holding sockets past timeout"
            ),
        },
        {
            "ddsource": "node",
            "service": "recipe-ai-cart",
            "ddtags": "env:prod,version:0.9.7",
            "hostname": "cart-svc-3",
            "status": "error",
            "message": (
                "502 Bad Gateway from /api/cart/add - upstream recipe-ai "
                "did not respond within 5000ms"
            ),
        },
        {
            "ddsource": "python",
            "service": "recipe-ai",
            "ddtags": "env:prod,version:1.4.2",
            "hostname": "recipeai-web-2",
            "status": "error",
            "message": (
                "EmbeddingsClient.embed: cohere returned 503 Service Unavailable "
                "after 4 retries (backoff capped at 1500ms total)"
            ),
        },
        {
            "ddsource": "python",
            "service": "recipe-ai",
            "ddtags": "env:prod,version:1.4.2",
            "hostname": "recipeai-web-1",
            "status": "error",
            "message": (
                "RecipeSearchTimeout: 9 consecutive failures, circuit breaker "
                "opening for embeddings.cohere for 30s"
            ),
        },
    ],
}


def post_logs(api_key: str, site: str, batch: list[dict]) -> None:
    """Push a batch of log events to Datadog's HTTP intake."""
    url = f"https://http-intake.logs.{site}/api/v2/logs"
    body = json.dumps(batch).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "DD-API-KEY": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
            print(f"  -> HTTP {resp.status}  ({len(batch)} events sent)")
    except urllib.error.HTTPError as exc:
        print(f"  !! Datadog rejected the batch: HTTP {exc.code} {exc.reason}")
        print(f"     {exc.read().decode('utf-8', errors='replace')[:200]}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"  !! Network error: {exc}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("Usage")[0].strip())
    parser.add_argument(
        "scenario",
        nargs="?",
        default="timeout",
        choices=sorted(SCENARIOS.keys()),
        help="Which incident pattern to emit (default: timeout)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to wait between events (default 0 - burst all at once)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("DD_API_KEY") or os.environ.get("DATADOG_API_KEY")
    if not api_key:
        print("ERROR: set DD_API_KEY (or DATADOG_API_KEY) in your environment.")
        sys.exit(2)
    site = (
        os.environ.get("DD_SITE")
        or os.environ.get("DATADOG_SITE")
        or "us5.datadoghq.com"
    )

    events = SCENARIOS[args.scenario]
    print(f"Emitting {len(events)} '{args.scenario}' events to {site} ...")

    if args.delay <= 0:
        # Burst: timestamps are spread across the past 60s so the
        # timeline in IncidentIQ looks like a real cascade, not a
        # single tick. We assign timestamps in code; Datadog accepts
        # explicit `date` fields on the intake.
        from datetime import timedelta

        anchor = datetime.now(timezone.utc) - timedelta(seconds=60)
        for i, ev in enumerate(events):
            ev["date"] = (anchor + timedelta(seconds=i * 8)).isoformat()
        post_logs(api_key, site, events)
    else:
        for i, ev in enumerate(events):
            ev["date"] = now_iso()
            post_logs(api_key, site, [ev])
            if i < len(events) - 1:
                time.sleep(args.delay)

    print(
        "\nDone. Datadog usually surfaces events in the Logs Explorer "
        "within 5-15 seconds.\n"
        "In IncidentIQ:\n"
        "  Dashboard -> Datadog tab -> Service: recipe-ai -> Window: 30 -> Analyze."
    )


if __name__ == "__main__":
    main()
