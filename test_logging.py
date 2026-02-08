
import sys
import os
from unittest.mock import MagicMock
# Ensure katrain is in path
sys.path.insert(0, r"d:\github\katrain-1.17.0")

from katrain.core.reports.karte.builder import build_karte_report
from katrain.core.analysis.models import EvalSnapshot

def test_logging():
    print("Testing debug logging...")
    
    # Mock game enough to reach _build_karte_report_impl
    game = MagicMock()
    game.game_id = "logging_test_game"
    game.sgf_filename = "test.sgf"
    
    # Pre-build snapshot to pass is_single_engine_snapshot check
    snapshot = EvalSnapshot(moves=[])
    
    # We want _build_karte_report_impl to fail.
    # It calls build_karte_json(game, ...).
    # build_karte_json calls game.root.get_property(...).
    # So if we make game.root raising an exception on access, it should fail.
    type(game).root = PropertyMock(side_effect=RuntimeError("Intentional Crash"))
    
    try:
        build_karte_report(game, snapshot=snapshot, raise_on_error=True)
    except RuntimeError:
        print("Caught expected RuntimeError.")
    except Exception as e:
        print(f"Caught unexpected exception: {e}")

    # Check log file
    log_path = r"d:\github\katrain-1.17.0\debug_error.log"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
            if "Intentional Crash" in content and "logging_test_game" in content:
                print("SUCCESS: Log file contains expected error.")
            else:
                print("FAILURE: Log file exists but content mismatch.")
                print("Content:", content)
    else:
        print("FAILURE: Log file not created.")

from unittest.mock import PropertyMock

if __name__ == "__main__":
    test_logging()
