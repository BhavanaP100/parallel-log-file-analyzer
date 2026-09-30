"""
sequential_analyzer.py
------------------------------------------------------
This file contains the SEQUENTIAL (single-threaded) version
of the log analysis logic.

"Sequential" means: one line is processed after another, in a
single thread, from top to bottom. There is no parallelism here.
This is our BASELINE — we will compare the multithreaded version
against this to see if threading actually helps.
------------------------------------------------------
"""

import time


def analyze_line(line):
    """
    Look at a single log line and decide what type it is.

    A typical log line looks like:
        2024-05-01 10:23:45 INFO User logged in successfully

    We simply check which keyword (INFO / WARNING / ERROR) is
    present in the line and return that as the "category".

    Returns one of: "INFO", "WARNING", "ERROR", or "OTHER"
    """
    line_upper = line.upper()
    if "ERROR" in line_upper:
        return "ERROR"
    elif "WARNING" in line_upper:
        return "WARNING"
    elif "INFO" in line_upper:
        return "INFO"
    else:
        return "OTHER"


def analyze_log_sequential(lines):
    """
    Analyze ALL log lines one by one, in a single thread.

    Parameters
    ----------
    lines : list of str
        Every line of the log file.

    Returns
    -------
    dict with:
        - counts: dictionary of {"INFO": x, "WARNING": y, "ERROR": z, "OTHER": w}
        - total_lines: total number of lines processed
        - time_taken: how many seconds this took (measured using time.perf_counter)
    """
    start_time = time.perf_counter()   # start the stopwatch

    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "OTHER": 0}

    # This is the core sequential loop: ONE line at a time, ONE thread.
    for line in lines:
        line = line.strip()
        if line == "":
            continue  # skip empty lines
        category = analyze_line(line)
        counts[category] += 1

    end_time = time.perf_counter()     # stop the stopwatch
    time_taken = end_time - start_time

    return {
        "counts": counts,
        "total_lines": sum(counts.values()),
        "time_taken": time_taken,
    }
