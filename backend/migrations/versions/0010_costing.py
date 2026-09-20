"""Add auditable costing runs, allocations and profitability snapshots."""

from alembic import op

revision = "0010_costing"
down_revision = "0009_treasury"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    create table cost_centers (
      id uuid primary key, code varchar(32) not null unique, name varchar(120) not null,
      is_active boolean not null default true
    );
    create table cost_events (
      id uuid primary key, event_type varchar(32) not null, source_type varchar(64) not null,
      source_id uuid not null, cost_center_id uuid, effective_date date not null,
      amount numeric(18,2) not null check(amount >= 0), currency_code varchar(3) not null default 'PYG',
      status varchar(16) not null default 'CONFIRMED' check(status in ('DRAFT','CONFIRMED','REVERSED')),
      idempotency_key varchar(128) unique, reversal_of_id uuid, actor_user_id uuid,
      metadata jsonb not null default '{}'::jsonb check(jsonb_typeof(metadata) = 'object'),
      created_at timestamptz not null default now()
    );
    create index ix_cost_events_status_date on cost_events(status, effective_date);
    create table cost_allocations (
      id uuid primary key, cost_event_id uuid not null references cost_events(id) on delete restrict,
      target_type varchar(32) not null, target_id uuid not null, weight numeric(18,4) not null,
      amount numeric(18,2) not null check(amount >= 0),
      constraint uq_cost_allocations_target unique(cost_event_id, target_type, target_id),
      constraint cost_allocations_values check(weight > 0)
    );
    create table cost_runs (
      id uuid primary key, run_date date not null, version integer not null check(version > 0),
      status varchar(16) not null default 'DRAFT' check(status in ('DRAFT','CALCULATING','CLOSED')),
      created_by uuid, closed_at timestamptz,
      constraint uq_cost_runs_date_version unique(run_date, version)
    );
    create table cost_run_snapshots (
      id uuid primary key, cost_run_id uuid not null references cost_runs(id) on delete restrict,
      target_type varchar(32) not null, target_id uuid not null,
      total_cost numeric(18,2) not null check(total_cost >= 0),
      quantity numeric(18,4) not null default 0 check(quantity >= 0), cost_per_unit numeric(18,2),
      constraint uq_cost_run_snapshot_target unique(cost_run_id, target_type, target_id)
    );
    create table profitability_snapshots (
      id uuid primary key, cost_run_id uuid not null references cost_runs(id) on delete restrict,
      source_id uuid not null, revenue numeric(18,2) not null check(revenue >= 0),
      cost numeric(18,2) not null check(cost >= 0), margin numeric(18,2) not null,
      margin_rate numeric(9,6), notes text,
      constraint uq_profitability_run_source unique(cost_run_id, source_id)
    );
    create trigger trg_cost_events_append_only
      before update or delete on cost_events for each row execute function reject_append_only_mutation();
    create trigger trg_cost_allocations_append_only
      before update or delete on cost_allocations for each row execute function reject_append_only_mutation();
    create trigger trg_cost_run_snapshots_append_only
      before update or delete on cost_run_snapshots for each row execute function reject_append_only_mutation();
    create trigger trg_profitability_snapshots_append_only
      before update or delete on profitability_snapshots for each row execute function reject_append_only_mutation();
    create function reject_closed_cost_run_mutation() returns trigger language plpgsql as $$
    begin
      if (tg_op = 'DELETE') or (old.status = 'CLOSED') then
        raise exception 'closed cost runs are append-only';
      end if;
      return new;
    end $$;
    create trigger trg_cost_runs_closed_immutable
      before update or delete on cost_runs for each row execute function reject_closed_cost_run_mutation();
    """)


def downgrade() -> None:
    op.execute("drop trigger if exists trg_cost_runs_closed_immutable on cost_runs")
    op.execute("drop function if exists reject_closed_cost_run_mutation()")
    op.execute("drop trigger if exists trg_profitability_snapshots_append_only on profitability_snapshots")
    op.execute("drop trigger if exists trg_cost_run_snapshots_append_only on cost_run_snapshots")
    op.execute("drop trigger if exists trg_cost_allocations_append_only on cost_allocations")
    op.execute("drop trigger if exists trg_cost_events_append_only on cost_events")
    op.execute("drop table if exists profitability_snapshots")
    op.execute("drop table if exists cost_run_snapshots")
    op.execute("drop table if exists cost_runs")
    op.execute("drop table if exists cost_allocations")
    op.execute("drop table if exists cost_events")
    op.execute("drop table if exists cost_centers")
