# Incident Intelligence Agent — Design Spec
**Date:** 2026-04-28
**Status:** Approved

---

## Overview

A Claude Code-native MCP server and CLI tool that takes a raw incident alert (PagerDuty JSON or plain text), generates a structured RCA draft via the Claude API, searches a local ChromaDB knowledge base of past incidents for similar issues, and returns combined markdown output ready to paste into Jira or Slack.

**Primary motivation:** On-call engineers waste 30–60 minutes per incident writing the same RCA structure from scratch and searching Slack/Confluence for similar past issues. This agent does both in under 10 seconds.

**Origin:** Inspired by a similar system architected in production at Orangetheory Fitness — this is the open-source, vendor-neutral version of that workflow.

---

## Project Location

```
/Users/sarthakhans/incident-intelligence-agent/
```

Will be published to GitHub as a public repository.

---

## Architecture

**Pattern:** Layered — a `core/` library shared by both a CLI entry point and an MCP server.

```
incident-intelligence-agent/
├── pyproject.toml
├── README.md
├── .env.example
├── data/
│   └── demo_incidents.json          # 8–10 synthetic past incidents
├── src/
│   └── incident_intel/
│       ├── __init__.py
│       ├── models.py                # Pydantic models (PagerDutyAlert, Incident, RCADraft)
│       ├── config.py                # env var loading (ANTHROPIC_API_KEY, CHROMA_PERSIST_DIR, CLAUDE_MODEL)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── ingestor.py          # loads incidents into ChromaDB (idempotent)
│       │   ├── rca_generator.py     # Claude API → structured RCA markdown (with retry)
│       │   ├── similarity_search.py # ChromaDB query → top-k similar incidents
│       │   └── formatter.py         # combines RCA + similar incidents → final markdown
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py              # Click CLI entry point
│       └── mcp/
│           ├── __init__.py
│           └── server.py            # MCP SDK server (stdio transport), 3 tools
└── tests/
    ├── test_rca_generator.py
    ├── test_similarity_search.py
    ├── test_formatter.py
    └── test_ingestor.py
```

---

## Data Model

### Incident (stored in ChromaDB)

```python
# Document text (embedded for similarity search)
document = f"{title}\n{summary}\n{root_cause}"

# Metadata (returned alongside results, not embedded)
metadata = {
    "id": "INC-0042",
    "title": "Redis OOM causing checkout timeouts",
    "severity": "P1",
    "date": "2024-11-15",
    "root_cause": "Memory limit not set on Redis; cache grew unbounded",
    "resolution": "Increased memory limit + added eviction policy",
    "link": ""   # optional Jira/Confluence URL, empty string if none
}
```

### Pydantic Models (`models.py`)

```python
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

### Input handling

- If the alert input parses as valid JSON → attempt to validate as `PagerDutyAlert`; extract fields
- If JSON parsing fails → treat entire input as plain text description
- In both cases, a plain text representation is passed to the Claude prompt

---

## Claude Prompt Design

### System prompt

```
You are an expert Site Reliability Engineer specializing in incident triage and root cause analysis.

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
- Each section should be 2–5 bullet points or sentences. Do not pad.
- Do not include any text outside these six sections.
- Output only markdown. No preamble, no sign-off.
```

### User prompt

```
Analyze this incident alert and produce a structured RCA draft:

{alert_text}
```

### Model

Configurable via `CLAUDE_MODEL` env var. Default: `claude-sonnet-4-6`.

---

## ChromaDB Configuration

- **Embedding function:** ChromaDB default (`sentence-transformers/all-MiniLM-L6-v2`)
  - Note: first run pulls ~90MB model via sentence-transformers (which requires PyTorch). Documented in README.
- **Collection name:** `incidents_v1`
- **Persistence path:** `CHROMA_PERSIST_DIR` env var, default `~/.incident-intel/chroma`
- **Idempotency:** Before inserting, check `collection.get(ids=[incident.id])`. Skip if already present.

---

## MCP Tool Interface

**Transport:** stdio (required for `claude mcp add` registration)

**Registration command:**
```bash
claude mcp add incident-intel -- python -m incident_intel.mcp.server
```

### Tools

```python
@mcp.tool()
def triage_incident(alert: str) -> str:
    """
    Full incident triage: generates a structured RCA draft and finds the top 3
    similar past incidents from the knowledge base. Returns unified markdown
    ready to paste into Jira or Slack.

    Args:
        alert: Raw PagerDuty webhook JSON string or plain text incident description.
    """

@mcp.tool()
def analyze_incident(alert: str) -> str:
    """
    Generate a structured RCA draft from an incident alert using Claude.
    Does not search the knowledge base.

    Args:
        alert: Raw PagerDuty webhook JSON string or plain text incident description.
    """

@mcp.tool()
def find_similar(description: str, top_k: int = 3) -> str:
    """
    Search the local incident knowledge base for similar past incidents.
    Returns top-k results with title, severity, date, root cause, and link.

    Args:
        description: Plain text description of the incident.
        top_k: Number of similar incidents to return (default: 3).
    """
```

---

## CLI Interface

Entry point registered as `incident-intel` via `[project.scripts]` in `pyproject.toml`.

```bash
# Full triage (RCA + similar incidents)
incident-intel triage --alert '{"title": "Redis OOM", ...}'
incident-intel triage --alert-file alert.json
incident-intel triage --alert "Database connection pool exhausted on prod"

