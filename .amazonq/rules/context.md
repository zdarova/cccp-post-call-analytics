# CCCP Post-Call Analytics - Project Rules

## Project Context
This repo implements the **post-call batch processing** pipeline. It processes call recordings to extract knowledge, generate metadata, discover themes, and suggest guidance improvements.

## Architecture
```
Blob Storage (recordings + metadata) → Azure Data Factory (orchestration) → Processing:
    ├─ Step 1: Whisper transcription (Azure OpenAI)
    ├─ Step 2: Extended metadata (GPT-4o: summary, tags, sentiment, NPS, quality)
    ├─ Step 3: Embedding generation (text-embedding-3-small)
    ├─ Step 4: Theme discovery (clustering embeddings + GPT-4o labeling)
    ├─ Step 5: Guidance gap analysis (compare agent behavior vs PDF guidance)
    └─ Output: pgvector (RAG index) + Snowflake (DWH) + Cosmos DB (metadata)
```

## Key Design Decisions
- **Azure Data Factory** orchestrates the pipeline (client already uses it)
- **Databricks** for heavy compute (embedding clustering, batch inference) — client's existing platform
- **Whisper (Azure OpenAI)** for transcription — better quality than Speech-to-Text for recordings
- **pgvector** stores embeddings for RAG retrieval by the chatbot
- **Snowflake** stores structured metadata for BI dashboards and KPI queries
- **Theme discovery** uses HDBSCAN clustering on embeddings + GPT-4o to label clusters

## Pipeline Stages

### 1. Ingestion
- Recordings land in Blob Storage (from Genesys export)
- Metadata (date, time, location, agent, customer ID) arrives as JSON sidecar

### 2. Transcription
- Azure OpenAI Whisper API (batch)
- Output: timestamped transcript per call

### 3. Enrichment (per call)
- GPT-4o generates: summary (50 words), thematic tags (3-5), overall sentiment (-1 to 1), estimated NPS (0-10), agent quality score (1-5)
- Stored in Cosmos DB + Snowflake

### 4. Embedding + Indexing
- Transcript chunks embedded with text-embedding-3-small
- Stored in pgvector for chatbot RAG
- Full transcript + metadata indexed for search

### 5. Theme Discovery (batch, weekly)
- All new call embeddings clustered (HDBSCAN)
- New clusters = new themes → GPT-4o labels them
- Compared against known theme taxonomy → flag novel themes

### 6. Guidance Improvement
- Compare agent responses vs. guidance document recommendations
- Identify gaps: situations where guidance doesn't cover what agents face
- Generate improvement suggestions for guidance authors

## Tech Stack
- Python 3.12, Azure Data Factory, Databricks
- Azure OpenAI (Whisper + GPT-4o + embeddings)
- pgvector (PostgreSQL Flexible B1ms)
- Snowflake (existing DWH)
- Cosmos DB (serverless)
- HDBSCAN, scikit-learn (clustering)

## Data Lineage
Every processed call tracks: `recording_blob → transcript → embeddings → themes → metadata`
