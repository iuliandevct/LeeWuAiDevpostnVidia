begin;

create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique
    check (slug ~ '^[a-z0-9]+(?:_[a-z0-9]+)*$'),
  name text not null,
  status text not null default 'active'
    check (status in ('active', 'inactive', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  slug text not null
    check (slug ~ '^[a-z0-9]+(?:_[a-z0-9]+)*$'),
  name text not null,
  isolation_mode text not null default 'shared'
    check (isolation_mode in ('shared', 'dedicated')),
  status text not null default 'active'
    check (status in ('planned', 'active', 'paused', 'archived')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, slug)
);

create table if not exists public.supabase_instances (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique
    check (slug ~ '^[a-z0-9]+(?:_[a-z0-9]+)*$'),
  name text not null,
  deployment_type text not null
    check (deployment_type in ('local', 'cloud', 'self_hosted')),
  purpose text not null default 'shared'
    check (purpose in ('shared', 'dedicated')),
  project_ref text,
  api_url text,
  status text not null default 'planned'
    check (status in ('planned', 'active', 'degraded', 'offline', 'archived')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.project_instances (
  project_id uuid not null references public.projects(id) on delete cascade,
  instance_id uuid not null references public.supabase_instances(id) on delete cascade,
  is_primary boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (project_id, instance_id)
);

create table if not exists public.company_members (
  company_id uuid not null references public.companies(id) on delete cascade,
  user_id uuid not null,
  role text not null default 'member'
    check (role in ('owner', 'admin', 'member', 'viewer', 'client')),
  created_at timestamptz not null default now(),
  primary key (company_id, user_id)
);

create index if not exists projects_company_id_idx
  on public.projects(company_id);
create index if not exists project_instances_instance_id_idx
  on public.project_instances(instance_id);
create index if not exists company_members_user_id_idx
  on public.company_members(user_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists companies_set_updated_at on public.companies;
create trigger companies_set_updated_at
before update on public.companies
for each row execute function public.set_updated_at();

drop trigger if exists projects_set_updated_at on public.projects;
create trigger projects_set_updated_at
before update on public.projects
for each row execute function public.set_updated_at();

drop trigger if exists supabase_instances_set_updated_at on public.supabase_instances;
create trigger supabase_instances_set_updated_at
before update on public.supabase_instances
for each row execute function public.set_updated_at();

insert into public.companies (slug, name)
values
  ('biteight', 'biteight'),
  ('bitsense', 'bitsense'),
  ('atdeco', 'atdeco'),
  ('vice_engineering', 'vice_engineering'),
  ('lp_mar', 'lp_mar'),
  ('gabinfy', 'gabinfy'),
  ('accounting', 'accounting'),
  ('lawyers', 'lawyers')
on conflict (slug) do update
set name = excluded.name,
    status = 'active';

insert into public.supabase_instances (
  slug,
  name,
  deployment_type,
  purpose,
  status,
  api_url
)
values (
  'local_shared',
  'Local shared Supabase',
  'local',
  'shared',
  'active',
  'http://localhost:54321'
)
on conflict (slug) do update
set status = excluded.status,
    api_url = excluded.api_url;

comment on table public.companies is
  'Tenant/company registry. Business data tables should reference company_id.';
comment on table public.projects is
  'Commercial projects; isolation_mode selects shared tables or a dedicated Supabase instance.';
comment on table public.supabase_instances is
  'Registry only. Never store service-role keys or database passwords here.';
comment on table public.company_members is
  'Membership foundation. RLS will be enabled after local Supabase Auth is configured.';

commit;
