# Incident Intelligence Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI + MCP server that ingests PagerDuty alerts, generates structured RCA drafts via Claude API, and surfaces similar past incidents from ChromaDB — returning unified markdown in under 10 seconds.

**Architecture:** Layered — a `core/` library (ingestor, rca_generator, similarity_search, formatter) shared by both a Click CLI and an MCP FastMCP server. All components have one responsibility and communicate through typed interfaces. Tests use in-memory ChromaDB and mocked Anthropic clients — no live API calls.

**Tech Stack:** Python 3.11+, Anthropic SDK, ChromaDB, FastMCP (MCP SDK), Click, Pydantic v2, Tenacity, structlog, python-dotenv, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | deps, entry point, build config |
| `.env.example` | env var template |
| `.gitignore` | standard Python ignores |
| `data/demo_incidents.json` | 10 synthetic past incidents |
| `src/incident_intel/__init__.py` | empty |
| `src/incident_intel/models.py` | Pydantic: PagerDutyAlert, Incident, RCADraft |
| `src/incident_intel/config.py` | env var loading, TriageError |
| `src/incident_intel/core/__init__.py` | empty |
| `src/incident_intel/core/ingestor.py` | load incidents into ChromaDB (idempotent) |
| `src/incident_intel/core/rca_generator.py` | Claude API → RCADraft (with retry) |
| `src/incident_intel/core/similarity_search.py` | ChromaDB query → list of metadata dicts |
| `src/incident_intel/core/formatter.py` | assemble final markdown from RCADraft + similar |
| `src/incident_intel/cli/__init__.py` | empty |
| `src/incident_intel/cli/main.py` | Click CLI: triage, analyze, find-similar, seed, ingest |
| `src/incident_intel/mcp/__init__.py` | empty |
| `src/incident_intel/mcp/server.py` | FastMCP server: triage_incident, analyze_incident, find_similar |
| `tests/conftest.py` | shared fixtures: in_memory_collection, sample_incidents |
| `tests/test_ingestor.py` | idempotency, load_from_file |
| `tests/test_similarity_search.py` | top-k results, empty collection |
| `tests/test_formatter.py` | markdown assembly, empty similar list |
| `tests/test_rca_generator.py` | alert parsing, mocked Claude call, TriageError on failure |
| `README.md` | pitch, quickstart, MCP registration, demo output, architecture diagram |

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/incident_intel/__init__.py`
- Create: `src/incident_intel/core/__init__.py`
- Create: `src/incident_intel/cli/__init__.py`
- Create: `src/incident_intel/mcp/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize git repo and directory structure**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git init
mkdir -p src/incident_intel/core src/incident_intel/cli src/incident_intel/mcp
mkdir -p tests data
touch src/incident_intel/__init__.py
touch src/incident_intel/core/__init__.py
touch src/incident_intel/cli/__init__.py
touch src/incident_intel/mcp/__init__.py
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "incident-intelligence-agent"
version = "0.1.0"
description = "Triage incidents and generate RCA drafts in under 10 seconds"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.25",
    "chromadb>=0.5",
    "mcp>=1.0",
    "click>=8.0",
    "pydantic>=2.0",
    "tenacity>=8.0",
    "python-dotenv>=1.0",
    "structlog>=24.0",
]

[project.scripts]
incident-intel = "incident_intel.cli.main:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/incident_intel"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Write `.env.example`**

```bash
# Required: your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Claude model to use for RCA generation (default: claude-sonnet-4-6)
CLAUDE_MODEL=claude-sonnet-4-6

# Optional: where ChromaDB persists data (default: ~/.incident-intel/chroma)
CHROMA_PERSIST_DIR=~/.incident-intel/chroma
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.env
.venv/
venv/
.pytest_cache/
.mypy_cache/
*.db
*.sqlite
```

- [ ] **Step 5: Write `tests/conftest.py`**

```python
import pytest
import chromadb
from incident_intel.models import Incident


@pytest.fixture
def sample_incidents():
    return [
        Incident(
            id="INC-0001",
            title="Redis OOM causing checkout timeouts",
            severity="P1",
            date="2024-11-15",
            root_cause="Memory limit not set on Redis; cache grew unbounded",
            resolution="Increased memory limit and added eviction policy",
            summary="Redis ran out of memory, causing checkout service to timeout",
        ),
        Incident(
            id="INC-0002",
            title="Database connection pool exhausted on orders service",
            severity="P1",
            date="2024-10-03",
            root_cause="Connection pool size too small for traffic spike",
            resolution="Increased pool size to 50; optimized two slow queries",
            summary="Orders service returned 503s after DB connection pool ran out",
        ),
        Incident(
            id="INC-0003",
            title="Memory leak in user-service causing OOM kills",
            severity="P2",
            date="2024-09-18",
            root_cause="Goroutine leak in session refresh loop",
            resolution="Rolled back offending PR; fixed goroutine leak",
            summary="user-service pods repeatedly OOM-killed by Kubernetes",
        ),
    ]


@pytest.fixture
def in_memory_collection():
    client = chromadb.EphemeralClient()
    return client.get_or_create_collection("incidents_v1")
```

- [ ] **Step 6: Install dependencies**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pip install pytest
```

- [ ] **Step 7: Commit scaffold**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add pyproject.toml .env.example .gitignore src/ tests/conftest.py
git commit -m "chore: project scaffold — pyproject, structure, fixtures"
```

---

## Task 2: Demo Data

**Files:**
- Create: `data/demo_incidents.json`

- [ ] **Step 1: Write `data/demo_incidents.json`**

