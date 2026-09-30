"""
app.py
------------------------------------------------------
MAIN APPLICATION FILE
This is the file you run to start the web app:
    streamlit run app.py

It builds the user interface using Streamlit and connects the
buttons/inputs to our two analyzer engines:
    - utils/sequential_analyzer.py   (single-threaded / baseline)
    - utils/parallel_analyzer.py     (multithreaded)
------------------------------------------------------
"""

import io
import time

import pandas as pd
import streamlit as st

from utils.sequential_analyzer import analyze_log_sequential
from utils.parallel_analyzer import analyze_log_parallel

# ----------------------------------------------------------------
# PAGE CONFIGURATION
# ----------------------------------------------------------------
st.set_page_config(
    page_title="Parallel Log File Analyzer",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Parallel Log File Analyzer Using Multithreading")
st.caption(
    "A mini-project demonstrating Sequential vs Multithreaded processing "
    "in Python for the subject: Parallel Computing"
)

# ----------------------------------------------------------------
# SIDEBAR: Settings
# ----------------------------------------------------------------
st.sidebar.header("⚙️ Settings")

num_threads = st.sidebar.slider(
    "Number of threads for parallel analysis",
    min_value=2, max_value=16, value=4, step=1,
    help="This decides how many chunks the log file is split into, "
         "and how many threads process it simultaneously.",
)

simulate_io = st.sidebar.checkbox(
    "Simulate I/O delay per line (e.g. sending alert / DB write)",
    value=False,
    help=(
        "Pure CPU-bound Python code does NOT speed up much with threads "
        "because of the GIL (explained in the Documentation tab). "
        "Turn this ON to simulate a more realistic scenario where each "
        "log line also triggers a tiny I/O operation (like a network call "
        "or database write) — this is where multithreading genuinely helps, "
        "because Python releases the GIL during I/O waits."
    ),
)

io_delay_ms = 0.0
if simulate_io:
    io_delay_ms = st.sidebar.slider(
        "Simulated I/O delay per line (milliseconds)",
        min_value=0.1, max_value=5.0, value=0.5, step=0.1,
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Tip:** Use the sample log files in `sample_logs/` if you don't "
    "have your own log file yet. `large_log.txt` (100,000 lines) shows "
    "the performance difference most clearly."
)

# ----------------------------------------------------------------
# FILE UPLOAD
# ----------------------------------------------------------------
st.subheader("1️⃣ Upload a Log File")

uploaded_file = st.file_uploader(
    "Choose a .txt or .log file", type=["txt", "log"]
)

lines = None

if uploaded_file is not None:
    raw_bytes = uploaded_file.read()
    text = raw_bytes.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    st.success(f"File loaded: **{uploaded_file.name}** — {len(lines):,} lines found.")
    with st.expander("Preview first 10 lines"):
        st.code("\n".join(lines[:10]))
else:
    st.info(
        "No file uploaded yet. You can upload your own `.txt`/`.log` file above, "
        "or copy one of the files from the `sample_logs/` folder "
        "(small_log.txt, medium_log.txt, large_log.txt) and upload it here."
    )

# ----------------------------------------------------------------
# HELPER: add optional simulated I/O delay into the analyzer calls
# ----------------------------------------------------------------
def maybe_wrap_with_delay(lines_in, delay_ms):
    """
    If the user enabled 'simulate I/O delay', we wrap every line with
    a tiny sleep. We do this by monkey-patching a small delay INSIDE
    the classification step via a simple wrapper function, so both
    the sequential and parallel analyzers experience the identical
    per-line workload — keeping the comparison fair.
    """
    if delay_ms and delay_ms > 0:
        time.sleep(delay_ms / 1000.0)


# We patch the analyze_line-equivalent behavior by wrapping the two
# analyzer entry points with a thin timing-delay layer, without
# touching their core counting logic (kept in utils/ for clarity).
def run_sequential_with_delay(lines_in, delay_ms):
    start = time.perf_counter()
    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "OTHER": 0}
    from utils.sequential_analyzer import analyze_line
    for line in lines_in:
        line = line.strip()
        if line == "":
            continue
        counts[analyze_line(line)] += 1
        if delay_ms:
            time.sleep(delay_ms / 1000.0)
    end = time.perf_counter()
    return {"counts": counts, "total_lines": sum(counts.values()), "time_taken": end - start}


def run_parallel_with_delay(lines_in, threads, delay_ms):
    import threading
    from utils.parallel_analyzer import analyze_line, split_into_chunks

    start = time.perf_counter()
    chunks = split_into_chunks(lines_in, threads)
    shared_counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "OTHER": 0}
    lock = threading.Lock()
    thread_log = []

    def worker(chunk, name):
        local_counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "OTHER": 0}
        for line in chunk:
            line = line.strip()
            if line == "":
                continue
            local_counts[analyze_line(line)] += 1
            if delay_ms:
                time.sleep(delay_ms / 1000.0)
        with lock:
            for k in shared_counts:
                shared_counts[k] += local_counts[k]
            thread_log.append(f"{name} processed {len(chunk)} lines")

    threads_list = []
    for i, chunk in enumerate(chunks):
        t = threading.Thread(target=worker, args=(chunk, f"Thread-{i+1}"))
        threads_list.append(t)
        t.start()
    for t in threads_list:
        t.join()

    end = time.perf_counter()
    return {
        "counts": shared_counts,
        "total_lines": sum(shared_counts.values()),
        "time_taken": end - start,
        "num_threads_used": len(chunks),
        "thread_log": thread_log,
    }


# ----------------------------------------------------------------
# ANALYSIS
# ----------------------------------------------------------------
st.subheader("2️⃣ Run the Analysis")

