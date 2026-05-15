# CCCP - Post-Call Analytics Pipeline

Batch processing of call recordings for knowledge extraction and quality analysis.

## What it does

```
Call Recordings (Blob) → Transcription (Whisper) → Analysis Pipeline:
    ├─ Theme Discovery (clustering + LLM labeling)
    ├─ Extended Metadata (summary, tags, sentiment, NPS, quality score)
    ├─ Guidance Improvement Suggestions (compare calls vs. guidance)
    └─ Knowledge Repository (Snowflake + AI Search index)
```

## Features

- **Transcription** — Azure OpenAI Whisper for batch audio-to-text
- **Theme discovery** — Embedding clustering + GPT-4o labeling of new themes
- **Extended metadata** — Per-call: transcription, summary, tags, sentiment, estimated NPS, agent quality
- **Guidance improvement** — Compares agent behavior vs. PDF guidance, suggests updates
- **Knowledge repo** — Indexed in AI Search for chatbot RAG + stored in Snowflake for BI

## Pipeline Flow

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────────┐
│ Blob Storage │────▶│ Azure Data   │────▶│ Databricks          │
│ (recordings) │     │ Factory      │     │ (processing)        │
└──────────────┘     │ (orchestrate)│     └──────────┬──────────┘
                     └──────────────┘                │
                                                     ▼
                     ┌───────────────────────────────────────────┐
                     │  1. Whisper transcription                  │
                     │  2. GPT-4o: summary + tags + sentiment     │
                     │  3. Embedding → clustering → theme labels  │
                     │  4. NPS estimation + agent quality score   │
                     │  5. Guidance gap analysis                  │
                     └───────────────────────────────┬───────────┘
                                                     │
                          ┌──────────────────────────┼──────────┐
                          ▼                          ▼          ▼
                   ┌─────────────┐         ┌──────────┐  ┌──────────┐
                   │ AI Search   │         │Snowflake │  │ Cosmos   │
                   │ (RAG index) │         │ (DWH)    │  │ (metadata)│
                   └─────────────┘         └──────────┘  └──────────┘
```

## Run Locally

```bash
export AZURE_OPENAI_ENDPOINT="https://..."
export AZURE_OPENAI_KEY="<key>"
export SNOWFLAKE_ACCOUNT="<account>"
export SNOWFLAKE_USER="<user>"
export SNOWFLAKE_PASSWORD="<password>"
export AZURE_STORAGE_CONNECTION="<connection_string>"

pip install -r requirements.txt
python pipeline/run.py --input-path recordings/ --local
```

## Related Repos

- **cccp-platform-infra** — Bicep IaC for all Azure resources
- **cccp-realtime-agent** — Real-time call processing
- **cccp-chatbot** — Multi-agent Teams chatbot