```json
[
  {
    "id": "INC-0001",
    "title": "Redis OOM causing checkout timeouts",
    "severity": "P1",
    "date": "2024-11-15",
    "summary": "Redis instance ran out of memory, causing the checkout service to fail with connection timeouts for 23 minutes.",
    "root_cause": "Redis maxmemory limit was not configured; cache grew unbounded after a marketing campaign drove a 4x traffic spike.",
    "resolution": "Set maxmemory to 2GB with allkeys-lru eviction policy; deployed config change and restarted Redis.",
    "link": ""
  },
  {
    "id": "INC-0002",
    "title": "Database connection pool exhausted on orders service",
    "severity": "P1",
    "date": "2024-10-03",
    "summary": "Orders service could not acquire DB connections, returning 503s to all clients for 18 minutes.",
    "root_cause": "Connection pool size (10) was too small for the sustained traffic spike after a flash sale; slow queries held connections open longer than expected.",
    "resolution": "Increased pool size to 50; identified and optimized two slow queries causing connection hold times.",
    "link": ""
  },
  {
    "id": "INC-0003",
    "title": "Memory leak in user-service causing OOM kills",
    "severity": "P2",
    "date": "2024-09-18",
    "summary": "user-service pods were repeatedly OOM-killed by Kubernetes, causing intermittent 502s for 45 minutes.",
    "root_cause": "A recent PR introduced a goroutine leak in the session refresh loop; goroutines accumulated over ~6 hours until RSS exceeded the 512MB container limit.",
    "resolution": "Rolled back the offending PR; increased memory limit temporarily to 1GB to stabilize; fixed goroutine leak in follow-up PR.",
    "link": ""
  },
  {
    "id": "INC-0004",
    "title": "TLS certificate expiry causing auth service failures",
    "severity": "P1",
    "date": "2024-08-30",
    "summary": "Authentication service returned SSL handshake errors to all clients for 12 minutes after the internal mTLS certificate expired.",
    "root_cause": "Internal CA certificate renewed but not propagated to the auth service replica set; certificate rotation runbook was not automated.",
    "resolution": "Manually rotated certificate; service recovered immediately after restart.",
    "link": ""
  },
  {
    "id": "INC-0005",
    "title": "Bad config push caused payment service crash loop",
    "severity": "P1",
    "date": "2024-08-05",
    "summary": "Payment service entered a crash loop immediately after a config deploy, causing 100% error rate for 8 minutes.",
    "root_cause": "A typo in the Stripe webhook secret environment variable caused the payment service to exit on startup validation.",
    "resolution": "Rolled back config deploy via CI/CD pipeline; validated new config in staging before re-deploying.",
    "link": ""
  },
  {
    "id": "INC-0006",
    "title": "CDN misconfiguration causing 5xx spike on static assets",
    "severity": "P2",
    "date": "2024-07-22",
    "summary": "CloudFront returned 502s for all static asset requests (images, JS, CSS) for 31 minutes after a distribution config change.",
    "root_cause": "Origin protocol policy was changed from HTTPS-only to HTTP-only; the origin S3 bucket had HTTP access disabled.",
    "resolution": "Reverted CloudFront distribution config to HTTPS-only; distribution deployed in ~5 minutes.",
    "link": ""
  },
  {
    "id": "INC-0007",
    "title": "Disk full on logging host causing service degradation",
    "severity": "P2",
    "date": "2024-06-14",
    "summary": "Fluentd log shipping failed across all services after the centralized logging host ran out of disk space, causing cascading write failures in app containers.",
    "root_cause": "Log rotation policy was not applied to a new high-volume debug log added in a recent release; disk filled in 6 hours.",
    "resolution": "Manually freed disk space; updated log rotation config; reduced debug log verbosity.",
    "link": ""
  },
  {
    "id": "INC-0008",
    "title": "Third-party payment gateway timeout cascade",
    "severity": "P1",
    "date": "2024-05-29",
    "summary": "Stripe API latency spike caused checkout timeouts, which held worker threads, which cascaded to a full checkout service outage lasting 22 minutes.",
    "root_cause": "No circuit breaker on Stripe API calls; thread pool exhausted as workers blocked on slow Stripe responses.",
    "resolution": "Deployed emergency timeout reduction (5s to 2s) on Stripe calls; added circuit breaker in follow-up.",
    "link": ""
  },
  {
    "id": "INC-0009",
    "title": "Cache stampede on product catalog after deploy",
    "severity": "P2",
    "date": "2024-04-11",
    "summary": "A deploy flushed the Redis product catalog cache; all requests simultaneously hit the database, causing a stampede that brought DB CPU to 100% for 9 minutes.",
    "root_cause": "Cache warm-up was not part of the deploy runbook; keys expired simultaneously rather than with jitter.",
    "resolution": "Restarted read replicas to shed load; added cache pre-warming step to deploy runbook and TTL jitter.",
    "link": ""
  },
  {
    "id": "INC-0010",
    "title": "Kubernetes node OOM evictions causing pod restarts across cluster",
    "severity": "P2",
    "date": "2024-03-08",
    "summary": "Multiple node-level OOM events caused batch job pods to evict application pods, resulting in intermittent 503s for 40 minutes across three services.",
    "root_cause": "A batch data export job had no memory limits; it consumed all available memory on shared nodes, triggering kubelet eviction of lower-priority pods.",
    "resolution": "Killed runaway batch job; added resource limits and requests to all batch jobs; separated batch and application node pools.",
    "link": ""
  }
]
```

- [ ] **Step 2: Commit demo data**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add data/demo_incidents.json
git commit -m "feat: add 10 synthetic demo incidents covering common enterprise failure patterns"
```

---

## Task 3: Models + Config

**Files:**
- Create: `src/incident_intel/models.py`
- Create: `src/incident_intel/config.py`

- [ ] **Step 1: Write `src/incident_intel/models.py`**

```python
from pydantic import BaseModel


