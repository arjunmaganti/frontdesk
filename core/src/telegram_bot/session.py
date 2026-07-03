import sqlite3
import time
import difflib
from datetime import datetime
import src.config as config
from src.db import get_pg_connection

LOCAL_DB_PATH = "state.db"

# =====================================================================
# 1. Local SQLite Helpers (Low-Latency Rate Limiter & Message Cap)
# =====================================================================

def get_local_connection(db_path=LOCAL_DB_PATH):
    """Establishes and returns a connection to the local SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=LOCAL_DB_PATH):
    """Creates the local database tables for transient cap and rate calculations."""
    with get_local_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Daily usage table to track LLM costs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                date TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)
        
        # Rate limiter table for spam protection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limiter (
                chat_id TEXT,
                timestamp REAL
            )
        """)
        conn.commit()

def check_daily_cap(db_path=LOCAL_DB_PATH) -> bool:
    """Returns True if the tenant's daily message cap has been exceeded, otherwise False."""
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    with get_local_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count FROM daily_usage WHERE date = ?", (current_date,))
        row = cursor.fetchone()
        
        if row and row["count"] >= config.DAILY_MESSAGE_CAP:
            return True
        return False

def increment_daily_usage(db_path=LOCAL_DB_PATH):
    """Increments the daily message count for the current date."""
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    with get_local_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_usage (date, count) 
            VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET count = count + 1
        """, (current_date,))
        conn.commit()

def check_rate_limit(chat_id: str, db_path=LOCAL_DB_PATH) -> bool:
    """Returns True if the user has exceeded their spam limit inside the rate window."""
    now = time.time()
    cutoff = now - config.USER_RATE_WINDOW
    
    with get_local_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rate_limiter WHERE timestamp < ?", (cutoff,))
        cursor.execute("SELECT COUNT(*) as count FROM rate_limiter WHERE chat_id = ?", (chat_id,))
        count = cursor.fetchone()["count"]
        
        if count >= config.USER_RATE_LIMIT:
            return True
            
        cursor.execute("INSERT INTO rate_limiter (chat_id, timestamp) VALUES (?, ?)", (chat_id, now))
        conn.commit()
        return False


# =====================================================================
# 2. Supabase PostgreSQL Helpers (Relays, Configuration & Cache)
# =====================================================================

def get_visitor_business(visitor_chat_id: str) -> str:
    """Retrieves the active business ID linked to the visitor from Supabase."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT active_business_id FROM public.visitors WHERE visitor_chat_id = %s", (visitor_chat_id,))
            row = cur.fetchone()
            if row:
                return row[0]
            return None
    finally:
        conn.close()

def set_visitor_business(visitor_chat_id: str, business_id: str):
    """Binds the visitor to their active business in Supabase."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.visitors (visitor_chat_id, active_business_id)
                VALUES (%s, %s)
                ON CONFLICT (visitor_chat_id) DO UPDATE SET active_business_id = EXCLUDED.active_business_id
                """,
                (visitor_chat_id, business_id)
            )
            conn.commit()
    finally:
        conn.close()

def get_business_config(business_id: str) -> dict:
    """Gets all settings (name, agent, phone, address, map_url, timezone, admin_chat_id) for a business."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT business_name, agent_name, website_url, business_phone, 
                       business_address, map_url, business_timezone, admin_chat_id,
                       active_visitor_chat_id
                FROM public.businesses 
                WHERE business_id = %s
                """,
                (business_id,)
            )
            row = cur.fetchone()
            if row:
                return {
                    "business_id": business_id,
                    "business_name": row[0],
                    "agent_name": row[1],
                    "website_url": row[2],
                    "business_phone": row[3],
                    "business_address": row[4],
                    "map_url": row[5],
                    "business_timezone": row[6],
                    "admin_chat_id": row[7],
                    "active_visitor_chat_id": row[8]
                }
            return None
    finally:
        conn.close()

def bind_business_admin(business_id: str, admin_chat_id: str) -> str:
    """Associates the owner's Telegram chat_id with their registered business ID."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            # Check if business exists
            cur.execute("SELECT business_name FROM public.businesses WHERE business_id = %s", (business_id,))
            row = cur.fetchone()
            if not row:
                return None # Business not found
            
            cur.execute(
                "UPDATE public.businesses SET admin_chat_id = %s WHERE business_id = %s",
                (admin_chat_id, business_id)
            )
            conn.commit()
            return row[0] # Return business name
    finally:
        conn.close()

def is_visitor_paused(visitor_chat_id: str) -> bool:
    """Returns True if the visitor's AI session is muted (human handoff is active)."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT is_paused FROM public.admin_relay WHERE visitor_chat_id = %s", (visitor_chat_id,))
            row = cur.fetchone()
            if row:
                return bool(row[0])
            return False
    finally:
        conn.close()

