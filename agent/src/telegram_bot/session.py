import time
import difflib
from datetime import date
from collections import defaultdict
import src.config as config
from src.db import get_pg_connection

# In-memory dictionary to track rate limiting timestamps per chat ID
_rate_limit_cache = defaultdict(list)

# =====================================================================
# 1. Stateless / Hybrid Helpers (In-Memory Limiter & Supabase Message Cap)
# =====================================================================

def init_db():
    """Dummy function for backward compatibility (no local SQLite db required)."""
    pass

def check_daily_cap() -> bool:
    """Returns True if the global daily message cap has been exceeded, otherwise False."""
    today = date.today().isoformat()
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT message_count FROM public.daily_usage WHERE usage_date = %s", (today,))
            row = cur.fetchone()
            if row and row[0] >= config.DAILY_MESSAGE_CAP:
                return True
            return False
    finally:
        conn.close()

def increment_daily_usage():
    """Increments the global daily message count in Supabase."""
    today = date.today().isoformat()
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.daily_usage (usage_date, message_count) 
                VALUES (%s, 1)
                ON CONFLICT(usage_date) DO UPDATE SET message_count = public.daily_usage.message_count + 1
                """,
                (today,)
            )
            conn.commit()
    finally:
        conn.close()

def check_rate_limit(chat_id: str) -> bool:
    """In-memory rate limiter to protect the bot from spam (zero latency)."""
    now = time.time()
    cutoff = now - config.USER_RATE_WINDOW
    
    # Filter out expired timestamps
    timestamps = [ts for ts in _rate_limit_cache[chat_id] if ts > cutoff]
    
    if len(timestamps) >= config.USER_RATE_LIMIT:
        return True
        
    timestamps.append(now)
    _rate_limit_cache[chat_id] = timestamps
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
    """Gets all settings (name, agent, phone, address, email, map_url, timezone, admin_chat_id) for a business."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT business_name, agent_name, website_url, business_phone, 
                       business_address, business_email, map_url, business_timezone, 
                       admin_chat_id, active_visitor_chat_id, flyer_url, owner_qr_url
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
                    "business_email": row[5],
                    "map_url": row[6],
                    "business_timezone": row[7],
                    "admin_chat_id": row[8],
                    "active_visitor_chat_id": row[9],
                    "flyer_url": row[10],
                    "owner_qr_url": row[11]
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

def is_authorized_admin(chat_id: str) -> bool:
    """Checks if the given Telegram chat_id belongs to any registered business administrator in the database."""
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM public.businesses WHERE admin_chat_id = %s LIMIT 1", (chat_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()
