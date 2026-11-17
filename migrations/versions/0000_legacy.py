"""Original Quiet Feed schema, kept byte-for-byte in drizzle/."""

from pathlib import Path

from alembic import op

revision = "0000"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    source = Path(__file__).resolve().parents[2] / "drizzle/0000_uneven_hobgoblin.sql"
    for statement in source.read_text().split("--> statement-breakpoint"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError("Restore a backup to remove the original application schema.")
