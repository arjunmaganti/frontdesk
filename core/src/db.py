import os
import psycopg2
from psycopg2.extras import RealDictCursor
from supabase import create_client, Client
import src.config as config

def get_supabase_client() -> Client:
    """Initializes and returns a Supabase API Client."""
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Supabase URL and Service Role Key must be set in the configuration.")
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)

def get_pg_connection():
    """Establishes and returns a direct connection to the Supabase PostgreSQL database."""
    if not config.SUPABASE_URL or not config.SUPABASE_DB_PASSWORD:
        raise ValueError("Supabase URL and DB Password must be set in the configuration.")
    
    # Extract project reference ID from Supabase URL
    # e.g., "huwvkafsezzvvqjjjllw" from "https://huwvkafsezzvvqjjjllw.supabase.co"
    project_ref = config.SUPABASE_URL.split("//")[-1].split(".")[0]
    
    host = f"db.{project_ref}.supabase.co"
    port = 5432
    database = "postgres"
    user = "postgres"
    password = config.SUPABASE_DB_PASSWORD
    
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    return conn