class PagerDutyAlert(BaseModel):
    """Validated shape of a PagerDuty webhook payload."""
    title: str
    service: str = ""
    severity: str = "unknown"
    triggered_at: str = ""
    description: str = ""


class Incident(BaseModel):
    id: str
    title: str
    severity: str
    date: str
    root_cause: str
    resolution: str
    link: str = ""
    summary: str = ""


class RCADraft(BaseModel):
    raw_markdown: str
    alert_title: str
    generated_at: str
```

- [ ] **Step 2: Write `src/incident_intel/config.py`**

```python
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class TriageError(Exception):
    """Raised when a triage workflow fails non-transiently."""
    pass


@dataclass
class Config:
    api_key: str
    model: str
    chroma_persist_dir: str


def get_config() -> Config:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise TriageError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Copy .env.example to .env and add your key."
        )
    return Config(
        api_key=api_key,
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        chroma_persist_dir=os.environ.get(
            "CHROMA_PERSIST_DIR",
            str(Path.home() / ".incident-intel" / "chroma"),
        ),
    )
```

- [ ] **Step 3: Commit models and config**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add src/incident_intel/models.py src/incident_intel/config.py
git commit -m "feat: add Pydantic models and config loader with TriageError"
```

---

## Task 4: Ingestor (TDD)

**Files:**
- Create: `src/incident_intel/core/ingestor.py`
- Create: `tests/test_ingestor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ingestor.py`:

```python
import json
import tempfile
from pathlib import Path

import pytest

from incident_intel.core.ingestor import ingest_incidents, load_from_file
from incident_intel.models import Incident


def test_ingest_adds_incidents(in_memory_collection, sample_incidents):
    count = ingest_incidents(sample_incidents, in_memory_collection)
    assert count == 3
    assert in_memory_collection.count() == 3


def test_ingest_is_idempotent(in_memory_collection, sample_incidents):
    ingest_incidents(sample_incidents, in_memory_collection)
    count = ingest_incidents(sample_incidents, in_memory_collection)
    assert count == 0  # no new insertions
    assert in_memory_collection.count() == 3  # same total


def test_ingest_partial_duplicates(in_memory_collection, sample_incidents):
    ingest_incidents([sample_incidents[0]], in_memory_collection)
    count = ingest_incidents(sample_incidents, in_memory_collection)
    assert count == 2  # only 2 new


def test_load_from_file(in_memory_collection):
    incidents = [
        {
            "id": "INC-TEST-1",
            "title": "Test incident",
            "severity": "P2",
            "date": "2024-01-01",
            "root_cause": "Test root cause",
            "resolution": "Test resolution",
        }
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(incidents, f)
        tmp_path = f.name

    count = load_from_file(tmp_path, in_memory_collection)
    assert count == 1
    assert in_memory_collection.count() == 1


def test_load_from_file_skips_malformed_records(in_memory_collection):
    incidents = [
        {"id": "INC-GOOD-1", "title": "Good", "severity": "P1", "date": "2024-01-01",
         "root_cause": "cause", "resolution": "fix"},
        {"bad": "record_missing_required_fields"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(incidents, f)
        tmp_path = f.name

    count = load_from_file(tmp_path, in_memory_collection)
    assert count == 1  # only the good record
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest tests/test_ingestor.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `ingestor` does not exist yet.

- [ ] **Step 3: Write `src/incident_intel/core/ingestor.py`**

```python
import json
from pathlib import Path
from typing import List

import chromadb
import structlog

from incident_intel.models import Incident

logger = structlog.get_logger()


def get_collection(persist_dir: str) -> chromadb.Collection:
    """Return the ChromaDB incidents collection, creating it if needed."""
    client = chromadb.PersistentClient(path=persist_dir)
    return client.get_or_create_collection("incidents_v1")


def ingest_incidents(
    incidents: List[Incident], collection: chromadb.Collection
) -> int:
    """Insert incidents into ChromaDB, skipping duplicates.

    Returns the count of newly inserted incidents.
    """
    inserted = 0
    for incident in incidents:
        existing = collection.get(ids=[incident.id])
        if existing["ids"]:
            logger.info("skipping_duplicate", id=incident.id)
            continue

        document = f"{incident.title}\n{incident.summary}\n{incident.root_cause}"
        collection.add(
            ids=[incident.id],
            documents=[document],
            metadatas=[
                {
                    "id": incident.id,
                    "title": incident.title,
                    "severity": incident.severity,
                    "date": incident.date,
                    "root_cause": incident.root_cause,
                    "resolution": incident.resolution,
                    "link": incident.link,
                }
            ],
        )
        logger.info("ingested_incident", id=incident.id, title=incident.title)
        inserted += 1

    return inserted


def load_from_file(file_path: str, collection: chromadb.Collection) -> int:
    """Load incidents from a JSON file and ingest into ChromaDB.

    Skips malformed records and logs errors per record.
    Returns count of newly inserted incidents.
    """
    path = Path(file_path)
    with open(path) as f:
        data = json.load(f)

    incidents = []
    for record in data:
        try:
            incidents.append(Incident(**record))
        except Exception as e:
            logger.error("malformed_record", error=str(e), record=record)

    return ingest_incidents(incidents, collection)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest tests/test_ingestor.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add src/incident_intel/core/ingestor.py tests/test_ingestor.py
git commit -m "feat: add idempotent ChromaDB ingestor with file loader"
```

---

## Task 5: Similarity Search (TDD)

**Files:**
- Create: `src/incident_intel/core/similarity_search.py`
- Create: `tests/test_similarity_search.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_similarity_search.py`:

```python
import pytest

