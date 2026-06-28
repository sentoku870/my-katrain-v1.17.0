"""Safe file write helper with directory creation and error handling."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def safe_write_file(
    path: str,
    content: str,
    file_kind: str,
    sgf_id: str,
    log_cb: Callable[[str], None] | None = None,
) -> Any | None:
    """Safely write content to file with directory creation and error handling.

    Args:
        path: Target file path
        content: Content to write
        file_kind: Type of file ("karte", "summary", "analyzed_sgf")
        sgf_id: Identifier for error reporting (SGF filename or player name)
        log_cb: Optional logging callback

    Returns:
        None on success, WriteError on failure

    Note:
        Returns WriteError from models module. Import is deferred to avoid
        circular imports at module load time.
    """
    from katrain.core.batch.models import WriteError

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    try:
        # Ensure parent directory exists (pathlib handles Windows paths correctly)
        parent = Path(path).parent
        parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return None  # Success

    except (OSError, PermissionError, UnicodeEncodeError) as e:
        error = WriteError(
            file_kind=file_kind,
            sgf_id=sgf_id,
            target_path=path,
            exception_type=type(e).__name__,
            message=str(e),
        )
        log(f"  ERROR writing {file_kind}: {e}")
        return error

    except Exception as e:  # noqa: BLE001
        # Catch-all for unexpected errors
        error = WriteError(
            file_kind=file_kind,
            sgf_id=sgf_id,
            target_path=path,
            exception_type=type(e).__name__,
            message=str(e),
        )
        log(f"  ERROR writing {file_kind} (unexpected): {e}")
        return error


# Alias for backward compatibility with private name
_safe_write_file = safe_write_file
