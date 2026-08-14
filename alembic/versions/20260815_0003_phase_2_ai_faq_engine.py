"""phase 2 ai faq engine

Revision ID: 0003_phase_2
Revises: 0002_phase_1
Create Date: 2026-08-15 00:00:02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_phase_2"
down_revision: str | None = "0002_phase_1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "ai_processing_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("primary_language", sa.String(length=20), nullable=True),
        sa.Column("language_mode", sa.String(length=20), nullable=True),
        sa.Column("interpreted_intents", json_type, nullable=False),
        sa.Column("decision_level", sa.String(length=20), nullable=True),
        sa.Column("decision_reason", sa.String(length=120), nullable=True),
        sa.Column("knowledge_found", sa.Boolean(), nullable=False),
        sa.Column("knowledge_source", sa.String(length=240), nullable=True),
        sa.Column("requires_clarification", sa.Boolean(), nullable=False),
        sa.Column("recommended_pic_role", sa.String(length=80), nullable=True),
        sa.Column("draft_response", sa.Text(), nullable=True),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("provider_request_id", sa.String(length=160), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_processing_runs_conversation_id"),
        "ai_processing_runs",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_processing_runs_event_id"),
        "ai_processing_runs",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_processing_runs_message_id"),
        "ai_processing_runs",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_processing_runs_processing_status"),
        "ai_processing_runs",
        ["processing_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_processing_runs_processing_status"), table_name="ai_processing_runs")
    op.drop_index(op.f("ix_ai_processing_runs_message_id"), table_name="ai_processing_runs")
    op.drop_index(op.f("ix_ai_processing_runs_event_id"), table_name="ai_processing_runs")
    op.drop_index(op.f("ix_ai_processing_runs_conversation_id"), table_name="ai_processing_runs")
    op.drop_table("ai_processing_runs")
