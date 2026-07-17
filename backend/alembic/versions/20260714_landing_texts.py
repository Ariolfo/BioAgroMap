"""add project_landing_texts

Revision ID: 20260714_landing_texts
Revises:
Create Date: 2026-07-14

"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_landing_texts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_landing_texts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("section_key", sa.String(length=120), nullable=False),
        sa.Column("draft_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("project_id", "section_key", name="uq_project_landing_texts_project_section"),
    )
    op.create_index("ix_project_landing_texts_project_id", "project_landing_texts", ["project_id"])
    op.create_index("ix_project_landing_texts_section_key", "project_landing_texts", ["section_key"])
    op.create_index(
        "ix_project_landing_texts_project_section",
        "project_landing_texts",
        ["project_id", "section_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_landing_texts_project_section", table_name="project_landing_texts")
    op.drop_index("ix_project_landing_texts_section_key", table_name="project_landing_texts")
    op.drop_index("ix_project_landing_texts_project_id", table_name="project_landing_texts")
    op.drop_table("project_landing_texts")
