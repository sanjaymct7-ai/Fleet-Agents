-- ============================================================
-- PHASE 1 SCHEMA — your first SQL lesson.
-- Paste this whole file into Supabase's SQL Editor and press Run.
--
-- Reading guide:
--   * Anything after "--" on a line is a comment (ignored by the database).
--   * CREATE TABLE defines a table: its name, then a list of columns.
--   * Each column line is:  column_name  TYPE  constraints
--   * Common types you'll see here:
--       bigint       whole numbers (we use it for IDs)
--       text         strings of any length
--       numeric      decimal numbers (money, coordinates, weights)
--       timestamptz  a timestamp WITH timezone (always prefer this)
--   * PRIMARY KEY  = the unique identifier of each row.
--   * GENERATED ... AS IDENTITY = the database auto-numbers rows 1,2,3...
--   * NOT NULL     = this column must always have a value.
--   * DEFAULT      = value used when you don't supply one.
--   * REFERENCES   = a "foreign key": this value must exist in another
--                    table. This is how tables link together.
--   * CHECK        = a rule every row must satisfy; the DB rejects
--                    anything else. Our first taste of "the database
--                    enforces correctness, not just the code".
-- ============================================================


-- ------------------------------------------------------------
-- 1) DRIVERS — the synthetic driver roster.
--    Written by: our seed script (later, the Dispatch agent will
--    update ONLY the status/assignment fields — least privilege).
-- ------------------------------------------------------------
create table drivers (
  id           bigint generated always as identity primary key,
  name         text not null,
  home_lat     numeric not null,          -- home-base latitude
  home_lng     numeric not null,          -- home-base longitude
  shift_start  text not null default '09:00',  -- kept as text for simplicity in Phase 1
  shift_end    text not null default '18:00',
  max_hours    numeric not null default 8,     -- hours-of-service limit per day
  status       text not null default 'off_shift'
               check (status in ('off_shift','available','on_route','unavailable'))
);

-- ------------------------------------------------------------
-- 2) ORDERS — one row per shipment request.
--    Written by: Order Intake agent ONLY (one door in).
-- ------------------------------------------------------------
create table orders (
  id            bigint generated always as identity primary key,
  created_at    timestamptz not null default now(),  -- auto-stamped
  customer_name text not null,
  customer_tier text not null default 'standard'
                check (customer_tier in ('standard','premium','enterprise')),
  pickup_lat    numeric not null,
  pickup_lng    numeric not null,
  drop_lat      numeric not null,
  drop_lng      numeric not null,
  window_start  timestamptz not null,   -- earliest allowed delivery
  window_end    timestamptz not null,   -- latest allowed delivery
  weight_kg     numeric not null check (weight_kg > 0),
  priority      int not null default 3 check (priority between 1 and 5), -- 1 = highest
  status        text not null default 'new'
                check (status in ('new','planned','assigned','in_transit',
                                  'delivered','failed','cancelled'))
);

-- ------------------------------------------------------------
-- 3) ROUTES — one row per planned vehicle route for the day.
--    Written by: Route Planning agent (creates them),
--    Dispatch agent (fills in driver_id).
-- ------------------------------------------------------------
create table routes (
  id                  bigint generated always as identity primary key,
  created_at          timestamptz not null default now(),
  driver_id           bigint references drivers(id),  -- NULL until Dispatch assigns
  vehicle_capacity_kg numeric not null default 500,
  total_distance_km   numeric,                        -- filled by the solver
  status              text not null default 'planned'
                      check (status in ('planned','assigned','active',
                                        'completed','aborted'))
);

-- ------------------------------------------------------------
-- 4) ROUTE_STOPS — the ordered stops inside a route.
--    A route is just a sequence of stops; each stop belongs to an
--    order. This is a classic "join" table linking routes<->orders.
-- ------------------------------------------------------------
create table route_stops (
  id              bigint generated always as identity primary key,
  route_id        bigint not null references routes(id),
  order_id        bigint not null references orders(id),
  seq             int not null,            -- 1st stop, 2nd stop, ...
  stop_type       text not null check (stop_type in ('pickup','dropoff')),
  planned_arrival timestamptz,             -- what the solver promised
  actual_arrival  timestamptz,             -- what the simulation delivers
  status          text not null default 'pending'
                  check (status in ('pending','arrived','done','failed','skipped'))
);

-- ------------------------------------------------------------
-- Seed one driver so the app's Setup Check can prove reads work.
-- INSERT = add a row. Columns listed first, values second, in order.
-- (Coordinates are placeholders — Phase 2's generator will use a
--  real city of your choice.)
-- ------------------------------------------------------------
insert into drivers (name, home_lat, home_lng, status)
values ('Test Driver 1', 13.0000, 80.2000, 'available');

-- ------------------------------------------------------------
-- Try these yourself in the SQL Editor afterwards (one at a time):
--
--   select * from drivers;                       -- read every row
--   select name, status from drivers;            -- only two columns
--   select count(*) from orders;                 -- should be 0 for now
--
-- Congratulations — you've created a relational schema with
-- foreign keys and constraints. That's real SQL.
-- ------------------------------------------------------------
