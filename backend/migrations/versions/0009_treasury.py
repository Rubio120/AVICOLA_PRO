"""Add auditable cash accounts, sessions, movements and transfers."""

from alembic import op

revision = "0009_treasury"
down_revision = "0008_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    create table cash_accounts (
      id uuid primary key, code varchar(32) not null unique, name varchar(120) not null,
      account_type varchar(16) not null default 'CASH', currency_code varchar(3) not null default 'PYG',
      is_active boolean not null default true
    );
    create table cash_sessions (
      id uuid primary key, cash_account_id uuid not null references cash_accounts(id) on delete restrict,
      opened_by uuid not null references users(id) on delete restrict, opened_at timestamptz not null default now(),
      opening_balance numeric(18,2) not null default 0 check(opening_balance >= 0),
      closed_by uuid references users(id) on delete restrict, closed_at timestamptz,
      expected_balance numeric(18,2), counted_balance numeric(18,2), difference numeric(18,2),
      status varchar(16) not null default 'OPEN' check(status in ('OPEN','CLOSED','REOPENED')),
      version integer not null default 1
    );
    create unique index uq_cash_sessions_open_account on cash_sessions(cash_account_id)
      where status in ('OPEN','REOPENED');
    create table cash_movements (
      id uuid primary key, cash_session_id uuid not null references cash_sessions(id) on delete restrict,
      cash_account_id uuid not null references cash_accounts(id) on delete restrict,
      movement_type varchar(16) not null check(
        movement_type in ('INCOME','EXPENSE','TRANSFER_IN','TRANSFER_OUT','REVERSAL')
      ),
      direction varchar(3) not null check(direction in ('IN','OUT')), amount numeric(18,2) not null check(amount > 0),
      effective_date date not null, payment_method_code varchar(32) references payment_methods(code) on delete restrict,
      source_type varchar(64), source_id uuid, reason varchar(500), status varchar(16) not null default 'CONFIRMED',
      reversal_of_id uuid references cash_movements(id) on delete restrict,
      actor_user_id uuid not null references users(id) on delete restrict,
      idempotency_key varchar(128) unique, created_at timestamptz not null default now()
    );
    create index ix_cash_movements_session_date on cash_movements(cash_session_id, effective_date);
    create table cash_transfers (
      id uuid primary key, source_movement_id uuid not null references cash_movements(id) on delete restrict,
      destination_movement_id uuid not null references cash_movements(id) on delete restrict,
      amount numeric(18,2) not null check(amount > 0), transfer_date date not null, reason varchar(500)
    );
    """)


def downgrade() -> None:
    op.execute("drop table if exists cash_transfers")
    op.execute("drop table if exists cash_movements")
    op.execute("drop table if exists cash_sessions")
    op.execute("drop table if exists cash_accounts")