# RCA only
incident-intel analyze --alert "Redis OOM killing checkout service"

# Similarity search only
incident-intel find-similar --description "Redis OOM killing checkout service"
incident-intel find-similar --description "..." --top-k 5

# Knowledge base management
incident-intel seed                           # loads data/demo_incidents.json
incident-intel ingest --file my_incidents.json
```

Output is always printed to stdout as markdown.

---

## Output Format

One unified markdown document (works in both Jira and Slack):

```markdown
# Incident Triage Report

**Alert:** Redis OOM causing checkout timeouts
**Generated:** 2026-04-28T14:32:00Z

---

## Summary
...

## Timeline
Timeline not available — fill in manually.

## Root Cause (Hypothesis)
...

## Impact
...

## Resolution Steps
...

## Prevention / Follow-ups
...

---

## Similar Past Incidents

1. **[INC-0042] Redis OOM causing checkout timeouts** — P1 · 2024-11-15
   Root cause: Memory limit not set on Redis; cache grew unbounded
   Resolution: Increased memory limit + added eviction policy

2. **[INC-0031] Cache stampede on product catalog** — P2 · 2024-09-03
   Root cause: TTL set to 0 after deploy; all keys expired simultaneously
   Resolution: Set TTL to 300s, added jitter

3. **[INC-0018] Memcached eviction causing login failures** — P1 · 2024-06-20
   Root cause: Memcached instance undersized for session volume
   Resolution: Scaled instance, added session persistence fallback

> Searched 47 past incidents · Top 3 shown
```

If ChromaDB is empty:
```markdown
> No similar incidents found — run `incident-intel seed` to load demo data.
```

---

## Enterprise Callouts

| Concern | Implementation |
|---|---|
| Structured logging | `structlog` with log level, component, and incident ID on every log line |
| Input validation | Pydantic `PagerDutyAlert` model; falls back to plain text gracefully |
| Idempotent ingest | Check `collection.get(ids=[id])` before insert; skip duplicates |
| Retry / backoff | Tenacity `@retry(stop=stop_after_attempt(3), wait=wait_exponential())` on Claude API calls |
| Configurable persistence | `CHROMA_PERSIST_DIR` env var, default `~/.incident-intel/chroma` |
| Graceful degradation | Empty ChromaDB returns RCA + informative note, never crashes |

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Invalid JSON alert | Log warning, fall back to plain text |
| Claude API failure (after 3 retries) | Raise `TriageError` with message; CLI exits with code 1 |
| ChromaDB empty | Return RCA + "No similar incidents found" note |
| Missing `ANTHROPIC_API_KEY` | Fail fast at startup with clear message |
| Malformed ingest JSON | Log error per-record, skip bad records, continue |

---

## Testing

All tests run without live API calls or disk I/O.

| File | What it tests |
|---|---|
| `test_rca_generator.py` | Mocks Anthropic client; asserts prompt structure, section headers present in output |
| `test_similarity_search.py` | In-memory ChromaDB collection; asserts top-k count, metadata shape |
| `test_formatter.py` | Unit tests on markdown assembly with fixture RCA + similar incidents |
| `test_ingestor.py` | In-memory ChromaDB; asserts idempotency (seed twice → same document count) |

No integration tests (require live API key — noted in README).

---

## Dependencies

```toml
[project]
requires-python = ">=3.11"

[project.dependencies]
anthropic = ">=0.25"
chromadb = ">=0.5"
mcp = ">=1.0"
click = ">=8.0"
pydantic = ">=2.0"
tenacity = ">=8.0"
python-dotenv = ">=1.0"
structlog = ">=24.0"

[project.scripts]
incident-intel = "incident_intel.cli.main:cli"
```

---

## README Requirements

The README must include:

1. **One-line pitch:** "Triage incidents and generate RCA drafts in under 10 seconds — powered by Claude and a local vector knowledge base."
2. **Origin story:** "Built this after architecting a similar system in production at Orangetheory Fitness — this is the open-source, vendor-neutral version of that workflow."
3. **Quick start:** `pip install -e .` → `incident-intel seed` → `incident-intel triage --alert "..."`
4. **MCP registration:** `claude mcp add incident-intel -- python -m incident_intel.mcp.server`
5. **ChromaDB note:** First run downloads ~90MB sentence-transformers model (one-time).
6. **Demo output:** A full example triage report in a code block.
7. **Architecture diagram** (ASCII or Mermaid): ingest → ChromaDB, alert → Claude → RCA → formatter → output.
8. **Configuration table:**

   | Env var | Default | Purpose |
   |---|---|---|
   | `ANTHROPIC_API_KEY` | required | Claude API authentication |
   | `CLAUDE_MODEL` | `claude-sonnet-4-6` | Model used for RCA generation |
   | `CHROMA_PERSIST_DIR` | `~/.incident-intel/chroma` | ChromaDB persistence path |

---

## Demo Data (`data/demo_incidents.json`)

8–10 synthetic incidents covering common enterprise failure patterns:
- Redis OOM / cache eviction
- Database connection pool exhaustion
- Memory leak causing OOM kills
- Certificate expiry causing auth failures
- Deployment rollback (bad config push)
- CDN misconfiguration causing 5xx spike
- Disk full on logging host
- Third-party API timeout cascade
