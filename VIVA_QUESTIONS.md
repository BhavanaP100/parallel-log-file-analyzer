# Viva Preparation — 20 Likely Questions & Simple Answers

**1. What is the aim of this project?**
To build a working application that analyzes server log files using
both sequential and multithreaded (parallel) approaches, and to
honestly compare their real, measured performance.

**2. What is a thread?**
A thread is the smallest unit of execution within a program. A single
program (process) can have multiple threads running concurrently,
sharing the same memory space.

**3. What is multithreading?**
Multithreading is running multiple threads within one program so that
several pieces of work can make progress at (or near) the same time.

**4. What is the difference between a process and a thread?**
A process is an independent running program with its own memory space.
A thread is a smaller unit *inside* a process; all threads of the same
process share that process's memory. Creating a thread is lighter/
cheaper than creating a whole new process.

**5. What is data parallelism? How is it used here?**
Data parallelism means running the *same* operation on different
pieces of data at the same time. Here, the same `analyze_chunk()`
function runs on different chunks of the log file, one chunk per
thread.

**6. What is task parallelism? Is it used in this project?**
Task parallelism means running *different* operations concurrently
(e.g., one thread parses data while another writes to a database).
This project uses data parallelism, not task parallelism, because
every thread does the identical job on different data.

**7. How is the log file divided among threads?**
The list of log lines is split into N roughly equal-sized,
non-overlapping chunks, where N is the number of threads chosen by the
user. Each thread receives exactly one chunk.

**8. What is a race condition?**
A race condition happens when two or more threads access and modify
shared data at the same time without proper coordination, causing
the final result to be incorrect or unpredictable, depending on timing.

**9. How does this project avoid race conditions?**
Each thread first counts its log lines into a *local* dictionary that
no other thread touches. Only when merging that local result into the
shared final dictionary does the thread acquire a `threading.Lock()`,
ensuring only one thread updates the shared dictionary at a time.

**10. What is a Lock in Python's threading module?**
A `Lock` is a synchronization primitive. Only one thread can "hold"
the lock at a time; other threads calling `lock.acquire()` (or using
`with lock:`) must wait until it's released. This prevents simultaneous
access to shared/critical data.

**11. What is the GIL (Global Interpreter Lock)?**
The GIL is a mechanism in CPython (the standard Python implementation)
that allows only one thread to execute Python bytecode at any given
instant, even on a multi-core CPU.

**12. Does multithreading always make Python programs faster?**
No. For CPU-bound, pure-Python work, the GIL limits real parallel
execution, so multithreading may give little or no speedup, and can
even be slightly slower due to thread management overhead. It helps
most for I/O-bound work (file/network/database waits), because the
GIL is released while a thread is waiting.

**13. Why did your project sometimes show the parallel version as
slower or equal, not faster?**
Because our log-line classification is simple CPU-bound string
matching. Under the GIL, threads take turns rather than truly running
simultaneously, and for smaller files the overhead of creating threads
outweighs any benefit. This is an accurate, expected result, not a bug.

**14. How did you demonstrate a case where multithreading DOES help?**
By adding an optional, clearly-labeled "simulated I/O delay" per line
(representing something like a network call). Since this is time spent
waiting rather than computing, Python releases the GIL during that
wait, and multiple threads can genuinely overlap — we measured close to
a 4x speedup with 4 threads in that mode.

**15. How do you measure execution time in Python?**
Using `time.perf_counter()` before and after the work, then subtracting
the two values. It gives a high-resolution timer suitable for
performance measurement.

**16. Why use `.join()` on each thread?**
`.join()` makes the main program wait until that particular thread has
completely finished running. Without calling `.join()` on all threads,
the program might try to read the final results before every thread
has finished writing them — giving wrong or incomplete counts.

**17. Why did you use threading instead of multiprocessing?**
Threading is simpler for beginners (no pickling issues, no
`if __name__ == "__main__":` requirement, shares memory directly, easy
to integrate with Streamlit). Multiprocessing would give real CPU
parallelism (each process has its own GIL) but adds complexity; it is
mentioned as future scope.

**18. What Python library did you use for the web interface, and why?**
Streamlit — because it lets you build an interactive web UI using pure
Python (no separate HTML/CSS/JavaScript needed), which is ideal for a
student project focused on the parallel computing logic rather than
web development.

**19. How did you verify your parallel implementation is correct?**
By comparing the INFO/WARNING/ERROR/OTHER counts produced by the
sequential method and the parallel method on the same file — they must
be identical. This was tested and confirmed on all three sample log
files (200, 20,000, and 100,000 lines).

**20. What would you improve if you had more time?**
Add a true multiprocessing-based comparison (to show genuine CPU
parallel speedup), support more log formats using regular expressions,
and add live/streaming log analysis instead of only static file
uploads.
