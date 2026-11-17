"""Gemini dispatch settings and summaries."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = "0000"
branch_labels = depends_on = None


def upgrade():
    source = Path(__file__).resolve().parents[2] / "drizzle/0001_fixed_stephen_strange.sql"
    for statement in source.read_text().split("--> statement-breakpoint"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError("Use the pre-upgrade backup to revert dispatch schema changes.")