from incident_intel.core.ingestor import ingest_incidents
from incident_intel.core.similarity_search import find_similar_incidents


def test_find_similar_returns_top_k(in_memory_collection, sample_incidents):
    ingest_incidents(sample_incidents, in_memory_collection)
    results = find_similar_incidents(
        "Redis memory issue causing service timeout",
        in_memory_collection,
        top_k=2,
    )
    assert len(results) == 2


def test_find_similar_returns_expected_metadata_keys(in_memory_collection, sample_incidents):
    ingest_incidents(sample_incidents, in_memory_collection)
    results = find_similar_incidents("Redis OOM", in_memory_collection, top_k=1)
    assert len(results) == 1
    meta = results[0]
    assert "id" in meta
    assert "title" in meta
    assert "severity" in meta
    assert "date" in meta
    assert "root_cause" in meta
    assert "resolution" in meta


def test_find_similar_returns_empty_list_when_collection_empty(in_memory_collection):
    results = find_similar_incidents("any description", in_memory_collection, top_k=3)
    assert results == []


def test_find_similar_clamps_top_k_to_collection_size(in_memory_collection, sample_incidents):
    ingest_incidents(sample_incidents[:2], in_memory_collection)
    results = find_similar_incidents("memory issue", in_memory_collection, top_k=10)
    assert len(results) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest tests/test_similarity_search.py -v
```

Expected: `ImportError` — `similarity_search` does not exist yet.

- [ ] **Step 3: Write `src/incident_intel/core/similarity_search.py`**

```python
from typing import Any, Dict, List

import chromadb
import structlog

logger = structlog.get_logger()


