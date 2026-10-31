create table if not exists public.connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  connection_string text not null,
  db_type text not null,
  created_at timestamptz default now(),
  unique(user_id)
);
alter table public.connections enable row level security;
create policy "Users can manage their own connection"
on public.connections for all to authenticated
using (auth.uid() = user_id) with check (auth.uid() = user_id);
