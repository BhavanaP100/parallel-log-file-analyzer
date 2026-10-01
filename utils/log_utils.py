"""
log_utils.py
------------------------------------------------------
Small, shared helper functions used by app.py across MULTIPLE pages
(Dashboard, Log Analysis, Performance Comparison).

Putting these here avoids re-writing "read the uploaded file" or
"turn counts into a table" logic separately on every page — every
page that needs them just imports from here.
------------------------------------------------------
"""

import pandas as pd

ALLOWED_EXTENSIONS = ("txt", "log")


def read_uploaded_file(uploaded_file):
    """
    Safely read a Streamlit UploadedFile into a list of log lines.

    This function does NOT raise exceptions to the caller for expected
    problems (empty file, bad encoding, no real content) — instead it
    returns a friendly error message so the UI can show a clean
    message instead of a raw Python traceback.

    Parameters
    ----------
    uploaded_file : st.runtime.uploaded_file_manager.UploadedFile

    Returns
    -------
    (lines, warning, error)
        lines   : list[str] or None  -> the log lines (None if error)
        warning : str or None        -> a non-fatal warning to show the user
        error    : str or None        -> a fatal error message (lines will be None)
    """
    try:
        raw_bytes = uploaded_file.read()
    except Exception:
        return None, None, "Could not read the uploaded file. Please try uploading it again."

    if len(raw_bytes) == 0:
        return None, None, "The uploaded file is empty (0 bytes). Please choose a non-empty .txt or .log file."

    warning = None
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # Fall back to a lossy decode so the app still works, but tell
        # the user their file wasn't clean UTF-8 text.
        text = raw_bytes.decode("utf-8", errors="replace")
        warning = (
            "This file contained some characters that are not valid UTF-8 text. "
            "Those characters were replaced, but line counts should still be reliable."
        )

    lines = text.splitlines()
    non_empty_lines = [line for line in lines if line.strip() != ""]

    if len(non_empty_lines) == 0:
        return None, None, "No readable log lines were found in this file. Please check the file content."

    return lines, warning, None


def counts_to_dataframe(counts):
    """
    Convert a counts dictionary like {"INFO": 10, "WARNING": 2, ...}
    into a pandas DataFrame with columns ["Log Level", "Count"],
    ready to display in a table or chart.
    """
    return pd.DataFrame(counts.items(), columns=["Log Level", "Count"])


def format_seconds(value):
    """Format a time in seconds consistently across the whole app."""
    return f"{value:.4f} sec"
