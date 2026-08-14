"""phase 0 foundation

Revision ID: 0001_phase_0
Revises:
Create Date: 2026-08-15 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_phase_0"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("venue", sa.String(length=240), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("registration_open", sa.Boolean(), nullable=False),
        sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_events_is_active"), "events", ["is_active"], unique=False)
    op.create_index(op.f("ix_events_slug"), "events", ["slug"], unique=False)

    op.create_table(
        "pic_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("role_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_key"),
    )
    op.create_index(op.f("ix_pic_roles_role_key"), "pic_roles", ["role_key"], unique=False)

    op.create_table(
        "faq_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("faq_key", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("generalized_question", sa.Text(), nullable=False),
        sa.Column("answer_source", sa.String(length=80), nullable=False),
        sa.Column("static_answer", sa.Text(), nullable=True),
        sa.Column("auto_reply_allowed", sa.Boolean(), nullable=False),
        sa.Column("requires_lookup", sa.Boolean(), nullable=False),
        sa.Column("requires_human", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_updated_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_faq_entries_category"), "faq_entries", ["category"], unique=False)
    op.create_index(op.f("ix_faq_entries_event_id"), "faq_entries", ["event_id"], unique=False)
    op.create_index(op.f("ix_faq_entries_faq_key"), "faq_entries", ["faq_key"], unique=False)

    op.create_table(
        "event_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("rule_type", sa.String(length=120), nullable=False),
        sa.Column("value", json_type, nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_rules_category"), "event_rules", ["category"], unique=False)
    op.create_index(op.f("ix_event_rules_event_id"), "event_rules", ["event_id"], unique=False)
    op.create_index(op.f("ix_event_rules_rule_type"), "event_rules", ["rule_type"], unique=False)

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("external_user_ref", sa.String(length=240), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("preferred_language", sa.String(length=20), nullable=True),
        sa.Column("state", sa.String(length=60), nullable=False),
        sa.Column("assigned_pic_role", sa.String(length=80), nullable=True),
        sa.Column("human_takeover", sa.Boolean(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_channel"), "conversations", ["channel"], unique=False)
    op.create_index(op.f("ix_conversations_event_id"), "conversations", ["event_id"], unique=False)
    op.create_index(
        op.f("ix_conversations_external_user_ref"),
        "conversations",
        ["external_user_ref"],
        unique=False,
    )
    op.create_index(op.f("ix_conversations_state"), "conversations", ["state"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("external_message_id", sa.String(length=240), nullable=True),
        sa.Column("direction", sa.String(length=40), nullable=False),
        sa.Column("sender_type", sa.String(length=40), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_conversation_id"),
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_messages_external_message_id"),
        "messages",
        ["external_message_id"],
        unique=False,
    )

    op.create_table(
        "handoff_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("assigned_pic_role", sa.String(length=80), nullable=False),
        sa.Column("priority", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_handoff_cases_assigned_pic_role"),
        "handoff_cases",
        ["assigned_pic_role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_handoff_cases_conversation_id"),
        "handoff_cases",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(op.f("ix_handoff_cases_event_id"), "handoff_cases", ["event_id"], unique=False)
    op.create_index(
        op.f("ix_handoff_cases_reason_code"),
        "handoff_cases",
        ["reason_code"],
        unique=False,
    )
    op.create_index(op.f("ix_handoff_cases_status"), "handoff_cases", ["status"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_ref", sa.String(length=160), nullable=True),
        sa.Column("metadata", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_event_type"), "audit_logs", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_event_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_handoff_cases_status"), table_name="handoff_cases")
    op.drop_index(op.f("ix_handoff_cases_reason_code"), table_name="handoff_cases")
    op.drop_index(op.f("ix_handoff_cases_event_id"), table_name="handoff_cases")
    op.drop_index(op.f("ix_handoff_cases_conversation_id"), table_name="handoff_cases")
    op.drop_index(op.f("ix_handoff_cases_assigned_pic_role"), table_name="handoff_cases")
    op.drop_table("handoff_cases")
    op.drop_index(op.f("ix_messages_external_message_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_conversations_state"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_external_user_ref"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_event_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_channel"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(op.f("ix_event_rules_rule_type"), table_name="event_rules")
    op.drop_index(op.f("ix_event_rules_event_id"), table_name="event_rules")
    op.drop_index(op.f("ix_event_rules_category"), table_name="event_rules")
    op.drop_table("event_rules")
    op.drop_index(op.f("ix_faq_entries_faq_key"), table_name="faq_entries")
    op.drop_index(op.f("ix_faq_entries_event_id"), table_name="faq_entries")
    op.drop_index(op.f("ix_faq_entries_category"), table_name="faq_entries")
    op.drop_table("faq_entries")
    op.drop_index(op.f("ix_pic_roles_role_key"), table_name="pic_roles")
    op.drop_table("pic_roles")
    op.drop_index(op.f("ix_events_slug"), table_name="events")
    op.drop_index(op.f("ix_events_is_active"), table_name="events")
    op.drop_table("events")