def find_similar_incidents(
    description: str,
    collection: chromadb.Collection,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Query ChromaDB for incidents similar to the given description.

    Returns a list of metadata dicts. Returns empty list if collection is empty.
    """
    count = collection.count()
    if count == 0:
        logger.info("knowledge_base_empty")
        return []

    results = collection.query(
        query_texts=[description],
        n_results=min(top_k, count),
        include=["metadatas", "distances"],
    )

    metadatas = results["metadatas"][0] if results["metadatas"] else []
    logger.info("similarity_search_complete", found=len(metadatas), top_k=top_k)
    return metadatas
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest tests/test_similarity_search.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add src/incident_intel/core/similarity_search.py tests/test_similarity_search.py
git commit -m "feat: add ChromaDB similarity search with empty-collection guard"
```

---

## Task 6: Formatter (TDD)

**Files:**
- Create: `src/incident_intel/core/formatter.py`
- Create: `tests/test_formatter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_formatter.py`:

```python
import pytest

from incident_intel.core.formatter import format_report, format_similar_incidents
from incident_intel.models import RCADraft


SAMPLE_SIMILAR = [
    {
        "id": "INC-0001",
        "title": "Redis OOM causing checkout timeouts",
        "severity": "P1",
        "date": "2024-11-15",
        "root_cause": "Memory limit not set on Redis; cache grew unbounded",
        "resolution": "Increased memory limit and added eviction policy",
        "link": "",
    },
    {
        "id": "INC-0002",
        "title": "Database connection pool exhausted",
        "severity": "P2",
        "date": "2024-10-03",
        "root_cause": "Pool size too small for traffic spike",
        "resolution": "Increased pool size to 50",
        "link": "https://jira.example.com/INC-0002",
    },
]

SAMPLE_DRAFT = RCADraft(
    raw_markdown="## Summary\nService down.\n## Timeline\nTimeline not available — fill in manually.\n## Root Cause (Hypothesis)\nUnknown.\n## Impact\nAll users.\n## Resolution Steps\nRestart service.\n## Prevention / Follow-ups\nAdd monitoring.",
    alert_title="Test alert",
    generated_at="2026-04-28T00:00:00+00:00",
)


def test_format_similar_includes_incident_ids():
    output = format_similar_incidents(SAMPLE_SIMILAR, total_searched=10)
    assert "INC-0001" in output
    assert "INC-0002" in output


def test_format_similar_includes_root_cause():
    output = format_similar_incidents(SAMPLE_SIMILAR, total_searched=10)
    assert "Memory limit not set on Redis" in output


def test_format_similar_includes_link_when_present():
    output = format_similar_incidents(SAMPLE_SIMILAR, total_searched=10)
    assert "https://jira.example.com/INC-0002" in output


def test_format_similar_empty_returns_seed_hint():
    output = format_similar_incidents([], total_searched=0)
    assert "incident-intel seed" in output
    assert "No similar incidents found" in output


def test_format_report_includes_alert_title():
    output = format_report(SAMPLE_DRAFT, SAMPLE_SIMILAR, total_searched=10)
    assert "Test alert" in output


def test_format_report_includes_rca_sections():
    output = format_report(SAMPLE_DRAFT, SAMPLE_SIMILAR, total_searched=10)
    assert "## Summary" in output
    assert "## Root Cause (Hypothesis)" in output
    assert "## Prevention / Follow-ups" in output


def test_format_report_includes_similar_section():
    output = format_report(SAMPLE_DRAFT, SAMPLE_SIMILAR, total_searched=10)
    assert "## Similar Past Incidents" in output
    assert "INC-0001" in output


def test_format_report_empty_similar_shows_hint():
    output = format_report(SAMPLE_DRAFT, [], total_searched=0)
    assert "incident-intel seed" in output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest tests/test_formatter.py -v
```

Expected: `ImportError` — `formatter` does not exist yet.

- [ ] **Step 3: Write `src/incident_intel/core/formatter.py`**

```python
from typing import Any, Dict, List

from incident_intel.models import RCADraft


def format_similar_incidents(
    similar: List[Dict[str, Any]], total_searched: int
) -> str:
    """Format similar incidents as a markdown section.

    Returns a seed hint if the list is empty.
    """
    if not similar:
        return "> No similar incidents found — run `incident-intel seed` to load demo data.\n"

    lines = ["## Similar Past Incidents\n"]
    for i, meta in enumerate(similar, 1):
        link_part = (
            f" · [{meta['id']}]({meta['link']})" if meta.get("link") else ""
        )
        lines.append(
            f"{i}. **[{meta['id']}] {meta['title']}**"
            f" — {meta['severity']} · {meta['date']}{link_part}"
        )
        lines.append(f"   Root cause: {meta['root_cause']}")
        lines.append(f"   Resolution: {meta['resolution']}\n")

    lines.append(f"> Searched {total_searched} past incidents · Top {len(similar)} shown")
    return "\n".join(lines)


def format_report(
    draft: RCADraft,
    similar: List[Dict[str, Any]],
    total_searched: int,
) -> str:
    """Assemble the full triage report: header + RCA + similar incidents."""
    header = (
        f"# Incident Triage Report\n\n"
        f"**Alert:** {draft.alert_title}\n"
        f"**Generated:** {draft.generated_at}\n\n"
        f"---\n\n"
    )
    similar_section = format_similar_incidents(similar, total_searched)
    return f"{header}{draft.raw_markdown}\n\n---\n\n{similar_section}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest tests/test_formatter.py -v
```

Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add src/incident_intel/core/formatter.py tests/test_formatter.py
git commit -m "feat: add markdown formatter for RCA report and similar incidents"
```

---

## Task 7: RCA Generator (TDD)

**Files:**
- Create: `src/incident_intel/core/rca_generator.py`
- Create: `tests/test_rca_generator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rca_generator.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from incident_intel.config import TriageError
from incident_intel.core.rca_generator import generate_rca, _parse_alert


FULL_MARKDOWN = (
    "## Summary\nService unavailable.\n"
    "## Timeline\nTimeline not available — fill in manually.\n"
    "## Root Cause (Hypothesis)\nMemory leak.\n"
    "## Impact\nAll checkout users.\n"
    "## Resolution Steps\nRestart pod.\n"
    "## Prevention / Follow-ups\nAdd memory limits."
)

PAGERDUTY_JSON = '{"title": "Redis OOM", "service": "checkout", "severity": "P1", "triggered_at": "2026-04-28T10:00:00Z", "description": "Redis is OOM"}'


def _make_mock_client(response_text: str):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_parse_alert_extracts_pagerduty_fields():
    alert_text, title = _parse_alert(PAGERDUTY_JSON)
    assert "Redis OOM" in alert_text
    assert title == "Redis OOM"
    assert "checkout" in alert_text


def test_parse_alert_falls_back_to_plain_text():
    plain = "Database is down, all queries failing"
    alert_text, title = _parse_alert(plain)
    assert alert_text == plain
    assert "Database is down" in title


def test_generate_rca_returns_draft_with_all_sections():
    with patch("incident_intel.core.rca_generator.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_client(FULL_MARKDOWN)
        draft = generate_rca(PAGERDUTY_JSON, api_key="test-key", model="claude-sonnet-4-6")

    assert "## Summary" in draft.raw_markdown
    assert "## Root Cause (Hypothesis)" in draft.raw_markdown
    assert "## Prevention / Follow-ups" in draft.raw_markdown
    assert draft.alert_title == "Redis OOM"
    assert draft.generated_at != ""


def test_generate_rca_passes_correct_model_to_api():
    with patch("incident_intel.core.rca_generator.Anthropic") as mock_cls:
        mock_client = _make_mock_client(FULL_MARKDOWN)
        mock_cls.return_value = mock_client
        generate_rca("plain text alert", api_key="test-key", model="claude-opus-4-6")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-6"


def test_generate_rca_raises_triage_error_on_api_failure():
    with patch("incident_intel.core.rca_generator.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_cls.return_value = mock_client

        with pytest.raises(TriageError, match="Claude API failed"):
            generate_rca("some alert", api_key="test-key", model="claude-sonnet-4-6")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest tests/test_rca_generator.py -v
```

Expected: `ImportError` — `rca_generator` does not exist yet.

- [ ] **Step 3: Write `src/incident_intel/core/rca_generator.py`**

```python
import json
from datetime import datetime, timezone

import structlog
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from incident_intel.config import TriageError
from incident_intel.models import PagerDutyAlert, RCADraft

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer specializing in incident triage and root cause analysis.

Your job is to take a raw incident alert and produce a concise, structured RCA draft in markdown.

Always output exactly these sections in this order, using these exact headers:
## Summary
## Timeline
## Root Cause (Hypothesis)
## Impact
## Resolution Steps
## Prevention / Follow-ups

Rules:
- If timeline information is not available, write: "Timeline not available — fill in manually."
- If a field cannot be determined from the alert, mark it with [UNKNOWN] and move on.
- Each section should be 2-5 bullet points or sentences. Do not pad.
- Do not include any text outside these six sections.
- Output only markdown. No preamble, no sign-off."""


def _parse_alert(alert: str) -> tuple[str, str]:
    """Parse alert input. Returns (alert_text_for_prompt, alert_title).

    Tries PagerDuty JSON first; falls back to plain text.
    """
    try:
        data = json.loads(alert)
        pd = PagerDutyAlert(**data)
        text = (
            f"Title: {pd.title}\n"
            f"Service: {pd.service}\n"
            f"Severity: {pd.severity}\n"
            f"Triggered at: {pd.triggered_at}\n"
            f"Description: {pd.description}"
        )
        return text, pd.title
    except Exception:
        logger.warning("alert_not_pagerduty_json", preview=alert[:80])
        return alert, alert[:80]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _call_claude(client: Anthropic, model: str, alert_text: str) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze this incident alert and produce a structured RCA draft:\n\n"
                    f"{alert_text}"
                ),
            }
        ],
    )
    return response.content[0].text


