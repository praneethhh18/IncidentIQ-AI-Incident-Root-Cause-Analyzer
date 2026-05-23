"""Tools available to the IncidentIQ agent.

Each tool is a deterministic function the agent can call mid-analysis to
gather more evidence, correlate data, or pivot its hypothesis. The agent
chooses which tools to invoke based on what the logs reveal.

Tools intentionally operate on inputs the model can derive from the prompt
(log slices, service names, time windows). They keep the agent grounded
in observable evidence rather than letting it hallucinate.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List

from app.services.store import AnalysisStore, get_store


SERVICE_RE = re.compile(r"\b([a-z][a-z0-9-]{2,30}(?:-(?:api|svc|worker|service|gateway|db|cache|queue)))\b")
ISO_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b")
ERROR_LEVEL_RE = re.compile(r"\b(FATAL|ERROR|WARN|WARNING)\b", re.IGNORECASE)
ERROR_KEYWORDS = [
    "oom", "outofmemory", "memory", "leak", "deadlock", "timeout",
    "exhausted", "refused", "unreachable", "circuit breaker",
    "failover", "panic", "crashloopbackoff", "503", "504", "500",
    "5xx", "throttl", "rate limit", "saturat",
]


def extract_entities(logs: str) -> Dict[str, Any]:
    """TOOL: pull services, timestamps, error levels, and signature keywords."""
    services = sorted(set(SERVICE_RE.findall(logs.lower())))
    timestamps = ISO_TS_RE.findall(logs)
    levels = Counter(m.upper() for m in ERROR_LEVEL_RE.findall(logs))
    hits = [k for k in ERROR_KEYWORDS if k in logs.lower()]
    return {
        "services": services[:12],
        "level_counts": dict(levels),
        "signature_keywords": hits[:10],
        "first_timestamp": timestamps[0] if timestamps else None,
        "last_timestamp": timestamps[-1] if timestamps else None,
        "log_lines": logs.count("\n") + 1,
    }


def search_logs(logs: str, pattern: str, max_matches: int = 6) -> Dict[str, Any]:
    """TOOL: grep the supplied log payload for a regex, return matched lines."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return {"pattern": pattern, "error": f"invalid regex: {exc}", "matches": []}

    matches: List[str] = []
    for line in logs.splitlines():
        if regex.search(line):
            matches.append(line.strip())
            if len(matches) >= max_matches:
                break
    return {"pattern": pattern, "matches": matches, "total": len(matches)}


def correlate_timeline(logs: str, max_events: int = 8) -> Dict[str, Any]:
    """TOOL: pull WARN/ERROR/FATAL log lines in chronological order."""
    rows: List[Dict[str, str]] = []
    for line in logs.splitlines():
        ts_match = ISO_TS_RE.search(line)
        lvl_match = ERROR_LEVEL_RE.search(line)
        if not ts_match or not lvl_match:
            continue
        try:
            ts_iso = ts_match.group(0)
            ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "level": lvl_match.group(0).upper(),
                "text": line.strip()[:240],
            }
        )

    rows.sort(key=lambda r: r["timestamp"])
    return {
        "events": rows[:max_events],
        "total_significant_events": len(rows),
    }


def service_dependency_hints(services: List[str]) -> Dict[str, Any]:
    """TOOL: lightweight inference of likely service roles from names."""
    role_map: Dict[str, List[str]] = defaultdict(list)
    for service in services:
        s = service.lower()
        if any(x in s for x in ("db", "postgres", "mysql", "rds", "aurora")):
            role_map["database"].append(service)
        elif any(x in s for x in ("redis", "cache", "memcached")):
            role_map["cache"].append(service)
        elif any(x in s for x in ("gateway", "proxy", "ingress", "lb")):
            role_map["gateway"].append(service)
        elif any(x in s for x in ("worker", "queue", "kafka", "consumer")):
            role_map["worker"].append(service)
        elif s.endswith("-api"):
            role_map["api"].append(service)
        elif s.endswith(("-svc", "-service")):
            role_map["service"].append(service)
        else:
            role_map["unknown"].append(service)
    return {"roles": dict(role_map), "service_count": len(services)}


