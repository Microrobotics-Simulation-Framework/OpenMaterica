# SPDX-License-Identifier: Apache-2.0
"""On Python 3.11 and 3.12, every test runs with room on CPython's frame stack (`in_a_large_frame`,
tests/conftest.py), and that room keeps a call repeated across the edge of a frame-stack chunk from mapping a
chunk at each call. From 3.13 on, CPython keeps a spare chunk, and no test runs in the large frame."""

import sys
import threading
import traceback

import pytest

from tests import conftest

if sys.platform == "linux":
    import resource

# A thread's first chunk holds 16 KiB, 2048 slots; `descend` takes about 20 a level, so the scan passes its
# edge well before the last depth.
DEPTHS = 250
CALLS = 2_000


def test_the_large_frame_is_applied_exactly_where_chunks_are_unmapped(request: pytest.FixtureRequest) -> None:
    # The version is read here, not from the conftest's constant, so that a gate forced either way fails.
    unmapped = sys.version_info < (3, 13)
    callers = [frame.f_code for frame, _ in traceback.walk_stack(None)]
    assert (conftest.in_a_large_frame.__code__ in callers) is unmapped
    # Where it is not applied, `runtest` is the item's own method, not a closure set on the item.
    item: pytest.Item = request.node  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert ("runtest" in vars(item)) is unmapped


def most_faults_at_one_depth(in_the_large_frame: bool) -> int:
    """The most minor page faults that `CALLS` calls of `leaf` cost at any depth from 0 to `DEPTHS` of
    `descend` in a new thread, whose frame stack starts empty: run inside the large frame, or not."""
    # Its frame is larger than `descend`'s, so at the last depth whose `descend` fits in a chunk, `leaf` does
    # not: each call opens the next chunk.
    leaf = conftest.large_frame_function(64)
    faults: list[int] = []

    def descend(depth: int) -> None:
        if depth:
            descend(depth - 1)
            return
        before = resource.getrusage(resource.RUSAGE_THREAD).ru_minflt
        for _ in range(CALLS):
            leaf(int)
        faults.append(resource.getrusage(resource.RUSAGE_THREAD).ru_minflt - before)

    def scan() -> None:
        for depth in range(DEPTHS):
            descend(depth)

    if in_the_large_frame:
        thread = threading.Thread(target=conftest.in_a_large_frame, args=(scan,))
    else:
        thread = threading.Thread(target=scan)
    thread.start()
    thread.join()
    assert len(faults) == DEPTHS
    return max(faults)


@pytest.mark.skipif(sys.platform != "linux", reason="a thread's own page faults are counted on Linux alone")
def test_inside_the_large_frame_no_depth_maps_a_chunk_at_each_call() -> None:
    assert most_faults_at_one_depth(in_the_large_frame=True) < CALLS // 20


@pytest.mark.skipif(sys.platform != "linux", reason="a thread's own page faults are counted on Linux alone")
def test_outside_it_one_depth_maps_a_chunk_at_each_call_where_chunks_are_unmapped() -> None:
    # The control: without the large frame, the scan meets the edge, and the count sees it on 3.11 and 3.12;
    # from 3.13 on, the spare chunk leaves no depth that maps at each call, so the frame is not applied.
    faults = most_faults_at_one_depth(in_the_large_frame=False)
    if sys.version_info < (3, 13):
        assert faults >= CALLS
    else:
        assert faults < CALLS // 20
