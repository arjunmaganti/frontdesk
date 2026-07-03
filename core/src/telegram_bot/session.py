import sqlite3
import time
import difflib
from datetime import datetime
import src.config as config

DB_PATH = "state.db"

def get_db_connection(db_path=DB_PATH):
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=DB_PATH):
    """Creates the database schema if it doesn't already exist."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Daily usage table to track LLM costs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                date TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)
        
        # 2. Rate limiter table for spam protection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limiter (
                chat_id TEXT,
                timestamp REAL
            )
        """)
        
        # 3. Session state mapping for active handoffs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_relay (
                visitor_chat_id TEXT PRIMARY KEY,
                is_paused INTEGER DEFAULT 0,
                active_reply_to TEXT,
                pending_question TEXT
            )
        """)
        
        # Migrating existing databases to include the pending_question column if missing
        try:
            cursor.execute("ALTER TABLE admin_relay ADD COLUMN pending_question TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists
            
        # 4. Cache resolved QA for future escalations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS escalations_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT UNIQUE,
                answer TEXT,
                timestamp REAL
            )
        """)
        
        conn.commit()

def check_daily_cap(db_path=DB_PATH) -> bool:
    """Returns True if the tenant's daily message cap has been exceeded, otherwise False."""
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count FROM daily_usage WHERE date = ?", (current_date,))
        row = cursor.fetchone()
        
        if row and row["count"] >= config.DAILY_MESSAGE_CAP:
            return True
        return False

def increment_daily_usage(db_path=DB_PATH):
    """Increments the daily message count for the current date."""
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        # Upsert date count
        cursor.execute("""
            INSERT INTO daily_usage (date, count) 
            VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET count = count + 1
        """, (current_date,))
        conn.commit()

def check_rate_limit(chat_id: str, db_path=DB_PATH) -> bool:
    """
    Returns True if the user is spamming (exceeded message limit within the window).
    Otherwise registers the message timestamp and returns False.
    """
    now = time.time()
    cutoff = now - config.USER_RATE_WINDOW
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Clean up old logs outside the rate window
        cursor.execute("DELETE FROM rate_limiter WHERE timestamp < ?", (cutoff,))
        
        # 2. Count messages in current window for this user
        cursor.execute("SELECT COUNT(*) as count FROM rate_limiter WHERE chat_id = ?", (chat_id,))
        count = cursor.fetchone()["count"]
        
        if count >= config.USER_RATE_LIMIT:
            return True  # Rate limit exceeded (spamming)
            
        # 3. Log current message timestamp
        cursor.execute("INSERT INTO rate_limiter (chat_id, timestamp) VALUES (?, ?)", (chat_id, now))
        conn.commit()
        return False

def is_visitor_paused(visitor_chat_id: str, db_path=DB_PATH) -> bool:
    """Returns True if the visitor's AI session is muted (human handoff is active)."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_paused FROM admin_relay WHERE visitor_chat_id = ?", (visitor_chat_id,))
        row = cursor.fetchone()
        if row:
            return row["is_paused"] == 1
        return False

def set_visitor_paused(visitor_chat_id: str, is_paused: bool, db_path=DB_PATH):
    """Sets the is_paused status for a visitor's AI session."""
    val = 1 if is_paused else 0
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_relay (visitor_chat_id, is_paused)
            VALUES (?, ?)
            ON CONFLICT(visitor_chat_id) DO UPDATE SET is_paused = ?
        """, (visitor_chat_id, val, val))
        conn.commit()

def set_active_visitor(visitor_chat_id: str, db_path=DB_PATH):
    """Sets which visitor the admin's next messages will be relayed to."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        # First clear any active reply pointers
        cursor.execute("UPDATE admin_relay SET active_reply_to = NULL")
        # Set the active pointer for this visitor
        cursor.execute("""
            INSERT INTO admin_relay (visitor_chat_id, active_reply_to)
            VALUES (?, ?)
            ON CONFLICT(visitor_chat_id) DO UPDATE SET active_reply_to = ?
        """, (visitor_chat_id, visitor_chat_id, visitor_chat_id))
        conn.commit()

def get_active_visitor(db_path=DB_PATH) -> str:
    """Returns the visitor Chat ID that is currently targeted for admin replies, or None."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT visitor_chat_id FROM admin_relay WHERE active_reply_to IS NOT NULL")
        row = cursor.fetchone()
        if row:
            return row["visitor_chat_id"]
        return None

def clear_active_visitor(db_path=DB_PATH):
    """Clears the active reply pointer for the admin."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE admin_relay SET active_reply_to = NULL")
        conn.commit()

def save_pending_question(visitor_chat_id: str, question: str, db_path=DB_PATH):
    """Saves the visitor's latest unanswered question to their session state."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_relay (visitor_chat_id, pending_question)
            VALUES (?, ?)
            ON CONFLICT(visitor_chat_id) DO UPDATE SET pending_question = ?
        """, (visitor_chat_id, question, question))
        conn.commit()

def get_pending_question(visitor_chat_id: str, db_path=DB_PATH) -> str:
    """Gets the visitor's pending unanswered question."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pending_question FROM admin_relay WHERE visitor_chat_id = ?", (visitor_chat_id,))
        row = cursor.fetchone()
        if row:
            return row["pending_question"]
        return None

def save_resolved_qa(question: str, answer: str, db_path=DB_PATH):
    """Saves a resolved Q&A pair into the escalations cache."""
    if not question or not answer:
        return
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO escalations_cache (question, answer, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(question) DO UPDATE SET answer = ?, timestamp = ?
        """, (question, answer, time.time(), answer, time.time()))
        conn.commit()

def find_cached_answer(query: str, db_path=DB_PATH) -> str:
    """Fuzzy searches for a previously resolved QA pair in SQLite."""
    if not query:
        return None
        
    normalized_query = query.strip().lower()
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer FROM escalations_cache")
        rows = cursor.fetchall()
        
        best_ratio = 0.0
        best_answer = None
        
        for row in rows:
            q = row["question"].strip().lower()
            
            # 1. Exact match
            if normalized_query == q:
                return row["answer"]
                
            # 2. Fuzzy match ratio
            ratio = difflib.SequenceMatcher(None, normalized_query, q).ratio()
            if ratio > 0.85:
                return row["answer"]
                
            # 3. Fallback to word-overlap checks
            q_words = set(q.split())
            query_words = set(normalized_query.split())
            if len(q_words) > 0 and len(query_words) > 0:
                overlap = len(q_words.intersection(query_words)) / max(len(q_words), len(query_words))
                if overlap > 0.80 and ratio > best_ratio:
                    best_ratio = ratio
                    best_answer = row["answer"]
                    
        if best_ratio > 0.70:
            return best_answer
            
    return None