def trace_origin(logs: str) -> Dict[str, Any]:
    """FORENSIC TOOL: find patient zero — the earliest abnormal signal.

    Walks the log timeline in order, returns the first WARN/ERROR/FATAL
    event together with the gap to the first ERROR/FATAL (time-to-impact).
    This is the "where did the cascade start" answer.
    """
    earliest_warn: Dict[str, Any] | None = None
    earliest_error: Dict[str, Any] | None = None

    for line in logs.splitlines():
        ts_match = ISO_TS_RE.search(line)
        lvl_match = ERROR_LEVEL_RE.search(line)
        if not ts_match or not lvl_match:
            continue
        try:
            ts = datetime.fromisoformat(ts_match.group(0).replace("Z", "+00:00"))
        except ValueError:
            continue

        level = lvl_match.group(0).upper()
        event = {"timestamp": ts.isoformat(), "level": level, "text": line.strip()[:240]}

        if level in ("WARN", "WARNING") and earliest_warn is None:
            earliest_warn = event
        if level in ("ERROR", "FATAL") and earliest_error is None:
            earliest_error = event
        if earliest_warn and earliest_error:
            break

    patient_zero = earliest_warn or earliest_error
    detection: Dict[str, Any] = {"event": patient_zero, "minutes_to_impact": None}
    if earliest_warn and earliest_error:
        try:
            t0 = datetime.fromisoformat(earliest_warn["timestamp"])
            t1 = datetime.fromisoformat(earliest_error["timestamp"])
            delta = (t1 - t0).total_seconds() / 60.0
            detection["minutes_to_impact"] = round(delta, 1)
            detection["first_user_visible_error"] = earliest_error
        except ValueError:
            pass

    return detection


