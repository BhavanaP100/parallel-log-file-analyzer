"""
parallel_analyzer.py
------------------------------------------------------
This file contains the PARALLEL (multithreaded) version of the
log analysis logic.

CONCEPT USED: DATA PARALLELISM
    - We take ONE large list of log lines (the "data").
    - We SPLIT it into smaller equal-sized pieces called "chunks".
    - We give EACH chunk to a SEPARATE THREAD.
    - Every thread runs the SAME function (analyze_chunk) but on
      DIFFERENT data. This is the definition of data parallelism,
      as opposed to task parallelism (where different threads run
      DIFFERENT functions).

WHY MULTITHREADING (and not multiprocessing) HERE?
    - Streamlit + multiprocessing is messy to set up for beginners
      (needs `if __name__ == "__main__":` guards, pickling, etc.)
    - Python's `threading` module is simple and beginner-friendly.
    - IMPORTANT (and this is a genuine, important limitation you
      should mention in your viva): Python has a Global Interpreter
      Lock (GIL). The GIL allows only ONE thread to execute Python
      bytecode at a time. This means for CPU-heavy, pure-Python work
      (like the simple string checks we do here), multithreading in
      Python does NOT give the same speedup you would get in a
      language like Java or C++. Threads are still genuinely useful
      for I/O-bound work (file reading, network calls, database
      queries) because the GIL is released during I/O waits.
    - This project measures REAL execution times so you can see this
      effect for yourself instead of just being told about it.

HOW RESULTS ARE COMBINED SAFELY (avoiding race conditions):
    - A "race condition" happens when two threads try to update the
      same shared variable at the same time, and the final value
      becomes wrong/unpredictable.
    - To prevent this, each thread first counts INFO/WARNING/ERROR
      ONLY within its own chunk (a *local* dictionary, not shared
      with anyone). No locking is needed for this part since nothing
      is shared yet.
    - Only AFTER a thread finishes counting its own chunk does it
      briefly acquire a `threading.Lock()` to add its local counts
      into the single shared result dictionary. The lock guarantees
      that only one thread can update the shared dictionary at any
      given instant, so counts are never lost or corrupted.
------------------------------------------------------
"""

import threading
import time


def analyze_line(line):
    """Same classification logic as the sequential version."""
    line_upper = line.upper()
    if "ERROR" in line_upper:
        return "ERROR"
    elif "WARNING" in line_upper:
        return "WARNING"
    elif "INFO" in line_upper:
        return "INFO"
    else:
        return "OTHER"


def split_into_chunks(lines, num_chunks):
    """
    Split the list of lines into `num_chunks` roughly equal pieces.

    Example: 100 lines split into 4 chunks -> 4 chunks of 25 lines each.
    This is the "data division" step of data parallelism.
    """
    n = len(lines)
    if num_chunks <= 0:
        num_chunks = 1
    chunk_size = max(1, n // num_chunks)

    chunks = []
    start = 0
    for i in range(num_chunks):
        # The LAST chunk takes any leftover lines (in case the
        # total doesn't divide evenly).
        if i == num_chunks - 1:
            chunks.append(lines[start:])
        else:
            chunks.append(lines[start:start + chunk_size])
            start += chunk_size

    # Remove any empty chunks (can happen if num_chunks > number of lines)
    chunks = [c for c in chunks if len(c) > 0]
    return chunks


def analyze_chunk(chunk, shared_counts, lock, thread_name, thread_log, delay_ms=0.0):
    """
    This function is run by EACH THREAD separately.

    Steps performed by every thread:
    1. Count INFO/WARNING/ERROR/OTHER lines WITHIN ITS OWN CHUNK ONLY.
       (This part touches no shared data, so it is 100% safe and can
       run at full speed in parallel with other threads.)
    2. Once done, acquire the lock and merge these local counts into
       the shared dictionary that all threads write into.
    """
    local_counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "OTHER": 0}

    for line in chunk:
        line = line.strip()
        if line == "":
            continue
        category = analyze_line(line)
        local_counts[category] += 1
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)   # simulated I/O wait (GIL is released)

    # ---- CRITICAL SECTION START ----
    # Only one thread may execute the code inside this "with" block
    # at any given time. This is what makes merging results SAFE.
    with lock:
        for key in shared_counts:
            shared_counts[key] += local_counts[key]
        thread_log.append(
            f"{thread_name} processed {len(chunk)} lines "
            f"(INFO={local_counts['INFO']}, WARNING={local_counts['WARNING']}, "
            f"ERROR={local_counts['ERROR']}, OTHER={local_counts['OTHER']})"
        )
    # ---- CRITICAL SECTION END ----


def analyze_log_parallel(lines, num_threads=4, delay_ms=0.0):
    """
    Analyze all log lines using MULTIPLE THREADS.

    Parameters
    ----------
    lines : list of str
        Every line of the log file.
    num_threads : int
        How many threads (and therefore how many chunks) to use.
    delay_ms : float
        Optional simulated I/O delay per line, in milliseconds (0 = off).

    Returns
    -------
    dict with:
        - counts: combined dictionary of {"INFO": x, "WARNING": y, ...}
        - total_lines: total number of lines processed
        - time_taken: how many seconds this took
        - num_threads_used: actual number of threads used (may be
          less than requested if the file is very small)
        - thread_log: a list of strings describing what each thread did
          (useful for the viva / demo, to PROVE threads really ran)
    """
    start_time = time.perf_counter()

    # Step 1: Divide the data into chunks (data parallelism)
    chunks = split_into_chunks(lines, num_threads)

    # Shared resources that ALL threads will write into
    shared_counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "OTHER": 0}
    lock = threading.Lock()
    thread_log = []
    threads = []

    # Step 2: Create and start one thread per chunk
    for i, chunk in enumerate(chunks):
        thread_name = f"Thread-{i + 1}"
        t = threading.Thread(
            target=analyze_chunk,
            args=(chunk, shared_counts, lock, thread_name, thread_log, delay_ms),
            name=thread_name,
        )
        threads.append(t)
        t.start()  # thread begins running analyze_chunk() right away

    # Step 3: Wait for ALL threads to finish before continuing.
    # .join() blocks the main program until that thread is done.
    for t in threads:
        t.join()

    end_time = time.perf_counter()
    time_taken = end_time - start_time

    return {
        "counts": shared_counts,
        "total_lines": sum(shared_counts.values()),
        "time_taken": time_taken,
        "num_threads_used": len(chunks),
        "thread_log": thread_log,
    }
