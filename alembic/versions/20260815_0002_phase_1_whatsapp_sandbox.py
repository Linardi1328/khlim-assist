"""phase 1 whatsapp sandbox

Revision ID: 0002_phase_1
Revises: 0001_phase_0
Create Date: 2026-08-15 00:00:01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_phase_1"
down_revision: str | None = "0001_phase_0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("delivery_status", sa.String(length=40), nullable=True))
    op.add_column(
        "messages",
        sa.Column("delivery_status_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("provider_error_code", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("provider_error_message", sa.String(length=500), nullable=True),
    )

    op.drop_index(op.f("ix_messages_external_message_id"), table_name="messages")
    op.create_index(
        "uq_messages_external_message_id_non_null",
        "messages",
        ["external_message_id"],
        unique=True,
        postgresql_where=sa.text("external_message_id IS NOT NULL"),
        sqlite_where=sa.text("external_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_messages_external_message_id_non_null", table_name="messages")
    op.create_index(
        op.f("ix_messages_external_message_id"),
        "messages",
        ["external_message_id"],
        unique=False,
    )
    op.drop_column("messages", "provider_error_message")
    op.drop_column("messages", "provider_error_code")
    op.drop_column("messages", "delivery_status_updated_at")
    op.drop_column("messages", "delivery_status")