def generate_rca(alert: str, api_key: str, model: str) -> RCADraft:
    """Generate a structured RCA draft from a raw alert string.

    Raises TriageError if Claude API fails after 3 retries.
    """
    alert_text, alert_title = _parse_alert(alert)
    client = Anthropic(api_key=api_key)
    logger.info("generating_rca", alert_title=alert_title, model=model)

    try:
        raw_markdown = _call_claude(client, model, alert_text)
    except Exception as e:
        raise TriageError(f"Claude API failed after 3 retries: {e}") from e

    return RCADraft(
        raw_markdown=raw_markdown,
        alert_title=alert_title,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest tests/test_rca_generator.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Run the full test suite**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add src/incident_intel/core/rca_generator.py tests/test_rca_generator.py
git commit -m "feat: add RCA generator with Claude API, retry logic, and PagerDuty parsing"
```

---

## Task 8: CLI

**Files:**
- Create: `src/incident_intel/cli/main.py`

No unit tests for the CLI layer — it's a thin wrapper over core functions that are already tested.
Manual smoke test in the step below.

- [ ] **Step 1: Write `src/incident_intel/cli/main.py`**

```python
import sys
from pathlib import Path

import click
import structlog

from incident_intel.config import TriageError, get_config
from incident_intel.core.formatter import format_report, format_similar_incidents
from incident_intel.core.ingestor import get_collection, load_from_file
from incident_intel.core.rca_generator import generate_rca
from incident_intel.core.similarity_search import find_similar_incidents

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(20)  # INFO
)
logger = structlog.get_logger()


@click.group()
def cli():
    """Incident Intelligence Agent — triage incidents and generate RCA drafts."""
    pass


@cli.command()
@click.option("--alert", default=None, help="Raw alert text or PagerDuty JSON string")
@click.option(
    "--alert-file",
    default=None,
    type=click.Path(exists=True),
    help="Path to alert JSON file",
)
def triage(alert, alert_file):
    """Generate RCA draft + find similar past incidents."""
    alert_text = _resolve_alert(alert, alert_file)
    config = _load_config()
    collection = get_collection(config.chroma_persist_dir)
    draft = generate_rca(alert_text, config.api_key, config.model)
    similar = find_similar_incidents(alert_text, collection)
    click.echo(format_report(draft, similar, total_searched=collection.count()))


@cli.command()
@click.option("--alert", required=True, help="Raw alert text or PagerDuty JSON string")
def analyze(alert):
    """Generate a structured RCA draft only (no similarity search)."""
    config = _load_config()
    draft = generate_rca(alert, config.api_key, config.model)
    click.echo(
        f"# Incident Triage Report\n\n"
        f"**Alert:** {draft.alert_title}\n"
        f"**Generated:** {draft.generated_at}\n\n"
        f"---\n\n"
        f"{draft.raw_markdown}"
    )


@cli.command("find-similar")
@click.option("--description", required=True, help="Incident description to search for")
@click.option("--top-k", default=3, show_default=True, help="Number of results to return")
def find_similar(description, top_k):
    """Search the knowledge base for similar past incidents."""
    config = _load_config()
    collection = get_collection(config.chroma_persist_dir)
    similar = find_similar_incidents(description, collection, top_k)
    click.echo(format_similar_incidents(similar, total_searched=collection.count()))


@cli.command()
def seed():
    """Load the bundled demo incidents into the knowledge base."""
    config = _load_config()
    # data/ is at the project root: src/incident_intel/cli/main.py → 4 levels up
    data_path = Path(__file__).parent.parent.parent.parent / "data" / "demo_incidents.json"
    if not data_path.exists():
        click.echo(f"Demo data not found at {data_path}", err=True)
        sys.exit(1)
    collection = get_collection(config.chroma_persist_dir)
    count = load_from_file(str(data_path), collection)
    click.echo(f"Seeded {count} new incidents. Knowledge base now has {collection.count()} total.")


@cli.command()
@click.option(
    "--file",
    "file_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to a JSON file of incidents to ingest",
)
def ingest(file_path):
    """Ingest incidents from a JSON file into the knowledge base."""
    config = _load_config()
    collection = get_collection(config.chroma_persist_dir)
    count = load_from_file(file_path, collection)
    click.echo(f"Ingested {count} new incidents. Knowledge base now has {collection.count()} total.")


def _load_config():
    try:
        return get_config()
    except TriageError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)


def _resolve_alert(alert, alert_file):
    if alert_file:
        with open(alert_file) as f:
            return f.read()
    if alert:
        return alert
    click.echo("Error: provide --alert TEXT or --alert-file PATH", err=True)
    sys.exit(1)
```

- [ ] **Step 2: Verify the CLI entry point is registered**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pip install -e . --quiet
incident-intel --help
```

Expected output:
```
Usage: incident-intel [OPTIONS] COMMAND [ARGS]...

  Incident Intelligence Agent — triage incidents and generate RCA drafts.

Options:
  --help  Show this message and exit.

Commands:
  analyze      Generate a structured RCA draft only (no similarity search).
  find-similar Search the knowledge base for similar past incidents.
  ingest       Ingest incidents from a JSON file into the knowledge base.
  seed         Load the bundled demo incidents into the knowledge base.
  triage       Generate RCA draft + find similar past incidents.
```

- [ ] **Step 3: Smoke test seed command (requires ANTHROPIC_API_KEY)**

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY, then:
incident-intel seed
```

Expected output:
```
Seeded 10 new incidents. Knowledge base now has 10 total.
```

- [ ] **Step 4: Commit**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add src/incident_intel/cli/main.py
git commit -m "feat: add Click CLI with triage, analyze, find-similar, seed, ingest commands"
```

