"""CCCP Post-Call Analytics Pipeline - processes recordings into knowledge."""

import os
import json
import logging
from datetime import datetime
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_postgres.vectorstores import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO)


def _get_llm():
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_KEY"],
        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"),
        api_version="2024-06-01",
        temperature=0.1, max_tokens=2048,
    )


def _pg_conn() -> str:
    pg = os.environ["PG_CONNECTION_STRING"]
    parts = dict(p.split("=", 1) for p in pg.split() if "=" in p)
    return f"postgresql+psycopg://{parts['user']}:{parts['password']}@{parts['host']}:{parts['port']}/{parts['dbname']}?sslmode={parts.get('sslmode', 'require')}"


def _get_vectorstore():
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_KEY"],
        azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
        api_version="2024-06-01",
    )
    return PGVector(
        connection=_pg_conn(),
        embeddings=embeddings,
        collection_name="call_transcripts",
    )


# --- Step 1: Transcription ---

def transcribe_recording(audio_path: str) -> str:
    """Transcribe audio using Azure OpenAI Whisper."""
    import openai
    client = openai.AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_KEY"],
        api_version="2024-06-01",
    )
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper", file=f, language="it"
        )
    return result.text


# --- Step 2: Enrichment ---

ENRICH_PROMPT = ChatPromptTemplate.from_template(
    "Analyse this call transcript and generate structured metadata.\n\n"
    "Transcript:\n{transcript}\n\n"
    "Generate JSON with:\n"
    '{{"summary": "<50 word summary>", "tags": ["tag1", "tag2", ...], '
    '"sentiment": <-1.0 to 1.0>, "estimated_nps": <0-10>, '
    '"agent_quality": <1-5>, "key_issues": ["issue1", ...], '
    '"resolution_status": "resolved|unresolved|partial", '
    '"commercial_opportunity": "none|cross_sell|upsell|retention"}}'
)


def enrich_transcript(transcript: str, metadata: dict) -> dict:
    """Generate extended metadata for a call transcript."""
    llm = _get_llm()
    result = (ENRICH_PROMPT | llm).invoke({"transcript": transcript[:4000]})
    try:
        enriched = json.loads(result.content)
    except Exception:
        enriched = {"summary": "", "tags": [], "sentiment": 0, "estimated_nps": 5,
                    "agent_quality": 3, "key_issues": [], "resolution_status": "unknown",
                    "commercial_opportunity": "none"}

    enriched.update(metadata)
    enriched["processed_at"] = datetime.utcnow().isoformat()
    return enriched


# --- Step 3: Embed and Index ---

def index_transcript(transcript: str, metadata: dict):
    """Chunk, embed, and store transcript in pgvector."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)
    from langchain.schema import Document

    chunks = splitter.split_text(transcript)
    docs = [
        Document(
            page_content=chunk,
            metadata={**metadata, "chunk_index": i}
        )
        for i, chunk in enumerate(chunks)
    ]

    vs = _get_vectorstore()
    vs.add_documents(docs)
    logging.info(f"  Indexed {len(docs)} chunks for call {metadata.get('call_id', 'unknown')}")


# --- Step 4: Theme Discovery ---

THEME_PROMPT = ChatPromptTemplate.from_template(
    "Analyse these call summaries and identify the top emerging themes.\n\n"
    "Summaries:\n{summaries}\n\n"
    "Identify:\n"
    "1. Top 5 themes (with frequency: high/medium/low)\n"
    "2. Any NEW themes not previously seen\n"
    "3. Themes correlated with negative sentiment\n\n"
    "Reply as JSON array: [{{\"theme\": \"...\", \"frequency\": \"...\", \"is_new\": true/false, \"sentiment_correlation\": \"positive/negative/neutral\"}}]"
)


def discover_themes(summaries: list[str]) -> list[dict]:
    """Discover themes from a batch of call summaries."""
    llm = _get_llm()
    result = (THEME_PROMPT | llm).invoke({"summaries": "\n".join(summaries[:20])})
    try:
        return json.loads(result.content)
    except Exception:
        return []


# --- Step 5: Guidance Gap Analysis ---

GUIDANCE_GAP_PROMPT = ChatPromptTemplate.from_template(
    "Compare these call scenarios with the current agent guidance.\n\n"
    "Call issues encountered:\n{issues}\n\n"
    "Current guidance covers:\n{guidance}\n\n"
    "Identify:\n"
    "1. Gaps: situations agents face that guidance doesn't cover\n"
    "2. Improvement suggestions for existing guidance\n"
    "3. Priority (high/medium/low) for each suggestion\n\n"
    "Reply as JSON array: [{{\"gap\": \"...\", \"suggestion\": \"...\", \"priority\": \"...\"}}]"
)


def analyse_guidance_gaps(issues: list[str], guidance_text: str) -> list[dict]:
    """Identify gaps between agent guidance and real call scenarios."""
    llm = _get_llm()
    result = (GUIDANCE_GAP_PROMPT | llm).invoke({
        "issues": "\n".join(issues[:15]),
        "guidance": guidance_text[:3000],
    })
    try:
        return json.loads(result.content)
    except Exception:
        return []


# --- Main Pipeline ---

def process_call(audio_path: str, metadata: dict) -> dict:
    """Full pipeline for a single call recording."""
    logging.info(f"Processing: {metadata.get('call_id', audio_path)}")

    # Step 1: Transcribe
    transcript = transcribe_recording(audio_path)
    logging.info(f"  Transcribed: {len(transcript)} chars")

    # Step 2: Enrich
    enriched = enrich_transcript(transcript, metadata)
    logging.info(f"  Enriched: sentiment={enriched.get('sentiment')}, nps={enriched.get('estimated_nps')}")

    # Step 3: Index
    index_transcript(transcript, {**metadata, **enriched})

    return {"transcript": transcript, "metadata": enriched}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python run.py <audio_file> [--metadata '{...}']")
        sys.exit(1)

    audio = sys.argv[1]
    meta = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {"call_id": "test-001"}
    result = process_call(audio, meta)
    print(json.dumps(result["metadata"], indent=2, ensure_ascii=False))
