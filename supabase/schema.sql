-- ── Jobs table ──────────────────────────────────────────────────────────────
create table if not exists public.jobs (
  id               text primary key,
  status           text not null default 'queued',
  progress         integer not null default 0,
  filename         text,
  file_path        text,
  log              text,
  result_pptx      text,
  result_svg       text,
  result_png       text,
  result_previews  text,
  diagram_count    integer default 0,
  slide_count      integer default 0,
  created_at       timestamptz default now(),
  updated_at       timestamptz default now()
);

-- Auto-update updated_at
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

drop trigger if exists trg_jobs_updated_at on public.jobs;
create trigger trg_jobs_updated_at
  before update on public.jobs
  for each row execute function public.set_updated_at();

-- Row-Level Security: anyone can insert/read their own job by ID
alter table public.jobs enable row level security;

drop policy if exists "insert own job"  on public.jobs;
drop policy if exists "read own job"    on public.jobs;
drop policy if exists "service update"  on public.jobs;

create policy "insert own job" on public.jobs
  for insert with check (true);

create policy "read own job" on public.jobs
  for select using (true);

create policy "service update" on public.jobs
  for update using (true);

-- ── Storage buckets ──────────────────────────────────────────────────────────
insert into storage.buckets (id, name, public)
  values ('pptx-inputs',  'pptx-inputs',  false)
  on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
  values ('pptx-outputs', 'pptx-outputs', true)
  on conflict (id) do nothing;

-- Allow anonymous uploads to inputs bucket
drop policy if exists "anon upload pptx"   on storage.objects;
drop policy if exists "public read outputs" on storage.objects;

create policy "anon upload pptx" on storage.objects
  for insert with check (bucket_id = 'pptx-inputs');

create policy "public read outputs" on storage.objects
  for select using (bucket_id = 'pptx-outputs');
