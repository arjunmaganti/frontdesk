-- =====================================================================
-- Unified Schema Initialization for Scaled Multi-Tenant Platform
-- =====================================================================

-- 1. Cascading cleanup of previous structures (for clean rebuilds)
drop trigger if exists trigger_process_business_load on public.business_load cascade;
drop function if exists public.process_business_load_row() cascade;
drop table if exists public.business_load cascade;
drop table if exists public.daily_usage cascade;
drop table if exists public.crawl_jobs cascade;
drop table if exists public.escalations_cache cascade;
drop table if exists public.knowledge_chunks cascade;
drop table if exists public.admin_relay cascade;
drop table if exists public.visitors cascade;
drop table if exists public.businesses cascade;

-- 2. Enable pgvector extension for semantic search
create extension if not exists vector;

-- 3. Create Daily Usage Table (Stateless Budget Cap persistence)
create table public.daily_usage (
    usage_date date primary key default current_date,
    message_count integer not null default 0
);

-- 4. Create Businesses Table (Tenant Metadata & Settings)
create table public.businesses (
    business_id text primary key,
    business_name text not null,
    agent_name text not null default 'Kim',
    website_url text not null,
    business_phone text,
    business_address text,
    business_email text, -- Deterministic email override
    map_url text,        -- Deterministic map url override
    business_timezone text not null default 'America/Los_Angeles',
    admin_chat_id text,
    active_visitor_chat_id text,
    flyer_url text,      -- Public Supabase Storage URL to the PDF flyer
    owner_qr_url text,   -- Public Supabase Storage URL to the Owner Activation QR image
    created_at timestamptz not null default now()
);

-- 5. Create Visitors Table (Active Session Mapping)
create table public.visitors (
    visitor_chat_id text primary key,
    active_business_id text references public.businesses(business_id) on delete cascade,
    created_at timestamptz not null default now()
);

-- 6. Create Admin Relay Table (Handoff State & Question Logging)
create table public.admin_relay (
    visitor_chat_id text primary key,
    business_id text references public.businesses(business_id) on delete cascade,
    is_paused boolean not null default false,
    pending_question text
);

-- 7. Create Knowledge Chunks Table (Unified Vector DB Chunks)
-- (No index defined on embedding because 3072 dimensions exceed pgvector index limits. 
-- Scoping searches by business_id ensures sub-millisecond sequential scans).
create table public.knowledge_chunks (
    id uuid primary key default gen_random_uuid(),
    business_id text references public.businesses(business_id) on delete cascade,
    content text not null,
    embedding vector(3072) not null,
    metadata jsonb,
    created_at timestamptz not null default now()
);

-- 8. Create Escalations Cache Table (Fuzzy Q&A Resolved Records)
create table public.escalations_cache (
    id bigint generated always as identity primary key,
    business_id text references public.businesses(business_id) on delete cascade,
    question text not null,
    answer text not null,
    timestamp timestamptz not null default now(),
    constraint unique_business_question unique (business_id, question)
);

-- 9. Create Crawl Jobs Table (Crawler Task Queue)
create table public.crawl_jobs (
    id uuid primary key default gen_random_uuid(),
    business_id text references public.businesses(business_id) on delete cascade,
    website_url text not null,
    status text not null default 'pending', -- 'pending' | 'processing' | 'completed' | 'failed'
    error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 10. Create Business Load Table (Bulk Onboarding Staging Queue with Optional Overrides)
create table public.business_load (
    id uuid primary key default gen_random_uuid(),
    business_id text not null,
    business_name text not null,
    agent_name text not null default 'Kim',
    website_url text not null,
    business_timezone text not null default 'America/Los_Angeles',
    admin_chat_id text,
    business_phone text,   -- Optional override
    business_address text, -- Optional override
    business_email text,   -- Optional override
    map_url text,          -- Optional override
    status text not null default 'pending', -- 'pending' | 'processing' | 'completed' | 'failed'
    error_message text,
    created_at timestamptz not null default now(),
    processed_at timestamptz
);

-- 11. Create Business Ingestion Function
create or replace function public.process_business_load_row()
returns trigger as $$
begin
    if new.status = 'pending' then
        -- A. Upsert business profile metadata, transferring overrides if provided
        insert into public.businesses (
            business_id, 
            business_name, 
            agent_name, 
            website_url, 
            business_timezone, 
            admin_chat_id,
            business_phone,
            business_address,
            business_email,
            map_url
        )
        values (
            new.business_id, 
            new.business_name, 
            new.agent_name, 
            new.website_url, 
            new.business_timezone, 
            new.admin_chat_id,
            new.business_phone,
            new.business_address,
            new.business_email,
            new.map_url
        )
        on conflict (business_id) do update set
            business_name = excluded.business_name,
            agent_name = excluded.agent_name,
            website_url = excluded.website_url,
            business_timezone = excluded.business_timezone,
            admin_chat_id = coalesce(excluded.admin_chat_id, public.businesses.admin_chat_id),
            business_phone = coalesce(excluded.business_phone, public.businesses.business_phone),
            business_address = coalesce(excluded.business_address, public.businesses.business_address),
            business_email = coalesce(excluded.business_email, public.businesses.business_email),
            map_url = coalesce(excluded.map_url, public.businesses.map_url);

        -- B. Automatically append task to crawler queue
        insert into public.crawl_jobs (business_id, website_url, status)
        values (new.business_id, new.website_url, 'pending');

        -- C. Terminate staging row status to completed
        new.status := 'completed';
        new.processed_at := now();
    end if;
    return new;
end;
$$ language plpgsql;

-- 12. Bind Trigger to Business Load Table
create trigger trigger_process_business_load
before insert on public.business_load
for each row
execute function public.process_business_load_row();
