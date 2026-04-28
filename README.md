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

## Running Tests

```bash
pip install -e .
pip install pytest
pytest -v
```
