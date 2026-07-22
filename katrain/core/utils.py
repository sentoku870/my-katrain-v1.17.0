import heapq
import math
import random
import struct
from collections.abc import Sequence
from typing import Any, TypeVar

T = TypeVar("T")


def var_to_grid(array_var: list[T], size: tuple[int, int]) -> list[list[T]]:
    """convert ownership/policy to grid format such that grid[y][x] is for move with coords x,y"""
    ix = 0
    grid: list[list[T]] = [[]] * size[1]
    for y in range(size[1] - 1, -1, -1):
        grid[y] = array_var[ix : ix + size[0]]
        ix += size[0]
    return grid


def evaluation_class(points_lost: float, eval_thresholds: Sequence[float | None]) -> int:
    """
    Evaluate the class (bucket) for a given loss value.

    Thresholds are assumed to be in DESCENDING order (e.g. [12, 6, 3, 1.5, 0.5, 0]).
    Returns index 0 for worst (largest loss) and len-1 for best (smallest loss).

    Args:
        points_lost: The loss value to evaluate (positive=bad, negative=good/gain)
        eval_thresholds: Sequence of threshold values.

    Returns:
        The class index (0-based), in range [0, len(eval_thresholds)-1]
    """
    i = 0
    while i < len(eval_thresholds) - 1:
        threshold = eval_thresholds[i]
        if threshold is None:
            # None = infinity threshold, skip to next
            i += 1
            continue
        if points_lost >= threshold:
            break
        i += 1
    return i


def pack_floats(float_list: list[float] | None) -> bytes:
    if float_list is None:
        return b""
    return struct.pack(f"{len(float_list)}e", *float_list)


def unpack_floats(data: bytes, num: int) -> tuple[float, ...] | None:
    if not data:
        return None
    return struct.unpack(f"{num}e", data)


def format_visits(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 1e5:
        return f"{n / 1000:.1f}k"
    if n < 1e6:
        return f"{n / 1000:.0f}k"
    return f"{n / 1e6:.0f}M"


def json_truncate_arrays(data: Any, lim: int = 20) -> Any:
    if isinstance(data, list):
        # Phase LV1-13: check length *before* recursing so that dict-list
        # entries (which previously recursed into every element) are also
        # collapsed when they exceed ``lim``.
        if len(data) > lim:
            head_type = type(data[0]).__name__ if data else "item"
            return [f"{len(data)} x {head_type}"]
        if data and isinstance(data[0], dict):
            return [json_truncate_arrays(d) for d in data]
        return data
    elif isinstance(data, dict):
        return {k: json_truncate_arrays(v) for k, v in data.items()}
    else:
        return data


TupleT = TypeVar("TupleT", bound=tuple[Any, ...])


def weighted_selection_without_replacement(items: list[TupleT], pick_n: int) -> list[TupleT]:
    """For a list of tuples where the second element (index 1) is a weight, returns random items with those weights, without replacement."""
    # Contract: each ``item`` is a 2-tuple ``(payload, weight)`` per the
    # docstring. ``TupleT = TypeVar("TupleT", bound=tuple[Any, ...])`` so
    # ``item[1]`` is typed ``Any`` and the math on it is safe.
    elt = [(math.log(random.random()) / (item[1] + 1e-18), item) for item in items]
    return [e[1] for e in heapq.nlargest(pick_n, elt)]  # NB fine if too small