def compute_blast_radius(
    services: List[str],
    roles: Dict[str, List[str]] | None = None,
    log_entities: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """FORENSIC TOOL: catalog every entity the incident touched.

    Combines the service inventory, role classification, and signal
    keywords into a typed blast-radius list (services, dependencies,
    user-facing surfaces).
    """
    roles = roles or {}
    log_entities = log_entities or {}
    entities: List[Dict[str, str]] = []

    role_lookup: Dict[str, str] = {}
    for role, svcs in roles.items():
        for svc in svcs:
            role_lookup[svc] = role

    for svc in services:
        kind = "service"
        role = role_lookup.get(svc, "service")
        if role in ("database", "cache"):
            kind = "dependency"
        impact = f"Touched as {role}"
        entities.append({"kind": kind, "name": svc, "role": role, "impact": impact})

    # Infer user-facing surfaces from signal keywords
    keywords = log_entities.get("signature_keywords") or []
    if any(k in keywords for k in ("503", "504", "500", "5xx")):
        entities.append(
            {
                "kind": "user_segment",
                "name": "All authenticated users",
                "role": "user_segment",
                "impact": "Receiving 5xx responses on critical paths",
            }
        )
    if "throttl" in keywords or "rate limit" in keywords:
        entities.append(
            {
                "kind": "user_segment",
                "name": "Heavy-traffic clients",
                "role": "user_segment",
                "impact": "Being throttled or rate-limited",
            }
        )
    if "failover" in keywords:
        entities.append(
            {
                "kind": "region",
                "name": "Primary region",
                "role": "region",
                "impact": "Active failover in progress",
            }
        )

    return {"entities": entities, "total": len(entities)}


def infer_trigger(log_entities: Dict[str, Any], logs: str) -> Dict[str, Any]:
    """FORENSIC TOOL: hypothesize what event birthed patient zero.

    Looks for deploy / config-change / scale-event / dependency-failure
    fingerprints in the log payload. Returns the strongest hypothesis
    with a confidence score.
    """
    lowered = logs.lower()
    keywords = log_entities.get("signature_keywords") or []

    candidates: List[Dict[str, Any]] = []

    if any(k in lowered for k in ("deploy", "rollout", "revision", "rev=", "git:")):
        candidates.append(
            {
                "trigger": "Recent deploy / rollout",
                "evidence": "Deploy or revision marker found in the logs.",
                "confidence": 0.70,
            }
        )
    if any(k in lowered for k in ("config reload", "config change", "configmap", "feature flag")):
        candidates.append(
            {
                "trigger": "Config / feature-flag change",
                "evidence": "Config-change indicator in the logs.",
                "confidence": 0.65,
            }
        )
    if any(k in lowered for k in ("scale", "hpa", "scaling", "replica count", "node added")):
        candidates.append(
            {
                "trigger": "Scaling event (HPA / cluster autoscaler)",
                "evidence": "Scaling activity present in the telemetry.",
                "confidence": 0.55,
            }
        )
    if "failover" in keywords or "clusterdown" in keywords:
        candidates.append(
            {
                "trigger": "Upstream dependency failure (failover / cluster down)",
                "evidence": "Dependency-level failover or unavailability detected.",
                "confidence": 0.75,
            }
        )
    if "exhausted" in keywords or "pool exhausted" in lowered:
        candidates.append(
            {
                "trigger": "Resource exhaustion under sustained load",
                "evidence": "Pool/queue exhaustion appears without an upstream trigger.",
                "confidence": 0.60,
            }
        )
    if "oom" in keywords or "outofmemory" in keywords:
        candidates.append(
            {
                "trigger": "Memory pressure with no eviction policy",
                "evidence": "OOM / heap-exhaustion signal in the logs.",
                "confidence": 0.65,
            }
        )

    if not candidates:
        return {
            "trigger": "Unknown — telemetry doesn't include a clear precipitating event",
            "evidence": "No deploy / config / scaling / dependency signals found.",
            "confidence": 0.30,
        }

    # Pick the highest-confidence candidate
    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates[0]


def query_similar_incidents(signature: str, limit: int = 3) -> Dict[str, Any]:
    """TOOL: look up past analyses whose root cause / title overlaps with the signature."""
    store: AnalysisStore = get_store()
    needle = signature.lower()
    if not needle.strip():
        return {"matches": []}

    hits: List[Dict[str, str]] = []
    for summary in store.list_recent(limit=50):
        haystack = f"{summary.title} {summary.root_cause}".lower()
        # crude scoring: count overlapping tokens
        tokens = [t for t in re.split(r"[^a-z0-9]+", needle) if len(t) > 3]
        score = sum(1 for token in tokens if token in haystack)
        if score:
            hits.append(
                {
                    "incident_id": summary.incident_id,
                    "title": summary.title,
                    "severity": summary.severity.value,
                    "score": str(score),
                }
            )
    hits.sort(key=lambda h: int(h["score"]), reverse=True)
    return {"matches": hits[:limit]}


# Tool registry — keeps the public surface explicit.
TOOLS = {
    "extract_entities": extract_entities,
    "search_logs": search_logs,
    "correlate_timeline": correlate_timeline,
    "service_dependency_hints": service_dependency_hints,
    "query_similar_incidents": query_similar_incidents,
    "trace_origin": trace_origin,
    "compute_blast_radius": compute_blast_radius,
    "infer_trigger": infer_trigger,
}


TOOL_CATALOG = [
    {
        "name": "extract_entities",
        "purpose": "Inventory services, error levels, signature keywords, and time bounds from raw logs.",
    },
    {
        "name": "search_logs",
        "purpose": "Regex grep against the log payload to test a specific hypothesis.",
    },
    {
        "name": "correlate_timeline",
        "purpose": "Order WARN/ERROR/FATAL events chronologically so cascade direction is visible.",
    },
    {
        "name": "service_dependency_hints",
        "purpose": "Infer probable roles (api / db / cache / worker / gateway) from service names.",
    },
    {
        "name": "query_similar_incidents",
        "purpose": "Search the local incident history for past analyses that match the error signature.",
    },
    {
        "name": "trace_origin",
        "purpose": "Forensic: find patient zero — the earliest abnormal signal that started the cascade.",
    },
    {
        "name": "compute_blast_radius",
        "purpose": "Forensic: enumerate every entity (services, dependencies, user segments) the incident touched.",
    },
    {
        "name": "infer_trigger",
        "purpose": "Forensic: hypothesize the precipitating event (deploy / config / scaling / dependency) that birthed patient zero.",
    },
]