---

## Task 9: MCP Server

**Files:**
- Create: `src/incident_intel/mcp/server.py`

- [ ] **Step 1: Write `src/incident_intel/mcp/server.py`**

```python
from mcp.server.fastmcp import FastMCP

from incident_intel.config import get_config
from incident_intel.core.formatter import format_report, format_similar_incidents
from incident_intel.core.ingestor import get_collection
from incident_intel.core.rca_generator import generate_rca
from incident_intel.core.similarity_search import find_similar_incidents

mcp = FastMCP("incident-intel")


@mcp.tool()
def triage_incident(alert: str) -> str:
    """Full incident triage: generates a structured RCA draft and finds the top 3
    similar past incidents from the knowledge base. Returns unified markdown
    ready to paste into Jira or Slack.

    Args:
        alert: Raw PagerDuty webhook JSON string or plain text incident description.
    """
    config = get_config()
    collection = get_collection(config.chroma_persist_dir)
    draft = generate_rca(alert, config.api_key, config.model)
    similar = find_similar_incidents(alert, collection)
    return format_report(draft, similar, total_searched=collection.count())


@mcp.tool()
def analyze_incident(alert: str) -> str:
    """Generate a structured RCA draft from an incident alert using Claude.
    Does not search the knowledge base.

    Args:
        alert: Raw PagerDuty webhook JSON string or plain text incident description.
    """
    config = get_config()
    draft = generate_rca(alert, config.api_key, config.model)
    return (
        f"# Incident Triage Report\n\n"
        f"**Alert:** {draft.alert_title}\n"
        f"**Generated:** {draft.generated_at}\n\n"
        f"---\n\n"
        f"{draft.raw_markdown}"
    )


@mcp.tool()
def find_similar(description: str, top_k: int = 3) -> str:
    """Search the local incident knowledge base for similar past incidents.
    Returns top-k results with title, severity, date, root cause, and link.

    Args:
        description: Plain text description of the incident.
        top_k: Number of similar incidents to return (default: 3).
    """
    config = get_config()
    collection = get_collection(config.chroma_persist_dir)
    similar = find_similar_incidents(description, collection, top_k)
    return format_similar_incidents(similar, total_searched=collection.count())


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Verify MCP server starts without errors**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
python -m incident_intel.mcp.server &
sleep 1
kill %1
```

Expected: server starts and exits cleanly (no import errors or tracebacks).

- [ ] **Step 3: Register with Claude Code**

```bash
claude mcp add incident-intel -- python -m incident_intel.mcp.server
```

Then in a Claude Code session, verify the tools appear:
```
/mcp
```

Expected: `incident-intel` listed with tools `triage_incident`, `analyze_incident`, `find_similar`.

- [ ] **Step 4: Commit**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add src/incident_intel/mcp/server.py
git commit -m "feat: add FastMCP server exposing triage_incident, analyze_incident, find_similar tools"
```

---

## Task 10: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# Incident Intelligence Agent

Triage incidents and generate RCA drafts in under 10 seconds — powered by Claude and a local vector knowledge base.

> Built this after architecting a similar system in production at Orangetheory Fitness — this is the open-source, vendor-neutral version of that workflow.

## What it does

Takes a raw incident alert (PagerDuty JSON or plain text), runs it through the Claude API to generate a structured RCA draft, searches a local ChromaDB knowledge base of past incidents for similar issues, and returns a combined markdown report ready to paste into Jira or Slack.

**Why it exists:** On-call engineers waste 30–60 minutes per incident writing the same RCA structure from scratch and hunting Slack/Confluence for similar past issues. This agent does both in under 10 seconds.

## Architecture

```
Alert (PagerDuty JSON or plain text)
        │
        ▼
┌─────────────────┐     ┌──────────────────┐
│  rca_generator  │────▶│   Claude API     │
│  (+ retry/      │     │  (claude-sonnet) │
│   backoff)      │     └──────────────────┘
└────────┬────────┘
         │  RCADraft
         ▼
┌─────────────────┐     ┌──────────────────┐
│    formatter    │◀────│similarity_search │
│                 │     │  (ChromaDB)      │
└────────┬────────┘     └──────────────────┘
         │                      ▲
         │                      │ ingestor
         ▼               past incidents JSON
  Markdown Report
  (Jira / Slack)

        Exposed via:
        ├── CLI  (incident-intel triage ...)
        └── MCP  (triage_incident tool)
```

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/incident-intelligence-agent
cd incident-intelligence-agent
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Seed the knowledge base with demo incidents
incident-intel seed

# 4. Triage an incident
incident-intel triage --alert "Redis OOM killing the checkout service, 100% error rate"
```

> **Note:** First run downloads the sentence-transformers model (~90MB, one-time) used by ChromaDB for embeddings.

## CLI Commands

```bash
# Full triage: RCA draft + similar incidents
incident-intel triage --alert "your alert text"
incident-intel triage --alert-file alert.json

# RCA draft only (no similarity search)
incident-intel analyze --alert "your alert text"

# Similarity search only (no Claude call)
incident-intel find-similar --description "Redis OOM killing checkout"
incident-intel find-similar --description "..." --top-k 5

# Knowledge base management
incident-intel seed                          # load bundled demo incidents
incident-intel ingest --file incidents.json  # load your own past incidents
```

## MCP Server (Claude Code / Claude Desktop)

```bash
# Register the MCP server
claude mcp add incident-intel -- python -m incident_intel.mcp.server
```