col1, col2 = st.columns(2)
run_seq = col1.button("▶ Run Sequential Analysis", use_container_width=True)
run_par = col2.button("▶ Run Parallel Analysis (Multithreaded)", use_container_width=True)
run_both = st.button("⚡ Run BOTH and Compare", use_container_width=True, type="primary")

if "sequential_result" not in st.session_state:
    st.session_state.sequential_result = None
if "parallel_result" not in st.session_state:
    st.session_state.parallel_result = None

if lines is None and (run_seq or run_par or run_both):
    st.error("Please upload a log file first.")

if lines is not None:
    if run_seq or run_both:
        with st.spinner("Running sequential analysis..."):
            if simulate_io:
                result = run_sequential_with_delay(lines, io_delay_ms)
            else:
                result = analyze_log_sequential(lines)
            st.session_state.sequential_result = result

    if run_par or run_both:
        with st.spinner(f"Running parallel analysis with {num_threads} threads..."):
            if simulate_io:
                result = run_parallel_with_delay(lines, num_threads, io_delay_ms)
            else:
                result = analyze_log_parallel(lines, num_threads=num_threads)
            st.session_state.parallel_result = result

# ----------------------------------------------------------------
# RESULTS
# ----------------------------------------------------------------
seq_result = st.session_state.sequential_result
par_result = st.session_state.parallel_result

if seq_result or par_result:
    st.subheader("3️⃣ Results")

    r1, r2 = st.columns(2)

    with r1:
        if seq_result:
            st.markdown("### 🔵 Sequential (Single Thread)")
            st.metric("Total Lines Processed", f"{seq_result['total_lines']:,}")
            st.metric("Time Taken", f"{seq_result['time_taken']:.4f} sec")
            df_seq = pd.DataFrame(
                seq_result["counts"].items(), columns=["Log Level", "Count"]
            )
            st.dataframe(df_seq, hide_index=True, use_container_width=True)
            st.bar_chart(df_seq.set_index("Log Level"))
        else:
            st.markdown("### 🔵 Sequential (Single Thread)")
            st.write("Not run yet.")

    with r2:
        if par_result:
            st.markdown(f"### 🟢 Parallel ({par_result.get('num_threads_used', num_threads)} Threads)")
            st.metric("Total Lines Processed", f"{par_result['total_lines']:,}")
            st.metric("Time Taken", f"{par_result['time_taken']:.4f} sec")
            df_par = pd.DataFrame(
                par_result["counts"].items(), columns=["Log Level", "Count"]
            )
            st.dataframe(df_par, hide_index=True, use_container_width=True)
            st.bar_chart(df_par.set_index("Log Level"))
            with st.expander("See what each thread did"):
                for line in par_result.get("thread_log", []):
                    st.text(line)
        else:
            st.markdown("### 🟢 Parallel (Multithreaded)")
            st.write("Not run yet.")

    # ------------------------------------------------------------
    # COMPARISON (only if both have been run)
    # ------------------------------------------------------------
    if seq_result and par_result:
        st.subheader("4️⃣ Performance Comparison")

        seq_time = seq_result["time_taken"]
        par_time = par_result["time_taken"]

        if par_time > 0:
            speedup = seq_time / par_time
        else:
            speedup = float("inf")

        c1, c2, c3 = st.columns(3)
        c1.metric("Sequential Time", f"{seq_time:.4f} sec")
        c2.metric("Parallel Time", f"{par_time:.4f} sec")
        c3.metric("Speedup (Sequential / Parallel)", f"{speedup:.2f}x")

        comparison_df = pd.DataFrame({
            "Method": ["Sequential", "Parallel"],
            "Time (seconds)": [seq_time, par_time],
        })
        st.bar_chart(comparison_df.set_index("Method"))

        # Honest, technically accurate interpretation of the result
        st.markdown("#### 📌 What does this result mean?")
        if simulate_io:
            if speedup > 1.05:
                st.success(
                    f"With simulated I/O delay enabled, the parallel version was "
                    f"**{speedup:.2f}x faster**. This matches theory: while one thread "
                    f"is *waiting* for its simulated I/O operation, Python releases the "
                    f"GIL (Global Interpreter Lock) and lets another thread run. "
                    f"This is where multithreading genuinely helps in Python."
                )
            else:
                st.warning(
                    "Parallel version was not clearly faster this time. Try increasing "
                    "the number of threads or the I/O delay, or use a larger log file."
                )
        else:
            if speedup > 1.05:
                st.success(
                    f"The parallel version was **{speedup:.2f}x faster** on this run. "
                    f"Note: results can vary between runs due to system load, thread "
                    f"creation overhead, and the size of the file."
                )
            elif speedup < 0.95:
                st.warning(
                    f"The parallel version was actually **slower** this time "
                    f"({speedup:.2f}x). This is a genuinely important and expected "
                    f"result for CPU-bound pure-Python code: Python's GIL (Global "
                    f"Interpreter Lock) allows only one thread to execute Python "
                    f"bytecode at a time. Since our line classification is simple "
                    f"CPU work with no real I/O waiting, threads mostly take turns "
                    f"instead of truly running simultaneously — and the overhead of "
                    f"creating/managing threads can outweigh any benefit. "
                    f"Try enabling **'Simulate I/O delay'** in the sidebar to see a "
                    f"scenario where threading genuinely helps."
                )
            else:
                st.info(
                    f"Sequential and parallel times were roughly the same "
                    f"({speedup:.2f}x) — this is also an expected outcome for "
                    f"small/CPU-bound workloads under Python's GIL."
                )

# ----------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------
st.markdown("---")
st.caption(
    "Mini Project: Parallel Log File Analyzer Using Multithreading | "
    "Subject: Parallel Computing | Built with Python + Streamlit"
)
