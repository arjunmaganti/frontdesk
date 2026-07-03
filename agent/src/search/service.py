import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import src.config as config
from src.db import get_pg_connection

def query_knowledge_base(query: str, business_id: str) -> str:
    """Queries the Supabase pgvector database for matching context chunks belonging to the business."""
    if not query or not business_id:
        return ""
        
    # 1. Compute query embedding using Gemini
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=config.GEMINI_API_KEY
    )
    vector = embeddings_model.embed_query(query)
    
    # 2. Query Supabase Postgres using cosine distance operator (<=>)
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content 
                FROM public.knowledge_chunks 
                WHERE business_id = %s 
                ORDER BY embedding <=> %s::vector 
                LIMIT 3
                """,
                (business_id, str(vector))
            )
            rows = cur.fetchall()
            return "\n\n".join([row[0] for row in rows])
    finally:
        conn.close()