Three tools are available:
- `triage_incident(alert)` — full triage: RCA + similar incidents
- `analyze_incident(alert)` — RCA draft only
- `find_similar(description, top_k=3)` — similarity search only

## Demo Output

```markdown
# Incident Triage Report

**Alert:** Redis OOM causing checkout timeouts
**Generated:** 2026-04-28T14:32:00+00:00

---

## Summary
- Redis instance exhausted all available memory, causing the checkout service
  to fail all requests with connection timeout errors.
- Impact window: ~23 minutes from first alert to full recovery.

## Timeline
Timeline not available — fill in manually.

## Root Cause (Hypothesis)
- Redis `maxmemory` was not configured; cache size grew unbounded after a
  marketing campaign drove a 4x traffic spike.
- No eviction policy was set, so Redis began refusing new writes once full.

## Impact
- 100% error rate on checkout service for approximately 23 minutes.
- Estimated 4,200 failed transactions during the window.

## Resolution Steps
1. Set `maxmemory 2gb` and `maxmemory-policy allkeys-lru` in Redis config.
2. Restart Redis instance to apply config.
3. Verify checkout service error rate returns to baseline.

## Prevention / Follow-ups
- Add `maxmemory` and eviction policy to Redis provisioning runbook.
- Set up a CloudWatch alarm on Redis `UsedMemory` > 80% of instance limit.
- Review all Redis instances for missing memory configuration.

---

## Similar Past Incidents

1. **[INC-0009] Cache stampede on product catalog after deploy** — P2 · 2024-04-11
   Root cause: Cache warm-up was not part of the deploy runbook; keys expired simultaneously.
   Resolution: Added cache pre-warming step to deploy runbook and TTL jitter.

2. **[INC-0008] Third-party payment gateway timeout cascade** — P1 · 2024-05-29
   Root cause: No circuit breaker on Stripe API calls; thread pool exhausted.
   Resolution: Deployed emergency timeout reduction; added circuit breaker.

3. **[INC-0002] Database connection pool exhausted on orders service** — P1 · 2024-10-03
   Root cause: Connection pool size too small for traffic spike.
   Resolution: Increased pool size to 50; optimized two slow queries.

> Searched 10 past incidents · Top 3 shown
```

## Ingesting Your Own Past Incidents

Create a JSON file with this shape:

```json
[
  {
    "id": "INC-0042",
    "title": "Redis OOM causing checkout timeouts",
    "severity": "P1",
    "date": "2024-11-15",
    "summary": "Optional: brief description of what happened",
    "root_cause": "Memory limit not set on Redis; cache grew unbounded",
    "resolution": "Increased memory limit + added eviction policy",
    "link": "https://jira.yourcompany.com/INC-0042"
  }
]
```

Then:
```bash
incident-intel ingest --file my_incidents.json
```

## Configuration

| Environment Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Claude API authentication |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Model used for RCA generation |
| `CHROMA_PERSIST_DIR` | `~/.incident-intel/chroma` | Where ChromaDB stores the knowledge base |

## Stack

- **[Claude API](https://www.anthropic.com)** — RCA generation
- **[ChromaDB](https://www.trychroma.com)** — local vector store for past incident similarity search
- **[MCP SDK](https://github.com/modelcontextprotocol/python-sdk)** — exposes the workflow as MCP tools
- **[Click](https://click.palletsprojects.com)** — CLI framework
- **[Pydantic](https://docs.pydantic.dev)** — input validation (PagerDuty webhook schema)
- **[Tenacity](https://tenacity.readthedocs.io)** — retry + exponential backoff on Claude API calls
- **[structlog](https://www.structlog.org)** — structured logging
````

- [ ] **Step 2: Run the full test suite one final time**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
pytest -v
```

Expected: all tests pass with 0 failures.

- [ ] **Step 3: Commit README and tag**

```bash
cd /Users/sarthakhans/incident-intelligence-agent
git add README.md
git commit -m "docs: add README with quickstart, demo output, architecture diagram, and MCP registration"
git tag v0.1.0
```

---

## Self-Review: Spec Coverage Check

| Spec requirement | Covered by |
|---|---|
| Ingest PagerDuty JSON or plain text | Task 7: `_parse_alert` in `rca_generator.py` |
| Generate structured RCA via Claude API | Task 7: `rca_generator.py` |
| Search ChromaDB for top-3 similar incidents | Task 5: `similarity_search.py` |
| Unified markdown output for Jira/Slack | Task 6: `formatter.py` |
| MCP server with 3 tools | Task 9: `mcp/server.py` |
| CLI: triage, analyze, find-similar, seed, ingest | Task 8: `cli/main.py` |
| Demo data (10 synthetic incidents) | Task 2: `data/demo_incidents.json` |
| Structured logging (structlog) | Tasks 4, 5, 7: logger on every core module |
| Pydantic input validation | Task 3: `models.py` + `_parse_alert` fallback |
| Idempotent ingest | Task 4: `ingest_incidents` checks `collection.get` |
| Retry + backoff on Claude API | Task 7: `@retry` on `_call_claude` |
| Configurable ChromaDB persist path | Task 3: `CHROMA_PERSIST_DIR` in `config.py` |
| Graceful degradation (empty ChromaDB) | Task 5: empty guard + Task 6: seed hint |
| `TriageError` on API failure | Task 7: `generate_rca` raises `TriageError` |
| Missing API key fails fast | Task 3: `get_config()` raises `TriageError` |
| Tests: no live API calls or disk I/O | Tasks 4–7: in-memory ChromaDB + mocked Anthropic |
| README with all required sections | Task 10 |
| `console_scripts` entry point | Task 1: `pyproject.toml` |
| MCP stdio transport | Task 9: `mcp.run()` default |
| ChromaDB embedding function note | Task 10: README |
