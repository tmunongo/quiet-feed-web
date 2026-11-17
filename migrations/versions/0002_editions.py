"""Edition size and independent closure."""

from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None


def upgrade():
    source = Path(__file__).resolve().parents[2] / "drizzle/0002_flippant_red_hulk.sql"
    for statement in source.read_text().split("--> statement-breakpoint"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError("Use the pre-upgrade backup to revert edition schema changes.")