def set_visitor_paused(visitor_chat_id: str, is_paused: bool, business_id: str):
    """Sets the is_paused status for a visitor's AI session in Supabase."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.admin_relay (visitor_chat_id, business_id, is_paused)
                VALUES (%s, %s, %s)
                ON CONFLICT (visitor_chat_id) DO UPDATE SET is_paused = EXCLUDED.is_paused
                """,
                (visitor_chat_id, business_id, is_paused)
            )
            conn.commit()
    finally:
        conn.close()

def get_business_by_admin(admin_chat_id: str) -> dict:
    """Finds a business configuration where this admin_chat_id is registered."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT business_id, business_name FROM public.businesses WHERE admin_chat_id = %s LIMIT 1",
                (admin_chat_id,)
            )
            row = cur.fetchone()
            if row:
                return {"business_id": row[0], "business_name": row[1]}
            return None
    finally:
        conn.close()

def set_active_visitor_for_admin(business_id: str, visitor_chat_id: str):
    """Sets which visitor the admin's next messages will be routed/relayed to."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE public.businesses SET active_visitor_chat_id = %s WHERE business_id = %s",
                (visitor_chat_id, business_id)
            )
            conn.commit()
    finally:
        conn.close()

def get_active_visitor_for_admin(admin_chat_id: str) -> str:
    """Retrieves the visitor chat ID currently targeted for admin replies."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT active_visitor_chat_id FROM public.businesses WHERE admin_chat_id = %s AND active_visitor_chat_id IS NOT NULL",
                (admin_chat_id,)
            )
            row = cur.fetchone()
            if row:
                return row[0]
            return None
    finally:
        conn.close()

def clear_active_visitor_for_admin(business_id: str):
    """Clears the active reply pointer for the business admin."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE public.businesses SET active_visitor_chat_id = NULL WHERE business_id = %s", (business_id,))
            conn.commit()
    finally:
        conn.close()

def save_pending_question(visitor_chat_id: str, question: str, business_id: str):
    """Saves the visitor's latest unanswered question to the relay state in Supabase."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.admin_relay (visitor_chat_id, business_id, pending_question)
                VALUES (%s, %s, %s)
                ON CONFLICT (visitor_chat_id) DO UPDATE SET pending_question = EXCLUDED.pending_question
                """,
                (visitor_chat_id, business_id, question)
            )
            conn.commit()
    finally:
        conn.close()

def get_pending_question(visitor_chat_id: str) -> str:
    """Gets the visitor's pending unanswered question."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pending_question FROM public.admin_relay WHERE visitor_chat_id = %s", (visitor_chat_id,))
            row = cur.fetchone()
            if row:
                return row[0]
            return None
    finally:
        conn.close()

def save_resolved_qa(business_id: str, question: str, answer: str):
    """Saves a resolved Q&A pair into the escalations cache table in Supabase."""
    if not question or not answer:
        return
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.escalations_cache (business_id, question, answer, timestamp)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (business_id, question) DO UPDATE SET answer = EXCLUDED.answer, timestamp = NOW()
                """,
                (business_id, question, answer)
            )
            conn.commit()
    finally:
        conn.close()

def find_cached_answer(business_id: str, query: str) -> str:
    """Fuzzy searches for a previously resolved QA pair inside the Supabase cache."""
    if not query or not business_id:
        return None
        
    normalized_query = query.strip().lower()
    
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT question, answer FROM public.escalations_cache WHERE business_id = %s", (business_id,))
            rows = cur.fetchall()
            
            best_ratio = 0.0
            best_answer = None
            
            for row in rows:
                q = row[0].strip().lower()
                
                # 1. Exact match
                if normalized_query == q:
                    return row[1]
                    
                # 2. Fuzzy match ratio
                ratio = difflib.SequenceMatcher(None, normalized_query, q).ratio()
                if ratio > 0.85:
                    return row[1]
                    
                # 3. Fallback to word-overlap checks
                q_words = set(q.split())
                query_words = set(normalized_query.split())
                if len(q_words) > 0 and len(query_words) > 0:
                    overlap = len(q_words.intersection(query_words)) / max(len(q_words), len(query_words))
                    if overlap > 0.80 and ratio > best_ratio:
                        best_ratio = ratio
                        best_answer = row[1]
                        
            if best_ratio > 0.70:
                return best_answer
                
        return None
    finally:
        conn.close()
