""" "Setup and configure logger."""

from uuid import uuid4


def new_task_id() -> str:
    """Generate a new unique task ID as a hex string."""
    return uuid4().hex
