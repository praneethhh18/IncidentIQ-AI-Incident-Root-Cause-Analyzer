"""Seeded demo incidents.

These power three things:

  1. The "Try a sample incident" buttons on the dashboard.
  2. The fallback root-cause analysis when AWS Bedrock is not configured.
  3. The seeded integration log streams when Datadog / Grafana / New Relic
     are not configured.

Each demo is hand-crafted to look like a real production failure pattern.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from app.models import (
    AffectedService,
    AnalyzeResponse,
    BlastRadiusEntity,
    FixRecommendation,
    ForensicReport,
    Severity,
    SourceKind,
    TimelineEvent,
)


# ── Raw log fixtures ──────────────────────────────────────────────────────

CASCADING_FAILURE_LOGS = """\
2026-05-23T02:58:12.014Z INFO  checkout-api      Request POST /api/v1/checkout user=u_4831 latency=120ms status=200
2026-05-23T02:58:31.481Z WARN  checkout-api      Postgres pool getConnection waited 1.8s host=db-primary.internal pool=writer
2026-05-23T02:58:47.902Z WARN  payments-worker   Redis cluster slot moved key=order:lock:u_5512 → node-3 (was node-1)
2026-05-23T02:59:11.220Z ERROR checkout-api      Postgres pool exhausted: 200/200 connections in use, 47 waiting
2026-05-23T02:59:14.553Z ERROR checkout-api      Request POST /api/v1/checkout user=u_5512 status=503 took 30012ms (pool timeout)
2026-05-23T02:59:18.117Z ERROR payments-worker   Failed to acquire order lock — Redis CLUSTERDOWN: The cluster is down
2026-05-23T02:59:24.901Z WARN  api-gateway       Upstream checkout-api 5xx rate 38% over last 1m
2026-05-23T02:59:41.336Z ERROR notifications-svc Worker queue backlog 14,217 messages (threshold 2,000)
2026-05-23T03:00:02.812Z ERROR checkout-api      Circuit breaker OPENED for upstream: payments-worker (50/50 fails)
2026-05-23T03:00:14.504Z FATAL payments-worker   Out of memory: heap=512MiB rss=731MiB, killing process
2026-05-23T03:00:15.118Z INFO  k8s/payments      Pod payments-worker-7f8d6c-rfk2x CrashLoopBackOff (restart 3)
2026-05-23T03:00:39.221Z ERROR api-gateway       SLO burn: error_rate=42% target=0.5% (84x budget burn)
"""


MEMORY_LEAK_LOGS = """\
2026-05-22T14:02:11Z INFO  recommendations-svc Pod started rev=git:8a1f2b3 heap_limit=1024MiB
2026-05-22T15:30:22Z WARN  recommendations-svc Heap usage 612MiB (60%) — GC pause 240ms
2026-05-22T16:48:11Z WARN  recommendations-svc Heap usage 812MiB (79%) — GC pause 520ms p99 latency 1.4s
2026-05-22T17:22:08Z WARN  recommendations-svc Heap usage 905MiB (88%) — Full GC pause 1.2s p99 latency 3.1s
2026-05-22T17:51:30Z ERROR recommendations-svc java.lang.OutOfMemoryError: Java heap space
2026-05-22T17:51:30Z ERROR recommendations-svc   at c.acme.reco.UserSimilarityCache.put(UserSimilarityCache.java:148)
2026-05-22T17:51:30Z ERROR recommendations-svc   at c.acme.reco.RecommendationService.warm(RecommendationService.java:73)
2026-05-22T17:51:31Z INFO  k8s/recommendations Pod recommendations-svc-6c4-x9k OOMKilled, restarting (5th restart in 4h)
2026-05-22T17:51:45Z WARN  api-gateway         Recommendations endpoint returning fallback (cached) for 18% of users
"""


DB_OUTAGE_LOGS = """\
2026-05-23T08:14:02Z INFO  orders-api        DB connection established host=rds-orders-prod.cluster-abc.us-east-1.rds.amazonaws.com
2026-05-23T08:42:11Z WARN  orders-api        SlowQuery 4.2s SELECT * FROM orders WHERE user_id=$1 ORDER BY created_at DESC
2026-05-23T08:42:54Z WARN  orders-api        SlowQuery 6.7s SELECT * FROM order_items WHERE order_id IN (...)
2026-05-23T08:43:18Z ERROR orders-api        Postgres connection lost: server closed the connection unexpectedly
2026-05-23T08:43:18Z ERROR orders-api        Failover detected: writer endpoint switched to rds-orders-prod-2
2026-05-23T08:43:42Z ERROR orders-api        503 — could not get connection, pool exhausted during failover
2026-05-23T08:44:01Z WARN  orders-api        Replica lag 18.4s (threshold 5s) — read-after-write inconsistencies likely
2026-05-23T08:44:09Z ERROR inventory-svc     Stale read detected: order #91823 status=pending but payment captured 14s ago
"""


# ── Pre-computed analyses ─────────────────────────────────────────────────


def _now_minus(minutes: int = 0, seconds: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes, seconds=seconds)


def cascading_failure_demo() -> AnalyzeResponse:
    base = _now_minus(minutes=2)
    return AnalyzeResponse(
        title="Cascading checkout failure — DB pool exhaustion → Redis cluster down",
        summary=(
            "A Postgres writer connection pool spike on checkout-api caused request "
            "queueing, which back-pressured payments-worker. As payments-worker piled "
            "up retries it exhausted the Redis cluster, which in turn OOM-killed the "
            "worker. Within ~110 seconds the api-gateway tripped its circuit breaker, "
            "pushing user-facing error rates to 42% and burning 84x the SLO budget."
        ),
        root_cause=(
            "Postgres writer connection pool on checkout-api exhausted (200/200) "
            "due to a long-running query holding connections, triggering a "
            "downstream cascade through Redis and payments-worker."
        ),
        confidence=0.92,
        severity=Severity.P1,
        severity_rationale=(
            "User-visible checkout failure at 42% error rate with active SLO burn — "
            "this is revenue-impacting and customer-visible. P1 by definition."
        ),
        affected_services=[
            AffectedService(
                name="checkout-api",
                role="api",
                impact="503 responses on POST /api/v1/checkout, 42% error rate",
                health="down",
            ),
            AffectedService(
                name="payments-worker",
                role="worker",
                impact="OOM-killed, CrashLoopBackOff (3 restarts)",
                health="down",
            ),
            AffectedService(
                name="db-primary (Postgres writer)",
                role="database",
                impact="Connection pool fully saturated, 47 callers waiting",
                health="degraded",
            ),
            AffectedService(
                name="redis-cluster",
                role="cache",
                impact="CLUSTERDOWN — slot migration in flight",
                health="down",
            ),
            AffectedService(
                name="api-gateway",
                role="gateway",
                impact="Circuit breaker open to checkout-api, SLO burn 84x",
                health="degraded",
            ),
        ],
        timeline=[
            TimelineEvent(
                timestamp=base,
                label="DB pool pressure begins",
                detail="checkout-api requests start waiting 1.8s for Postgres connections.",
                severity=Severity.P3,
            ),
            TimelineEvent(
                timestamp=base + timedelta(seconds=35),
                label="Redis slot migration",
                detail="payments-worker reports Redis slot moved from node-1 to node-3.",
                severity=Severity.P3,
            ),
            TimelineEvent(
                timestamp=base + timedelta(seconds=59),
                label="Pool exhausted",
                detail="checkout-api Postgres pool fully saturated, requests timing out.",
                severity=Severity.P2,
            ),
            TimelineEvent(
                timestamp=base + timedelta(seconds=66),
                label="Redis CLUSTERDOWN",
                detail="payments-worker can no longer acquire order locks.",
                severity=Severity.P1,
            ),
            TimelineEvent(
                timestamp=base + timedelta(seconds=110),
                label="Circuit breaker opens",
                detail="api-gateway opens breaker on checkout-api after 50/50 fails.",
                severity=Severity.P1,
            ),
            TimelineEvent(
                timestamp=base + timedelta(seconds=122),
                label="payments-worker OOM",
                detail="Process killed (heap=512MiB, rss=731MiB), CrashLoopBackOff begins.",
                severity=Severity.P1,
            ),
        ],
        fixes=[
            FixRecommendation(
                priority=1,
                title="Kill the long-running writer query and add a statement timeout",
                rationale=(
                    "The pool didn't grow — connections are being held. A bounded "
                    "statement_timeout prevents one slow query from starving the pool."
                ),
                action="Identify the blocking query, terminate it, then enforce a 5s statement timeout.",
                snippet=(
                    "-- find blockers\nSELECT pid, age(clock_timestamp(), query_start), query\n"
                    "FROM pg_stat_activity\nWHERE state = 'active' AND query_start < now() - interval '10s'\n"
                    "ORDER BY query_start;\n\n-- terminate the offender\nSELECT pg_terminate_backend(<pid>);\n\n"
                    "-- enforce going forward\nALTER ROLE checkout_api SET statement_timeout = '5s';"
                ),
            ),
            FixRecommendation(
                priority=2,
                title="Wait out the Redis cluster reshard, then validate slot map",
                rationale=(
                    "CLUSTERDOWN during slot migration is transient. Forcing a failover "
                    "now risks data loss; wait, then verify."
                ),
                action="Let MOVED responses propagate; verify with CLUSTER INFO and CLUSTER SLOTS.",
                snippet="redis-cli -c -h <host> CLUSTER INFO\nredis-cli -c -h <host> CLUSTER SLOTS",
            ),
            FixRecommendation(
                priority=3,
                title="Lower payments-worker concurrency until pool recovers",
                rationale=(
                    "The worker is retrying aggressively, amplifying load. Reducing "
                    "concurrency lets the database catch up before scale-out."
                ),
                action="Scale payments-worker replicas from 8 → 4 and reduce per-pod concurrency from 32 → 8.",
                snippet="kubectl scale deploy/payments-worker --replicas=4\nkubectl set env deploy/payments-worker WORKER_CONCURRENCY=8",
            ),
            FixRecommendation(
                priority=4,
                title="Raise payments-worker memory limit and add OOM alerting",
                rationale=(
                    "Heap reached 512MiB then RSS 731MiB — the limit is tight for "
                    "current traffic. Add an alert before OOMKilled fires."
                ),
                action="Raise pod memory limit to 1Gi, add a >85% heap alert with 5-min window.",
                snippet=(
                    "resources:\n  limits:\n    memory: 1Gi\n  requests:\n    memory: 768Mi"
                ),
            ),
        ],
        evidence=[
            "ERROR checkout-api Postgres pool exhausted: 200/200 connections in use, 47 waiting",
            "ERROR payments-worker Failed to acquire order lock — Redis CLUSTERDOWN: The cluster is down",
            "ERROR checkout-api Circuit breaker OPENED for upstream: payments-worker (50/50 fails)",
            "FATAL payments-worker Out of memory: heap=512MiB rss=731MiB, killing process",
            "ERROR api-gateway SLO burn: error_rate=42% target=0.5% (84x budget burn)",
        ],
        source=SourceKind.DEMO,
        model="demo",
        forensic=ForensicReport(
            patient_zero=TimelineEvent(
                timestamp=base,
                label="Patient zero — first connection wait",
                detail=(
                    "checkout-api logged Postgres pool getConnection waited 1.8s "
                    "on db-primary.internal — the first abnormal signal before any "
                    "user-visible failure."
                ),
                severity=Severity.P3,
            ),
            propagation_path=[
                "db-primary (Postgres)",
                "checkout-api",
                "payments-worker",
                "redis-cluster",
                "api-gateway",
                "end users",
            ],
            blast_radius=[
                BlastRadiusEntity(
                    kind="service",
                    name="checkout-api",
                    impact="Pool exhausted, 503s on POST /api/v1/checkout",
                    severity=Severity.P1,
                ),
                BlastRadiusEntity(
                    kind="service",
                    name="payments-worker",
                    impact="OOM-killed, CrashLoopBackOff (3 restarts)",
                    severity=Severity.P1,
                ),
                BlastRadiusEntity(
                    kind="dependency",
                    name="db-primary (Postgres writer)",
                    impact="Connection pool fully saturated, 47 callers waiting",
                    severity=Severity.P2,
                ),
                BlastRadiusEntity(
                    kind="dependency",
                    name="redis-cluster",
                    impact="CLUSTERDOWN during slot migration",
                    severity=Severity.P1,
                ),
                BlastRadiusEntity(
                    kind="service",
                    name="api-gateway",
                    impact="Circuit breaker open, SLO burn 84x",
                    severity=Severity.P2,
                ),
                BlastRadiusEntity(
                    kind="user_segment",
                    name="All checkout users",
                    impact="42% of POST /api/v1/checkout requests failing with 503",
                    severity=Severity.P1,
                ),
                BlastRadiusEntity(
                    kind="user_segment",
                    name="Notification recipients",
                    impact="14k queued notifications backlogged",
                    severity=Severity.P3,
                ),
            ],
            trigger_hypothesis=(
                "Long-running writer query on db-primary held connections past the "
                "pool's idle timeout, starving new requests. The Redis slot migration "
                "happened concurrently but is symptom, not cause — the database "
                "pressure is what birthed patient zero."
            ),
            trigger_confidence=0.78,
            minutes_to_detection=1,
        ),
    )


def memory_leak_demo() -> AnalyzeResponse:
    base = _now_minus(minutes=240)
    return AnalyzeResponse(
        title="recommendations-svc OOMKilled — UserSimilarityCache unbounded growth",
        summary=(
            "recommendations-svc has been OOMKilled five times over 4 hours. Heap "
            "usage climbs linearly from start-up until a Full GC pause crosses the "
            "1-second mark, at which point an OOM terminates the process. Stack "
            "traces consistently point at UserSimilarityCache.put — an in-memory "
            "cache without eviction."
        ),
        root_cause=(
            "UserSimilarityCache has no max-size or TTL, so cached entries grow "
            "unbounded with active user IDs until the JVM heap is exhausted."
        ),
        confidence=0.88,
        severity=Severity.P2,
        severity_rationale=(
            "User-visible degradation (18% of users on fallback recommendations) "
            "but no full outage and a graceful fallback is in place. P2."
        ),
        affected_services=[
            AffectedService(
                name="recommendations-svc",
                role="api",
                impact="OOMKilled every ~50 minutes, 18% of users see fallback",
                health="degraded",
            ),
            AffectedService(
                name="api-gateway",
                role="gateway",
                impact="Serving cached fallback for recommendations endpoint",
                health="degraded",
            ),
        ],
        timeline=[
            TimelineEvent(
                timestamp=base,
                label="Pod started",
                detail="recommendations-svc came up on revision 8a1f2b3, heap limit 1024MiB.",
                severity=Severity.P3,
            ),
            TimelineEvent(
                timestamp=base + timedelta(minutes=88),
                label="Heap at 60%",
                detail="GC pauses growing to 240ms — first warning sign.",
                severity=Severity.P3,
            ),
            TimelineEvent(
                timestamp=base + timedelta(minutes=166),
                label="Heap at 79%",
                detail="GC pause hits 520ms, p99 latency degrades to 1.4s.",
                severity=Severity.P2,
            ),
            TimelineEvent(
                timestamp=base + timedelta(minutes=200),
                label="Heap at 88%",
                detail="Full GC pause 1.2s, p99 latency 3.1s.",
                severity=Severity.P2,
            ),
            TimelineEvent(
                timestamp=base + timedelta(minutes=229),
                label="OOM thrown",
                detail="java.lang.OutOfMemoryError at UserSimilarityCache.put.",
                severity=Severity.P1,
            ),
        ],
        fixes=[
            FixRecommendation(
                priority=1,
                title="Bound UserSimilarityCache with a Caffeine cache (size + TTL)",
                rationale=(
                    "An in-process cache without an eviction policy will always grow "
                    "to fill available memory. Caffeine is the JVM-standard fix."
                ),
                action="Replace the underlying Map with a Caffeine cache, max 50k entries, 30-min TTL.",
                snippet=(
                    "Cache<UserId, SimilarityVector> cache = Caffeine.newBuilder()\n"
                    "    .maximumSize(50_000)\n"
                    "    .expireAfterWrite(Duration.ofMinutes(30))\n"
                    "    .recordStats()\n"
                    "    .build();"
                ),
            ),
            FixRecommendation(
                priority=2,
                title="Add a heap-usage Prometheus alert at 75%",
                rationale="Catch the leak two restarts earlier next time.",
                action="Add an alert on jvm_memory_used_bytes{area=\"heap\"} / jvm_memory_max_bytes > 0.75 for 5m.",
            ),
            FixRecommendation(
                priority=3,
                title="Roll back to the pre-leak revision while you ship the fix",
                rationale="Stops the user impact immediately while engineering work proceeds.",
                action="kubectl rollout undo deploy/recommendations-svc",
                snippet="kubectl rollout undo deploy/recommendations-svc --to-revision=<previous>",
            ),
        ],
        evidence=[
            "ERROR java.lang.OutOfMemoryError: Java heap space",
            "ERROR at c.acme.reco.UserSimilarityCache.put(UserSimilarityCache.java:148)",
            "INFO  Pod recommendations-svc-6c4-x9k OOMKilled, restarting (5th restart in 4h)",
            "WARN  Recommendations endpoint returning fallback (cached) for 18% of users",
        ],
        source=SourceKind.DEMO,
        model="demo",
        forensic=ForensicReport(
            patient_zero=TimelineEvent(
                timestamp=base + timedelta(minutes=88),
                label="Patient zero — heap pressure begins",
                detail=(
                    "Heap usage crossed 60% with GC pauses growing to 240ms. "
                    "The leak started here; OOMs came an hour later."
                ),
                severity=Severity.P3,
            ),
            propagation_path=[
                "recommendations-svc (heap)",
                "recommendations-svc (latency)",
                "api-gateway",
                "end users (fallback recommendations)",
            ],
            blast_radius=[
                BlastRadiusEntity(
                    kind="service",
                    name="recommendations-svc",
                    impact="OOMKilled every ~50 minutes (5 restarts in 4h)",
                    severity=Severity.P2,
                ),
                BlastRadiusEntity(
                    kind="service",
                    name="api-gateway",
                    impact="Serving cached fallback for 18% of recommendation requests",
                    severity=Severity.P3,
                ),
                BlastRadiusEntity(
                    kind="user_segment",
                    name="18% of active users",
                    impact="Receiving stale / generic recommendations instead of personalized",
                    severity=Severity.P2,
                ),
                BlastRadiusEntity(
                    kind="data",
                    name="UserSimilarityCache",
                    impact="Cache rebuilds from scratch after every OOM; cold-start latency penalty",
                    severity=Severity.P3,
                ),
            ],
            trigger_hypothesis=(
                "UserSimilarityCache was introduced without a max-size or TTL "
                "policy. As traffic grew and more unique user IDs entered the "
                "cache, the heap filled linearly until the JVM ran out of space. "
                "No precipitating deploy / config event — this is slow-burn "
                "resource exhaustion, latent in the code from the start."
            ),
            trigger_confidence=0.82,
            minutes_to_detection=141,
        ),
    )


def db_outage_demo() -> AnalyzeResponse:
    base = _now_minus(minutes=12)
    return AnalyzeResponse(
        title="RDS failover with replica lag — orders-api stale reads",
        summary=(
            "rds-orders-prod underwent a writer failover. orders-api recovered "
            "connections quickly but the new writer's replicas are 18s behind, "
            "causing stale reads. inventory-svc has already observed at least one "
            "inconsistency: an order marked pending after its payment was captured."
        ),
        root_cause=(
            "RDS Aurora writer failover triggered by sustained slow queries on the "
            "old primary; reads have not been quiesced during the lag window, so "
            "reads from replicas return stale order state."
        ),
        confidence=0.84,
        severity=Severity.P1,
        severity_rationale=(
            "Inventory inconsistency on captured payments risks double-charging "
            "and overselling. Even a single observed case is P1."
        ),
        affected_services=[
            AffectedService(
                name="orders-api",
                role="api",
                impact="503s during failover, now serving stale data on read path",
                health="degraded",
            ),
            AffectedService(
                name="inventory-svc",
                role="worker",
                impact="Stale reads — observed inconsistency on order #91823",
                health="degraded",
            ),
            AffectedService(
                name="rds-orders-prod",
                role="database",
                impact="Failover complete; replica lag 18.4s vs 5s threshold",
                health="degraded",
            ),
        ],
        timeline=[
            TimelineEvent(
                timestamp=base,
                label="Slow queries begin",
                detail="orders queries on user_id climb past 4s.",
                severity=Severity.P3,
            ),
            TimelineEvent(
                timestamp=base + timedelta(minutes=1, seconds=16),
                label="Connection lost",
                detail="Postgres closes the writer connection unexpectedly.",
                severity=Severity.P2,
            ),
            TimelineEvent(
                timestamp=base + timedelta(minutes=1, seconds=16),
                label="Failover",
                detail="Writer endpoint switches to rds-orders-prod-2.",
                severity=Severity.P2,
            ),
            TimelineEvent(
                timestamp=base + timedelta(minutes=1, seconds=59),
                label="Replica lag breach",
                detail="Lag at 18.4s — read-after-write inconsistencies likely.",
                severity=Severity.P1,
            ),
            TimelineEvent(
                timestamp=base + timedelta(minutes=2, seconds=7),
                label="Inventory inconsistency observed",
                detail="Order #91823 status=pending but payment captured 14s ago.",
                severity=Severity.P1,
            ),
        ],
        fixes=[
            FixRecommendation(
                priority=1,
                title="Route reads to the writer until replica lag falls under 1s",
                rationale="Eliminates stale reads while the cluster catches up.",
                action="Flip ORDERS_DB_READ_ENDPOINT to the writer for the lag window.",
                snippet="kubectl set env deploy/orders-api ORDERS_DB_READ_ENDPOINT=$ORDERS_DB_WRITER",
            ),
            FixRecommendation(
                priority=2,
                title="Quarantine and re-check order #91823 (and any siblings)",
                rationale="Avoid double-fulfillment while the data settles.",
                action=(
                    "Mark the order with a manual-review flag, then re-query from "
                    "the writer 30 seconds after lag clears."
                ),
            ),
            FixRecommendation(
                priority=3,
                title="Add an alarm on AuroraReplicaLag > 5s for 60s",
                rationale="Surface this before customer impact next time.",
                action="Create a CloudWatch alarm and page on-call.",
                snippet=(
                    "aws cloudwatch put-metric-alarm \\\n"
                    "  --alarm-name aurora-replica-lag-orders \\\n"
                    "  --metric-name AuroraReplicaLag \\\n"
                    "  --namespace AWS/RDS --statistic Maximum \\\n"
                    "  --period 60 --threshold 5 --evaluation-periods 1 \\\n"
                    "  --comparison-operator GreaterThanThreshold"
                ),
            ),
        ],
        evidence=[
            "ERROR Postgres connection lost: server closed the connection unexpectedly",
            "ERROR Failover detected: writer endpoint switched to rds-orders-prod-2",
            "WARN  Replica lag 18.4s (threshold 5s) — read-after-write inconsistencies likely",
            "ERROR Stale read detected: order #91823 status=pending but payment captured 14s ago",
        ],
        source=SourceKind.DEMO,
        model="demo",
        forensic=ForensicReport(
            patient_zero=TimelineEvent(
                timestamp=base,
                label="Patient zero — slow queries on old primary",
                detail=(
                    "orders-api SlowQuery 4.2s on SELECT orders WHERE user_id — "
                    "sustained slow queries are what eventually drove RDS to "
                    "promote the standby. Failover was a symptom, not the cause."
                ),
                severity=Severity.P3,
            ),
            propagation_path=[
                "rds-orders-prod (slow queries)",
                "rds-orders-prod (failover triggered)",
                "orders-api",
                "inventory-svc",
                "order #91823 (stale read)",
            ],
            blast_radius=[
                BlastRadiusEntity(
                    kind="dependency",
                    name="rds-orders-prod (Aurora cluster)",
                    impact="Writer failover complete; replica lag 18.4s vs 5s threshold",
                    severity=Severity.P2,
                ),
                BlastRadiusEntity(
                    kind="service",
                    name="orders-api",
                    impact="503s during failover, now serving stale data on read path",
                    severity=Severity.P1,
                ),
                BlastRadiusEntity(
                    kind="service",
                    name="inventory-svc",
                    impact="Stale reads — observed inconsistency on order #91823",
                    severity=Severity.P1,
                ),
                BlastRadiusEntity(
                    kind="data",
                    name="Recent orders (last ~20s)",
                    impact="Risk of incorrect status; double-charge / oversell window open",
                    severity=Severity.P1,
                ),
                BlastRadiusEntity(
                    kind="region",
                    name="us-east-1",
                    impact="Primary region affected; cross-region traffic unaffected",
                    severity=Severity.P2,
                ),
            ],
            trigger_hypothesis=(
                "Sustained slow queries on the old primary (likely a missing or "
                "stale index on orders.user_id + orders.created_at) drove load "
                "high enough for RDS to initiate failover. The user-visible "
                "incident only became a P1 once the lag started producing stale "
                "reads on captured payments."
            ),
            trigger_confidence=0.72,
            minutes_to_detection=2,
        ),
    )


SAMPLE_INCIDENTS: Dict[str, Dict[str, str]] = {
    "cascading-failure": {
        "title": "Cascading checkout failure (DB → Redis → workers)",
        "logs": CASCADING_FAILURE_LOGS,
        "service_hint": "checkout-api",
    },
    "memory-leak": {
        "title": "Recommendations service memory leak",
        "logs": MEMORY_LEAK_LOGS,
        "service_hint": "recommendations-svc",
    },
    "db-outage": {
        "title": "RDS failover with replica lag",
        "logs": DB_OUTAGE_LOGS,
        "service_hint": "orders-api",
    },
}


def list_samples() -> List[Dict[str, str]]:
    """Return metadata for the sample-incident picker on the dashboard."""
    return [
        {"id": key, "title": value["title"], "service_hint": value["service_hint"]}
        for key, value in SAMPLE_INCIDENTS.items()
    ]


def get_sample_logs(sample_id: str) -> Dict[str, str] | None:
    return SAMPLE_INCIDENTS.get(sample_id)


def fallback_analysis(logs: str) -> AnalyzeResponse:
    """Pick the closest hand-crafted demo analysis for a paste-in.

    Used when Bedrock is unavailable. Heuristics on the log content steer the
    user to the most relevant fixture so the demo still feels intelligent.
    Order matters: cascade signals take precedence because they often *also*
    contain OOMs or RDS terms as downstream symptoms.
    """
    lowered = logs.lower()

    # RDS-specific signals first: they are very specific and the DB outage
    # demo also mentions "pool exhausted" as a transient failover symptom.
    if "replica lag" in lowered or ("rds" in lowered and "failover" in lowered):
        return db_outage_demo()

    # Cascade signals: pool exhaustion combined with circuit breaker / Redis.
    cascade_signals = (
        "clusterdown",
        "circuit breaker",
        "cascading",
        "checkout-api",
    )
    if "pool exhausted" in lowered or any(s in lowered for s in cascade_signals):
        return cascading_failure_demo()

    if "outofmemory" in lowered or "oomkilled" in lowered or "heap" in lowered:
        return memory_leak_demo()

    return cascading_failure_demo()
