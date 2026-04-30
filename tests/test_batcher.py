"""Tests for batcher.group_batches — pure function, no I/O."""

from conftest import make_catalog, make_fn

from src.graph.nodes.batcher import group_batches


def test_empty_returns_empty() -> None:
    assert group_batches([], {}, batch_size=5, max_lines=500) == []


def test_single_function_one_batch() -> None:
    ids, catalog = make_catalog(make_fn("f", start_line=1, end_line=10))
    batches = group_batches(ids, catalog, batch_size=5, max_lines=500)
    assert batches == [ids]


def test_batch_size_limit_splits() -> None:
    fns = [make_fn(f"f{i}", start_line=i * 10, end_line=i * 10 + 5) for i in range(4)]
    ids, catalog = make_catalog(*fns)
    batches = group_batches(ids, catalog, batch_size=2, max_lines=500)
    assert len(batches) == 2
    assert all(len(b) <= 2 for b in batches)


def test_max_lines_splits_batch() -> None:
    # Two functions, each 60 lines — max_lines=80 forces split
    f1 = make_fn("f1", start_line=1, end_line=61)
    f2 = make_fn("f2", start_line=62, end_line=122)
    ids, catalog = make_catalog(f1, f2)
    batches = group_batches(ids, catalog, batch_size=10, max_lines=80)
    assert len(batches) == 2


def test_same_file_functions_grouped_together() -> None:
    a1 = make_fn("a1", file_path="src/a.py", start_line=1, end_line=5)
    a2 = make_fn("a2", file_path="src/a.py", start_line=6, end_line=10)
    b1 = make_fn("b1", file_path="src/b.py", start_line=1, end_line=5)
    ids, catalog = make_catalog(a1, a2, b1)
    batches = group_batches(ids, catalog, batch_size=10, max_lines=500)
    # b1 must not share a batch with a-file functions
    flat_files = [{str(catalog[fid].file_path) for fid in batch} for batch in batches]
    for files in flat_files:
        assert len(files) == 1


def test_oversized_single_fn_gets_own_batch() -> None:
    # One function larger than max_lines; must still appear alone (not discarded)
    big = make_fn("big", start_line=1, end_line=600)
    small = make_fn("small", start_line=601, end_line=610)
    ids, catalog = make_catalog(big, small)
    batches = group_batches(ids, catalog, batch_size=10, max_lines=500)
    # big lands in its own batch, small in another
    assert any(len(b) == 1 and catalog[b[0]].name == "big" for b in batches)
