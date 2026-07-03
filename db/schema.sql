-- =====================================================================
-- Supabase PostgreSQL Schema Setup (Multi-Tenant pgvector Architecture)
-- =====================================================================

-- 1. Enable pgvector extension for semantic search
create extension if not exists vector;

-- 2. Create Businesses Table (Tenant Metadata & Settings)
create table if not exists public.businesses (
    business_id text primary key,
    business_name text not null,
    agent_name text not null default 'Kim',
    website_url text not null,
    business_phone text,
    business_address text,
    map_url text,
    business_timezone text not null default 'America/Los_Angeles',
    admin_chat_id text,
    active_visitor_chat_id text,
    created_at timestamptz not null default now()
);

-- 3. Create Visitors Table (User Session Routing)
create table if not exists public.visitors (
    visitor_chat_id text primary key,
    active_business_id text references public.businesses(business_id) on delete set null
);

-- 4. Create Admin Relay Table (Escalation Takeover States)
create table if not exists public.admin_relay (
    visitor_chat_id text primary key,
    business_id text references public.businesses(business_id) on delete cascade,
    is_paused boolean not null default false,
    pending_question text
);

-- 5. Create Knowledge Chunks Table (Unified Vector DB Chunks)
create table if not exists public.knowledge_chunks (
    id uuid primary key default gen_random_uuid(),
    business_id text references public.businesses(business_id) on delete cascade,
    content text not null,
    embedding vector(1536) not null,
    metadata jsonb,
    created_at timestamptz not null default now()
);

-- Create an HNSW index on the vector embedding column for fast cosine searches
create index if not exists knowledge_chunks_embedding_idx 
on public.knowledge_chunks 
using hnsw (embedding vector_cosine_ops);

-- 6. Create Escalations Cache Table (Fuzzy Q&A Resolved Records)
create table if not exists public.escalations_cache (
    id bigint generated always as identity primary key,
    business_id text references public.businesses(business_id) on delete cascade,
    question text not null,
    answer text not null,
    timestamp timestamptz not null default now()
);

-- Ensure Q&A entries are unique per business
create unique index if not exists escalations_cache_unique_idx 
on public.escalations_cache (business_id, question);

-- 7. Create Crawl Jobs Table (Crawler Task Queue)
create table if not exists public.crawl_jobs (
    id uuid primary key default gen_random_uuid(),
    business_id text references public.businesses(business_id) on delete cascade,
    website_url text not null,
    status text not null default 'pending', -- 'pending' | 'processing' | 'completed' | 'failed'
    error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);


-- 9. Create Business Load Table (Bulk Onboarding Staging)
create table if not exists public.business_load (
    id uuid primary key default gen_random_uuid(),
    business_id text not null,
    business_name text not null,
    agent_name text not null default 'Kim',
    website_url text not null,
    business_timezone text not null default 'America/Los_Angeles',
    admin_chat_id text,
    status text not null default 'pending', -- 'pending' | 'processing' | 'completed' | 'failed'
    error_message text,
    created_at timestamptz not null default now(),
    processed_at timestamptz
);

-- 10. Create Business Load Trigger Function (Staging Ingestion)
create or replace function public.process_business_load_row()
returns trigger as $$
begin
    if new.status = 'pending' then
        -- A. Upsert into the main businesses table
        insert into public.businesses (
            business_id, 
            business_name, 
            agent_name, 
            website_url, 
            business_timezone, 
            admin_chat_id
        )
        values (
            new.business_id, 
            new.business_name, 
            new.agent_name, 
            new.website_url, 
            new.business_timezone, 
            new.admin_chat_id
        )
        on conflict (business_id) do update set
            business_name = excluded.business_name,
            agent_name = excluded.agent_name,
            website_url = excluded.website_url,
            business_timezone = excluded.business_timezone,
            admin_chat_id = coalesce(excluded.admin_chat_id, public.businesses.admin_chat_id);

        -- B. Automatically queue a crawl job
        insert into public.crawl_jobs (business_id, website_url, status)
        values (new.business_id, new.website_url, 'pending');

        -- C. Update the staging row status
        new.status := 'completed';
        new.processed_at := now();
    end if;
    return new;
end;
$$ language plpgsql;

-- Bind trigger to run before insert on business_load
drop trigger if exists trigger_process_business_load on public.business_load;
create trigger trigger_process_business_load
before insert on public.business_load
for each row
execute function public.process_business_load_row();
