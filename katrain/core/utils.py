import heapq
import math
from pathlib import Path
import random
import struct
import sys
from typing import Any, Dict, List, Sequence, Tuple, TypeVar

import importlib.resources as pkg_resources


T = TypeVar("T")


def var_to_grid(array_var: List[T], size: Tuple[int, int]) -> List[List[T]]:
    """convert ownership/policy to grid format such that grid[y][x] is for move with coords x,y"""
    ix = 0
    grid: List[List[T]] = [[]] * size[1]
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
        eval_thresholds: Thresholds for each class. None entries are treated as infinity.

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


def check_thread(tb: bool = False) -> None:  # for checking if draws occur in correct thread
    import threading

    print("build in ", threading.current_thread().ident)
    if tb:
        import traceback

        traceback.print_stack()


PATHS: Dict[str, str] = {}


def find_package_resource(path: str, silent_errors: bool = False) -> str:
    global PATHS
    if path.startswith("katrain"):
        if not PATHS.get("PACKAGE"):
            try:
                files_ref = pkg_resources.files("katrain")
                # Handle both Traversable and Path types
                if hasattr(files_ref, "absolute"):
                    PATHS["PACKAGE"] = str(files_ref.absolute())  # type: ignore[union-attr]
                else:
                    PATHS["PACKAGE"] = str(files_ref)
            except (ModuleNotFoundError, FileNotFoundError, ValueError) as e:
                print(f"Package path not found, installation possibly broken. Error: {e}", file=sys.stderr)
                return f"FILENOTFOUND/{path}"
        return str(Path(PATHS["PACKAGE"]) / path.replace("katrain\\", "katrain/").replace("katrain/", ""))
    else:
        return str(Path(path).expanduser().absolute())


def pack_floats(float_list: List[float] | None) -> bytes:
    if float_list is None:
        return b""
    return struct.pack(f"{len(float_list)}e", *float_list)


def unpack_floats(data: bytes, num: int) -> Tuple[float, ...] | None:
    if not data:
        return None
    return struct.unpack(f"{num}e", data)


def format_visits(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 1e5:
        return f"{n/1000:.1f}k"
    if n < 1e6:
        return f"{n/1000:.0f}k"
    return f"{n/1e6:.0f}M"


def json_truncate_arrays(data: Any, lim: int = 20) -> Any:
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return [json_truncate_arrays(d) for d in data]
        if len(data) > lim:
            data = [f"{len(data)} x {type(data[0]).__name__}"]
        return data
    elif isinstance(data, dict):
        return {k: json_truncate_arrays(v) for k, v in data.items()}
    else:
        return data


TupleT = TypeVar("TupleT", bound=Tuple[Any, ...])


def weighted_selection_without_replacement(items: List[TupleT], pick_n: int) -> List[TupleT]:
    """For a list of tuples where the second element (index 1) is a weight, returns random items with those weights, without replacement."""
    # Type ignore: we trust that item[1] exists and is numeric based on the docstring contract
    elt = [(math.log(random.random()) / (item[1] + 1e-18), item) for item in items]  # type: ignore[index,operator]
    return [e[1] for e in heapq.nlargest(pick_n, elt)]  # NB fine if too small
