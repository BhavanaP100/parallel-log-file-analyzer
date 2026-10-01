"""
app.py
------------------------------------------------------
MAIN APPLICATION FILE
Run with:
    streamlit run app.py

This file is only responsible for the USER INTERFACE. All the real
log-analysis logic lives in utils/ and is imported here, not
re-implemented:
    - utils/log_utils.py            (file reading/validation, small helpers)
    - utils/sequential_analyzer.py  (single-threaded / baseline engine)
    - utils/parallel_analyzer.py    (multithreaded engine)

The app has 5 sections, chosen from the sidebar:
    1. Dashboard
    2. Log Analysis
    3. Performance Comparison
    4. How It Works
    5. About

A file is uploaded ONCE. The parsed lines are kept in
st.session_state so every section can use the same data without
asking the user to upload it again.
------------------------------------------------------
"""

import pandas as pd
import streamlit as st

from utils.log_utils import read_uploaded_file, counts_to_dataframe, format_seconds
from utils.sequential_analyzer import analyze_log_sequential
from utils.parallel_analyzer import analyze_log_parallel

PAGES = ["Dashboard", "Log Analysis", "Performance Comparison", "How It Works", "About"]


# ======================================================================
# SETUP: page config, CSS, session state
# ======================================================================

def configure_page():
    st.set_page_config(
        page_title="Parallel Log File Analyzer",
        page_icon=None,
        layout="wide",
    )
    try:
        with open("assets/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        # The app still works without the CSS file; it just looks plainer.
        pass


def init_session_state():
    """Create every session_state key we rely on, exactly once."""
    defaults = {
        "page": "Dashboard",
        "uploaded_signature": None,   # (filename, size) of the last processed upload
        "filename": None,
        "log_lines": None,
        "upload_warning": None,
        "sequential_result": None,
        "parallel_result": None,
        "latest_analysis": None,      # whichever result was computed most recently
        "num_threads": 4,
        "simulate_io": False,
        "io_delay_ms": 0.5,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_to(page_name):
    """Callback used by quick-access buttons to switch sidebar page."""
    st.session_state.page = page_name


def clear_everything():
    """Callback for the 'Clear file & results' button in the sidebar."""
    for key in ["uploaded_signature", "filename", "log_lines", "upload_warning",
                "sequential_result", "parallel_result", "latest_analysis"]:
        st.session_state[key] = None


# ======================================================================
# SHARED UPLOAD HANDLING (used by Dashboard and Log Analysis pages)
# ======================================================================

def render_uploader(key_suffix):
    """
    Renders a file_uploader widget and processes any new file through
    the SAME validation/reading logic (utils.log_utils.read_uploaded_file)
    regardless of which page the uploader is shown on. If the file is
    unchanged from what's already in session_state, nothing is
    re-processed.
    """
    uploaded_file = st.file_uploader(
        "Choose a .txt or .log file",
        type=["txt", "log"],
        key=f"uploader_{key_suffix}",
    )

    if uploaded_file is None:
        return

    signature = (uploaded_file.name, uploaded_file.size)
    if st.session_state.uploaded_signature == signature:
        return  # already processed this exact file, do nothing

    lines, warning, error = read_uploaded_file(uploaded_file)

    if error:
        st.error(error)
        return

    st.session_state.uploaded_signature = signature
    st.session_state.filename = uploaded_file.name
    st.session_state.log_lines = lines
    st.session_state.upload_warning = warning
    # A new file invalidates any previous analysis results.
    st.session_state.sequential_result = None
    st.session_state.parallel_result = None
    st.session_state.latest_analysis = None

    non_empty = sum(1 for line in lines if line.strip() != "")
    st.success(f"Loaded **{uploaded_file.name}** — {non_empty:,} non-empty lines found.")
    if warning:
        st.warning(warning)


# ======================================================================
# SMALL REUSABLE UI PIECES
# ======================================================================

def render_header():
    st.markdown(
        """
        <div class="app-header">
            <h1>Parallel Log File Analyzer</h1>
            <p>Analyze log files and compare sequential and multithreaded processing.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(counts, total):
    """A row of 4 custom metric cards: Total, INFO, WARNING, ERROR."""
    st.markdown(
        f"""
        <div class="metric-card-row">
            <div class="metric-card">
                <div class="metric-label">Total Log Entries</div>
                <div class="metric-value">{total:,}</div>
            </div>
            <div class="metric-card accent-info">
                <div class="metric-label">INFO</div>
                <div class="metric-value">{counts.get('INFO', 0):,}</div>
            </div>
            <div class="metric-card accent-warning">
                <div class="metric-label">WARNING</div>
                <div class="metric-value">{counts.get('WARNING', 0):,}</div>
            </div>
            <div class="metric-card accent-error">
                <div class="metric-label">ERROR</div>
                <div class="metric-value">{counts.get('ERROR', 0):,}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title, body, button_label=None, button_target=None):
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-title">{title}</div>
            <div>{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if button_label and button_target:
        st.button(button_label, on_click=go_to, args=(button_target,))


# ======================================================================
# PAGE 1: DASHBOARD
# ======================================================================

def page_dashboard():
    render_header()

    st.markdown(
        '<div class="section-subtext">'
        "This project analyzes server log files using two approaches — a single-threaded "
        "(sequential) engine and a multithreaded (parallel) engine — and compares their "
        "real, measured execution time. Upload a log file below to get started."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-heading">Upload a Log File</div>', unsafe_allow_html=True)
    render_uploader(key_suffix="dashboard")

    st.markdown('<div class="section-heading">Current Snapshot</div>', unsafe_allow_html=True)

    if st.session_state.log_lines is None:
        render_empty_state(
            "No file analyzed yet",
            "Upload a .txt or .log file above, then run an analysis from the "
            "Log Analysis page to see real metrics here.",
            button_label="Go to Log Analysis",
            button_target="Log Analysis",
        )
        return

    if st.session_state.latest_analysis is None:
        st.markdown(
            f'<div class="content-card">A file (<b>{st.session_state.filename}</b>) is loaded, '
            f'but it has not been analyzed yet.</div>',
            unsafe_allow_html=True,
        )
        st.button("Go to Log Analysis \u2192", on_click=go_to, args=("Log Analysis",), type="primary")
        return

    result = st.session_state.latest_analysis
    render_metric_cards(result["counts"], result["total_lines"])
    st.caption(
        f"From **{st.session_state.filename}**, using the "
        f"**{result['source']}** engine \u2014 processed in {format_seconds(result['time_taken'])}."
    )

    c1, c2 = st.columns(2)
    c1.button("Re-analyze this file \u2192", on_click=go_to, args=("Log Analysis",))
    c2.button("Compare performance \u2192", on_click=go_to, args=("Performance Comparison",))


# ======================================================================
# PAGE 2: LOG ANALYSIS
# ======================================================================

def page_log_analysis():
    render_header()
    st.markdown('<div class="section-heading">Log Analysis</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtext">Workflow: Upload Log File &rarr; Validate File &rarr; '
        "Analyze &rarr; Display Results.</div>",
        unsafe_allow_html=True,
    )

    st.caption("Supported file types: .txt, .log (plain text log files).")
    render_uploader(key_suffix="analysis")

    if st.session_state.log_lines is None:
        render_empty_state(
            "Nothing to analyze yet",
            "Upload a log file above to enable analysis.",
        )
        return

    lines = st.session_state.log_lines
    non_empty = sum(1 for line in lines if line.strip() != "")
    st.markdown(
        f'<div class="content-card">File: <b>{st.session_state.filename}</b> '
        f'&middot; {non_empty:,} non-empty lines ready to analyze.</div>',
        unsafe_allow_html=True,
    )

    analyze_clicked = st.button("Analyze", type="primary")

    if analyze_clicked:
        try:
            with st.spinner("Analyzing log file..."):
                result = analyze_log_sequential(lines)
        except Exception as exc:
            st.error("Something went wrong while analyzing this file. Please try a different file.")
            with st.expander("Technical details (for debugging)"):
                st.code(str(exc))
            return

        st.session_state.sequential_result = result
        st.session_state.latest_analysis = {**result, "source": "Sequential"}

    result = st.session_state.sequential_result
    if result is None:
        st.info("Click **Analyze** to process this file and see results.")
        return

    st.markdown('<div class="section-heading">Results</div>', unsafe_allow_html=True)
    render_metric_cards(result["counts"], result["total_lines"])

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="content-card"><h4>Log Level Distribution</h4>', unsafe_allow_html=True)
        df = counts_to_dataframe(result["counts"])
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="content-card"><h4>Distribution Chart</h4>', unsafe_allow_html=True)
        st.bar_chart(df.set_index("Log Level"))
        st.markdown("</div>", unsafe_allow_html=True)

    st.caption(f"Processed in {format_seconds(result['time_taken'])} (single-threaded baseline).")


# ======================================================================
# PAGE 3: PERFORMANCE COMPARISON
# ======================================================================

def render_architecture_diagram():
    st.markdown('<div class="section-heading">How the Work Is Divided</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="diagram-box">Log File
   |
   v
Divide Work into N Chunks</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="thread-box-row">
            <div class="thread-box">Thread 1</div>
            <div class="thread-box">Thread 2</div>
            <div class="thread-box">Thread 3</div>
            <div class="thread-box">Thread 4</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="diagram-box">   |
   v
Combine Results (using a Lock)
   |
   v
Final Analysis</div>
        """,
        unsafe_allow_html=True,
    )


def page_performance():
    render_header()
    st.markdown('<div class="section-heading">Performance Comparison</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtext">Compares the same file processed sequentially (one '
        "thread) and in parallel (multiple threads), using real, measured execution times."
        "</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.log_lines is None:
        render_empty_state(
            "No file loaded",
            "Upload a log file on the Dashboard or Log Analysis page first.",
            button_label="Go to Dashboard",
            button_target="Dashboard",
        )
        return

    lines = st.session_state.log_lines
    st.caption(f"Using **{st.session_state.filename}** ({len(lines):,} lines) for this comparison.")

    # ---- Controls ----
    st.markdown('<div class="section-heading">Settings</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.num_threads = st.slider(
            "Number of threads for parallel analysis",
            min_value=2, max_value=16, value=st.session_state.num_threads, step=1,
            help="The log file is split into this many chunks, one per thread.",
        )
    with c2:
        st.session_state.simulate_io = st.checkbox(
            "Simulate I/O delay per line (e.g. network call / DB write)",
            value=st.session_state.simulate_io,
            help=(
                "Pure CPU-bound Python code does not speed up much with threads because "
                "of the GIL (see 'How It Works'). Turn this on to simulate each log line "
                "also triggering a tiny I/O operation \u2014 this is where multithreading "
                "genuinely helps, because Python releases the GIL during I/O waits."
            ),
        )
        if st.session_state.simulate_io:
            st.session_state.io_delay_ms = st.slider(
                "Simulated delay per line (ms)",
                min_value=0.1, max_value=5.0, value=st.session_state.io_delay_ms, step=0.1,
            )

    delay_ms = st.session_state.io_delay_ms if st.session_state.simulate_io else 0.0

    # ---- Run buttons ----
    b1, b2, b3, b4 = st.columns(4)
    run_seq = b1.button("Run Sequential")
    run_par = b2.button("Run Parallel")
    run_both = b3.button("Run Both & Compare", type="primary")
    reset = b4.button("Reset Results")

    if reset:
        st.session_state.sequential_result = None
        st.session_state.parallel_result = None

    if run_seq or run_both:
        try:
            with st.spinner("Running sequential analysis..."):
                result = analyze_log_sequential(lines, delay_ms=delay_ms)
            st.session_state.sequential_result = result
            st.session_state.latest_analysis = {**result, "source": "Sequential"}
        except Exception as exc:
            st.error("Sequential analysis failed. Please try again.")
            with st.expander("Technical details (for debugging)"):
                st.code(str(exc))

    if run_par or run_both:
        try:
            with st.spinner(f"Running parallel analysis with {st.session_state.num_threads} threads..."):
                result = analyze_log_parallel(
                    lines, num_threads=st.session_state.num_threads, delay_ms=delay_ms
                )
            st.session_state.parallel_result = result
            st.session_state.latest_analysis = {**result, "source": "Parallel"}
        except Exception as exc:
            st.error("Parallel analysis failed. Please try again.")
            with st.expander("Technical details (for debugging)"):
                st.code(str(exc))

    seq_result = st.session_state.sequential_result
    par_result = st.session_state.parallel_result

    if seq_result is None and par_result is None:
        st.info("Choose your settings above, then click **Run Sequential**, **Run Parallel**, or **Run Both & Compare**.")
        render_architecture_diagram()
        return

    # ---- Results ----
    st.markdown('<div class="section-heading">Results</div>', unsafe_allow_html=True)
    r1, r2 = st.columns(2)

    with r1:
        st.markdown('<div class="content-card"><h4>Sequential (Single Thread)</h4>', unsafe_allow_html=True)
        if seq_result:
            st.metric("Time Taken", format_seconds(seq_result["time_taken"]))
            st.metric("Total Lines", f"{seq_result['total_lines']:,}")
            st.dataframe(counts_to_dataframe(seq_result["counts"]), hide_index=True, use_container_width=True)
        else:
            st.write("Not run yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with r2:
        title = f"Parallel ({par_result['num_threads_used']} Threads)" if par_result else "Parallel (Multithreaded)"
        st.markdown(f'<div class="content-card"><h4>{title}</h4>', unsafe_allow_html=True)
        if par_result:
            st.metric("Time Taken", format_seconds(par_result["time_taken"]))
            st.metric("Total Lines", f"{par_result['total_lines']:,}")
            st.dataframe(counts_to_dataframe(par_result["counts"]), hide_index=True, use_container_width=True)
            with st.expander("See what each thread did"):
                for line in par_result.get("thread_log", []):
                    st.text(line)
        else:
            st.write("Not run yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Comparison (only when both exist) ----
    if seq_result and par_result:
        st.markdown('<div class="section-heading">Sequential vs. Parallel</div>', unsafe_allow_html=True)

        seq_time = seq_result["time_taken"]
        par_time = par_result["time_taken"]
        speedup = (seq_time / par_time) if par_time > 0 else float("inf")

        c1, c2, c3 = st.columns(3)
        c1.metric("Sequential Time", format_seconds(seq_time))
        c2.metric("Parallel Time", format_seconds(par_time))
        c3.metric("Speedup (Seq \u00f7 Parallel)", f"{speedup:.2f}x")

        comparison_df = pd.DataFrame({
            "Method": ["Sequential", "Parallel"],
            "Time (seconds)": [seq_time, par_time],
        })
        st.bar_chart(comparison_df.set_index("Method"))

        st.markdown('<div class="section-heading">What Does This Result Mean?</div>', unsafe_allow_html=True)
        if st.session_state.simulate_io:
            if speedup > 1.05:
                st.success(
                    f"With simulated I/O delay enabled, the parallel version was **{speedup:.2f}x faster**. "
                    "This matches theory: while one thread is waiting for its simulated I/O operation, "
                    "Python releases the GIL and lets another thread run \u2014 this is where "
                    "multithreading genuinely helps in Python."
                )
            else:
                st.warning(
                    "Parallel version was not clearly faster this time. Try increasing the number of "
                    "threads or the simulated delay, or use a larger log file."
                )
        else:
            if speedup > 1.05:
                st.success(
                    f"The parallel version was **{speedup:.2f}x faster** on this run. Results can vary "
                    "between runs due to system load, thread-creation overhead, and file size."
                )
            elif speedup < 0.95:
                st.warning(
                    f"The parallel version was actually **slower** this time ({speedup:.2f}x). This is "
                    "an expected result for CPU-bound pure-Python code: Python's Global Interpreter Lock "
                    "(GIL) allows only one thread to execute Python bytecode at a time, so threads mostly "
                    "take turns rather than truly running simultaneously, and thread-management overhead "
                    "can outweigh any benefit. Try **'Simulate I/O delay'** above to see a case where "
                    "threading genuinely helps."
                )
            else:
                st.info(
                    f"Sequential and parallel times were roughly the same ({speedup:.2f}x) \u2014 also an "
                    "expected outcome for small or CPU-bound workloads under Python's GIL."
                )

    render_architecture_diagram()
    st.caption(
        "Sequential processing: one thread reads and classifies every line, one after another. "
        "Parallel processing: the file is split into N chunks, one thread classifies each chunk "
        "concurrently, and results are safely combined using a threading.Lock. See **How It Works** "
        "for the full explanation, including Python's GIL limitation."
    )


# ======================================================================
# PAGE 4: HOW IT WORKS
# ======================================================================

def page_how_it_works():
    render_header()
    st.markdown('<div class="section-heading">A. Sequential Processing</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="content-card">The file is processed using a single loop, in a single '
        "thread. Each line is read, checked for the keywords ERROR / WARNING / INFO, and "
        "counted \u2014 one line completes before the next one starts. This is the baseline "
        "we compare the multithreaded version against.</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-heading">B. Multithreaded Processing</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
        The log file is split into N roughly equal, non-overlapping chunks (N = number of
        threads chosen). Each chunk is handed to a separate <code>threading.Thread</code>,
        which classifies only its own lines into a local count dictionary that no other
        thread can see. Once a thread finishes counting its chunk, it briefly acquires a
        <code>threading.Lock</code> to add its local counts into one shared result dictionary.
        The lock guarantees only one thread updates the shared dictionary at a time, so no
        line is ever lost or double-counted.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-heading">C. Sequential vs. Parallel</div>', unsafe_allow_html=True)
    comparison_df = pd.DataFrame({
        "Aspect": ["Threads used", "Work division", "Best suited for", "Result combination", "Typical Python speedup"],
        "Sequential": ["1", "None \u2014 one line at a time", "Small files, simplicity", "Not applicable", "Baseline (1x)"],
        "Parallel (Threading)": [
            "N (user-selected)",
            "File split into N chunks",
            "I/O-bound work (network/disk waits)",
            "Local counts merged via a Lock",
            "Near Nx for I/O-bound work; little/no gain for pure CPU work",
        ],
    })
    st.dataframe(comparison_df, hide_index=True, use_container_width=True)

    st.markdown('<div class="section-heading">D. Limitations \u2014 Python\'s GIL</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
        Python's standard implementation (CPython) has a <b>Global Interpreter Lock (GIL)</b>:
        only one thread can execute Python bytecode at any instant, even on a multi-core CPU.
        For <b>CPU-bound</b> work \u2014 like the simple string checks used to classify a log
        line \u2014 threads mostly take turns rather than truly running at the same time, so
        multithreading may give little or no speedup, and can even be slightly slower once
        thread-creation overhead is included. The GIL is <b>released</b> during I/O waits
        (disk, network, database), which is why threading helps more for I/O-bound work.
        This app does not hide this limitation \u2014 it measures real times so you can see
        the effect for yourself on the Performance Comparison page.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ======================================================================
# PAGE 5: ABOUT
# ======================================================================

def page_about():
    render_header()

    st.markdown('<div class="section-heading">Objective</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="content-card">Build a log file analyzer that processes server logs '
        "using both sequential and multithreaded approaches, and honestly compare their "
        "real, measured performance \u2014 including cases where multithreading does not "
        "help, due to Python's GIL.</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-heading">Technology Stack</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
        <ul>
            <li>Python 3</li>
            <li>Streamlit \u2014 web interface</li>
            <li>Pandas \u2014 tables and charts</li>
            <li>Python <code>threading</code> module \u2014 multithreaded engine</li>
            <li>HTML/CSS (via Streamlit) \u2014 layout and styling</li>
        </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-heading">Major Features</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
        <ul>
            <li>Upload and analyze .txt / .log server log files</li>
            <li>Sequential (single-threaded) log analysis engine</li>
            <li>Multithreaded log analysis engine with safe result merging</li>
            <li>Real, measured execution-time comparison (no hard-coded numbers)</li>
            <li>Optional simulated I/O delay to fairly demonstrate when threading helps</li>
            <li>Log-level distribution tables and charts</li>
        </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-heading">Course Information</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="content-card">Mini-project for the subject: <b>Parallel Computing</b> '
        "(7th Semester, Computer Science Engineering).</div>",
        unsafe_allow_html=True,
    )


# ======================================================================
# MAIN
# ======================================================================

def render_sidebar():
    with st.sidebar:
        st.markdown("### Navigation")
        st.session_state.page = st.radio(
            "Go to", PAGES,
            index=PAGES.index(st.session_state.page),
            label_visibility="collapsed",
        )
        st.markdown("---")
        if st.session_state.filename:
            st.caption(f"Loaded file: **{st.session_state.filename}**")
        else:
            st.caption("No file loaded yet.")
        st.button("Clear file & results", on_click=clear_everything)


def main():
    configure_page()
    init_session_state()
    render_sidebar()

    page = st.session_state.page
    if page == "Dashboard":
        page_dashboard()
    elif page == "Log Analysis":
        page_log_analysis()
    elif page == "Performance Comparison":
        page_performance()
    elif page == "How It Works":
        page_how_it_works()
    elif page == "About":
        page_about()

    st.markdown(
        '<div class="app-footer">Mini Project: Parallel Log File Analyzer &middot; '
        "Subject: Parallel Computing &middot; Built with Python + Streamlit</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
