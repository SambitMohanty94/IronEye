-- IronEye Phase 4 - Supabase PostgreSQL schema

create extension if not exists "pgcrypto";

create table if not exists cameras (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    source text not null,
    location text,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists workers (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    employee_code text unique,
    phone text,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists incidents (
    id uuid primary key default gen_random_uuid(),
    camera_id uuid references cameras(id) on delete set null,
    worker_id uuid references workers(id) on delete set null,
    incident_type text not null,
    risk_level text not null,
    confidence numeric,
    foot_x integer,
    foot_y integer,
    evidence_path text,
    detected_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists alerts_log (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid references incidents(id) on delete cascade,
    channel text not null,
    destination text,
    status text not null,
    message text,
    sent_at timestamptz not null default now()
);

create index if not exists idx_incidents_detected_at
    on incidents(detected_at desc);

create index if not exists idx_incidents_risk_level
    on incidents(risk_level);

create index if not exists idx_alerts_incident_id
    on alerts_log(incident_id);

-- Prepare incidents for Supabase Realtime.
alter table incidents replica identity full;