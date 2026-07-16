import os
import sys
import logging

# Ensure python path has agent folder
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent"))

from src.db import get_pg_connection

def run_migration():
    print("🚀 Starting Web App database migrations...")
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            # 1. Create web_sessions table
            print("   Creating public.web_sessions table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.web_sessions (
                    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    business_id TEXT REFERENCES public.businesses(business_id) ON DELETE CASCADE,
                    visitor_ip TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            
            # 2. Create public.web_chat_messages table
            print("   Creating public.web_chat_messages table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.web_chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id UUID REFERENCES public.web_sessions(session_id) ON DELETE CASCADE,
                    sender VARCHAR(50) NOT NULL, -- 'visitor' | 'assistant' | 'staff' | 'system'
                    message TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            
            # 3. Reload Supabase PostgREST schema cache
            print("   Reloading Supabase schema cache...")
            cur.execute("NOTIFY pgrst, 'reload schema';")
            
            conn.commit()
            print("🎉 Database migrations completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
