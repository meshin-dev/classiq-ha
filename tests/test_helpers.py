"""Tests for app.helpers.new_task_id function."""

import re

from app.helpers import new_task_id

HEX_RE = re.compile(r"^[0-9a-f]{32}$")


def test_new_task_id_type_and_length():
    tid = new_task_id()
    assert isinstance(tid, str)
    assert len(tid) == 32


def test_new_task_id_is_hex_lowercase():
    tid = new_task_id()
    assert HEX_RE.match(tid), f"Not lowercase hex: {tid}"


def test_new_task_id_uniqueness_sample():
    sample_size = 200
    ids = {new_task_id() for _ in range(sample_size)}
    assert len(ids) == sample_size


def test_new_task_id_multiple_match_hex_pattern():
    for _ in range(25):
        assert HEX_RE.match(new_task_id())
