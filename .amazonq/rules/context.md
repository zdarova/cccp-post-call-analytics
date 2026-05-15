# CCCP Post-Call Analytics - Project Rules

## Project Context
Batch processing pipeline for call recordings. Extracts knowledge, generates metadata, discovers themes, and suggests guidance improvements.

## Current State
- Pipeline code ready, not yet triggered with real recordings
- PostgreSQL tables seeded with sample data (7 calls, 6 themes)
- Whisper model deployed in Azure OpenAI (westeurope)
- Blob Storage containers ready: `recordings/`, `transcripts/`

## Architecture
```
Blob Storage (recordings) → Azure Data Factory (orchestration) → Pipeline:
    1. Whisper transcription (Azure OpenAI)
    2. GPT-5.4 enrichment (summary, tags, sentiment, NPS, quality)
    3. Embedding + chunking → pgvector (call_transcripts collection)
    4. Structured metadata → PostgreSQL (call_metadata table)
    5. Theme discovery (HDBSCAN clustering + GPT-5.4 labeling)
    6. Guidance gap analysis (compare calls vs guidance docs)
```

## Data Model (PostgreSQL)
- `call_metadata`: call_id, customer_id, agent_id, call_date, duration, summary, tags[], sentiment, nps, quality, resolution_status, commercial_opportunity
- `discovered_themes`: theme, frequency, is_new, sentiment_correlation, call_count
- `call_transcripts` (pgvector): chunked transcript embeddings for RAG

## Key Design Decisions
- **Whisper** for transcription (better quality than real-time STT for recordings)
- **PostgreSQL** stores everything (replaces Snowflake for PoC)
- **HDBSCAN** for theme clustering (density-based, finds arbitrary-shaped clusters)
- **Azure Data Factory** for orchestration (client's existing tool)
- **GitHub Actions** as alternative trigger for PoC (no ADF setup needed)

## CI/CD
- `pipeline/` changes → `pipeline.yml` (install deps + ready to run)
- Manual trigger via `workflow_dispatch` with blob path input
- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`
- OIDC federated auth

## Tech Stack
- Python 3.12
- Azure OpenAI (Whisper + GPT-5.4 + text-embedding-3-small)
- PostgreSQL pgvector + structured tables
- HDBSCAN, scikit-learn
- Azure Blob Storage, Azure Data Factory
