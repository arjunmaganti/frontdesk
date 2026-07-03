import sqlite3
import time
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
                active_reply_to TEXT
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
