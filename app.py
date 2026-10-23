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
    - utils/ui.py                   (icons, hero, cards, charts)

The app has 5 sections, chosen from the sidebar:
    1. Dashboard
    2. Log Analysis
    3. Performance Comparison
    4. How It Works
    5. About

A file is uploaded (or a sample is chosen) ONCE. The parsed lines are
kept in st.session_state so every section can use the same data
without asking the user to upload it again.
------------------------------------------------------
"""

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import ui
from utils.log_utils import (
    read_uploaded_file, counts_to_dataframe, format_seconds, format_short_seconds, percent_of,
)
from utils.sequential_analyzer import analyze_log_sequential
from utils.parallel_analyzer import analyze_log_parallel

BASE_DIR = Path(__file__).parent
SAMPLE_DIR = BASE_DIR / "sample_logs"

NAV = [
    ("Dashboard", ":material/home:"),
    ("Log Analysis", ":material/description:"),
    ("Performance Comparison", ":material/bar_chart:"),
    ("How It Works", ":material/settings:"),
    ("About", ":material/info:"),
]
PAGES = [name for name, _ in NAV]

SAMPLES = {
    "small": ("Small Log", "small_log.txt"),
    "medium": ("Medium Log", "medium_log.txt"),
    "large": ("Large Log", "large_log.txt"),
}


# ======================================================================
# SETUP: page config, CSS, session state
# ======================================================================

def configure_page():
    st.set_page_config(
        page_title="Parallel Log File Analyzer",
        page_icon=":material/analytics:",
        layout="wide",
    )
    try:
        css = (BASE_DIR / "assets" / "style.css").read_text(encoding="utf-8")
        st.markdown(f"<style>{ui.icon_css()}\n{css}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        # The app still works without the CSS file; it just looks plainer.
        pass


def init_session_state():
    """Create every session_state key we rely on, exactly once."""
    defaults = {
        "page": "Dashboard",
        "filename": None,
        "log_lines": None,
        "upload_warning": None,
        "seen_upload": {},            # {uploader name: (filename, size)} already processed
        "uploader_version": 0,        # bump to reset the file_uploader widget
        "sequential_result": None,
        "parallel_result": None,
        "latest_analysis": None,      # whichever result was computed most recently
        "pending_run": None,          # "seq" | "par" | "both" requested by a button
        "num_threads": 4,
        "simulate_io": False,
        "io_delay_ms": 0.5,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_to(page_name):
    """Callback used by navigation buttons to switch page."""
    st.session_state.page = page_name


def reset_results():
    st.session_state.sequential_result = None
    st.session_state.parallel_result = None
    st.session_state.latest_analysis = None


def clear_everything():
    """Callback for the 'Clear file & results' button in the sidebar."""
    st.session_state.filename = None
    st.session_state.log_lines = None
    st.session_state.upload_warning = None
    st.session_state.seen_upload = {}
    st.session_state.uploader_version += 1   # empties the uploader widget
    reset_results()


# ======================================================================
# FILE LOADING (upload or bundled sample)
# ======================================================================

def set_loaded_file(name, lines, warning):
    """Store a validated file in session state and drop any old results."""
    st.session_state.filename = name
    st.session_state.log_lines = lines
    st.session_state.upload_warning = warning
    reset_results()


def load_sample(key):
    """Callback for the Small / Medium / Large sample buttons."""
    label, filename = SAMPLES[key]
    path = SAMPLE_DIR / filename
    try:
        raw = path.read_bytes()
    except OSError:
        st.session_state.upload_warning = f"Sample file not found: sample_logs/{filename}"
        return
    lines, warning, error = read_uploaded_file(io.BytesIO(raw))
    if error:
        st.session_state.upload_warning = error
        return
    set_loaded_file(filename, lines, warning)
    st.session_state.uploader_version += 1   # clear any previously uploaded file chip


def render_uploader(name):
    """
    Renders a file_uploader and sends any NEW file through the same
    validation (utils.log_utils.read_uploaded_file) on every page.
    """
    uploaded = st.file_uploader(
        "Upload a log file",
        type=["txt", "log"],
        key=f"uploader_{name}_{st.session_state.uploader_version}",
        label_visibility="collapsed",
    )
    if uploaded is None:
        return

    signature = (uploaded.name, uploaded.size)
    if st.session_state.seen_upload.get(name) == signature:
        return  # this exact file was already processed

    lines, warning, error = read_uploaded_file(uploaded)
    if error:
        st.error(error)
        return

    st.session_state.seen_upload[name] = signature
    set_loaded_file(uploaded.name, lines, warning)


def non_empty_count():
    lines = st.session_state.log_lines or []
    return sum(1 for line in lines if line.strip() != "")


def loaded_status():
    """One-line status under the sample buttons."""
    if st.session_state.filename:
        ui.html(
            f'<div class="loaded-chip">{ui.icon("info", 18)}<span>Loaded <b>{st.session_state.filename}</b>'
            f" &middot; {non_empty_count():,} non-empty lines</span></div>"
        )
        if st.session_state.upload_warning:
            st.warning(st.session_state.upload_warning)
    else:
        ui.html('<div class="idle-chip">No file loaded yet.</div>')
        if st.session_state.upload_warning:
            st.warning(st.session_state.upload_warning)


# ======================================================================
# RUNNING THE ENGINES (shared by Dashboard + Performance pages)
# ======================================================================

def current_delay_ms():
    return st.session_state.io_delay_ms if st.session_state.simulate_io else 0.0


def execute_analysis(mode):
    """
    Run the sequential and/or parallel engine on the loaded file and store
    the REAL measured results. mode is "seq", "par" or "both".
    """
    lines = st.session_state.log_lines
    delay_ms = current_delay_ms()

    if mode in ("seq", "both"):
        try:
            with st.spinner("Running sequential analysis..."):
                result = analyze_log_sequential(lines, delay_ms=delay_ms)
            st.session_state.sequential_result = result
            st.session_state.latest_analysis = {**result, "source": "Sequential"}
        except Exception as exc:
            st.error("Sequential analysis failed. Please try again.")
            with st.expander("Technical details (for debugging)"):
                st.code(str(exc))

    if mode in ("par", "both"):
        try:
            threads = st.session_state.num_threads
            with st.spinner(f"Running parallel analysis with {threads} threads..."):
                result = analyze_log_parallel(lines, num_threads=threads, delay_ms=delay_ms)
            st.session_state.parallel_result = result
            st.session_state.latest_analysis = {**result, "source": "Multithreaded"}
        except Exception as exc:
            st.error("Parallel analysis failed. Please try again.")
            with st.expander("Technical details (for debugging)"):
                st.code(str(exc))


def request_run(mode):
    """Button callback: remember what was asked; the page runs it before drawing results."""
    st.session_state.pending_run = mode


def run_pending():
    mode = st.session_state.pending_run
    st.session_state.pending_run = None
    if mode is None:
        return
    if st.session_state.log_lines is None:
        st.toast("Upload a log file or pick a sample log first.", icon=":material/warning:")
        return
    execute_analysis(mode)


# ======================================================================
# PAGE 1: DASHBOARD
# ======================================================================

def card(key):
    """A white rounded card. All cards share the 'card_' key prefix for CSS."""
    return st.container(key=f"card_{key}")


def upload_card():
    with card("upload"):
        ui.card_title(ui.icon("upload", 26), "Upload Log File",
                      "Upload a .log or .txt file to analyze. You can also use the sample logs provided.")
        render_uploader("dashboard")
        ui.html('<div class="up-meta"><span>Supported format: .log, .txt (UTF-8)</span>'
                "<span>Max file size: 100 MB</span></div>")
        ui.html('<div class="or-divider">OR</div>')
        ui.html(f'<div class="sub-title">{ui.icon("database", 20)}<span class="t">Use Sample Logs</span></div>')
        cols = st.columns(3)
        for col, key in zip(cols, SAMPLES):
            with col:
                st.button(SAMPLES[key][0], key=f"sample_{key}", on_click=load_sample, args=(key,),
                          width="stretch")
        loaded_status()


def quick_actions_card():
    with card("actions"):
        ui.card_title(ui.icon("gear", 26), "Quick Actions",
                      "Run analysis on the uploaded file using different methods.")
        st.button("Run Sequential Analysis", key="qa_seq", icon=":material/play_arrow:",
                  on_click=request_run, args=("seq",), width="stretch")
        st.button("Run Parallel Analysis", key="qa_par", icon=":material/groups:",
                  on_click=request_run, args=("par",), width="stretch")
        st.button("Run Both & Compare", key="qa_both", icon=":material/fast_forward:",
                  on_click=request_run, args=("both",), width="stretch")
        delay = f"{st.session_state.io_delay_ms:g} ms I/O delay" if st.session_state.simulate_io else "no simulated I/O delay"
        ui.html(f'<div class="qa-hint">Parallel uses {st.session_state.num_threads} threads, {delay}. '
                "Change this on the Performance Comparison page.</div>")


def distribution_card(result):
    with card("dist"):
        ui.card_title(ui.icon("bars", 26), "Log Level Distribution")
        if result is None:
            ui.empty_note("No results yet", "Run an analysis to see how log levels are distributed.")
            return
        c1, c2 = st.columns([1, 1.05])
        with c1:
            ui.level_pie(result["counts"])
        with c2:
            ui.level_legend(result["counts"], result["total_lines"])


def time_card():
    seq = st.session_state.sequential_result
    par = st.session_state.parallel_result
    with card("time"):
        ui.card_title(ui.icon("clock", 26), "Execution Time Comparison")
        if seq is None and par is None:
            ui.empty_note("No timings yet", "Run an analysis (or Run Both &amp; Compare) to see measured execution times.")
            return
        ui.time_bar(seq["time_taken"] if seq else None, par["time_taken"] if par else None)
        if seq and par and par["time_taken"] > 0:
            speedup = seq["time_taken"] / par["time_taken"]
            ui.html(f'<div class="qa-hint">Measured speedup (sequential &divide; multithreaded): <b>{speedup:.2f}x</b></div>')


def page_dashboard():
    ui.dashboard_hero()
    run_pending()

    result = st.session_state.latest_analysis
    ui.level_cards(result["counts"] if result else None, result["total_lines"] if result else 0)

    left, right = st.columns([1.42, 1], gap="medium")
    with left:
        upload_card()
    with right:
        quick_actions_card()

    left, right = st.columns([0.89, 1], gap="medium")
    with left:
        distribution_card(result)
    with right:
        time_card()


# ======================================================================
# PAGE 2: LOG ANALYSIS
# ======================================================================

def page_log_analysis():
    ui.hero("LOG ANALYSIS", "Log Analysis",
            "Workflow: Upload Log File \u2192 Validate File \u2192 Analyze \u2192 Display Results.", compact=True)

    with card("la_upload"):
        ui.card_title(ui.icon("upload", 26), "Upload Log File", "Supported file types: .txt, .log (plain text log files).")
        render_uploader("analysis")

    if st.session_state.log_lines is None:
        ui.empty_note("Nothing to analyze yet", "Upload a log file above, or pick a sample on the Dashboard.")
        return

    ui.html(f'<div class="loaded-chip">{ui.icon("info", 18)}<span>File: <b>{st.session_state.filename}</b>'
            f" &middot; {non_empty_count():,} non-empty lines ready to analyze.</span></div>")
    if st.session_state.upload_warning:
        st.warning(st.session_state.upload_warning)

    if st.button("Analyze", type="primary"):
        try:
            with st.spinner("Analyzing log file..."):
                result = analyze_log_sequential(st.session_state.log_lines)
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

    ui.section_heading("Results")
    ui.level_cards(result["counts"], result["total_lines"])

    col1, col2 = st.columns([1, 1], gap="medium")
    with col1:
        with card("la_table"):
            ui.card_title(ui.icon("database", 24), "Log Level Table")
            st.dataframe(counts_to_dataframe(result["counts"]), hide_index=True, width="stretch")
    with col2:
        with card("la_chart"):
            ui.card_title(ui.icon("bars", 24), "Distribution Chart")
            ui.level_pie(result["counts"])

    st.caption(f"Processed in {format_seconds(result['time_taken'])} (single-threaded baseline).")


# ======================================================================
# PAGE 3: PERFORMANCE COMPARISON
# ======================================================================

def render_architecture_diagram():
    ui.section_heading("How the Work Is Divided")
    ui.html('<div class="diagram-box">Log File\n   |\n   v\nDivide Work into N Chunks</div>'.replace("\n", "&#10;"))
    ui.html('<div class="thread-box-row">'
            + "".join(f'<div class="thread-box">Thread {i}</div>' for i in range(1, 5)) + "</div>")
    ui.html('<div class="diagram-box">   |&#10;   v&#10;Combine Results (using a Lock)&#10;   |&#10;   v&#10;Final Analysis</div>')


def page_performance():
    ui.hero("PERFORMANCE", "Performance Comparison",
            "The same file processed sequentially (one thread) and in parallel (multiple threads), "
            "using real, measured execution times.", compact=True)

    if st.session_state.log_lines is None:
        ui.empty_note("No file loaded", "Upload a log file or pick a sample on the Dashboard first.")
        st.button("Go to Dashboard", on_click=go_to, args=("Dashboard",), type="primary")
        return

    lines = st.session_state.log_lines
    st.caption(f"Using **{st.session_state.filename}** ({len(lines):,} lines) for this comparison.")

    # ---- Controls ----
    with card("perf_settings"):
        ui.card_title(ui.icon("gear", 24), "Settings")
        c1, c2 = st.columns(2, gap="large")
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

    # ---- Run buttons ----
    b1, b2, b3, b4 = st.columns(4)
    run_seq = b1.button("Run Sequential", width="stretch")
    run_par = b2.button("Run Parallel", width="stretch")
    run_both = b3.button("Run Both & Compare", type="primary", width="stretch")
    reset = b4.button("Reset Results", width="stretch")

    if reset:
        reset_results()
    if run_both:
        execute_analysis("both")
    elif run_seq:
        execute_analysis("seq")
    elif run_par:
        execute_analysis("par")

    seq_result = st.session_state.sequential_result
    par_result = st.session_state.parallel_result

    if seq_result is None and par_result is None:
        st.info("Choose your settings above, then click **Run Sequential**, **Run Parallel**, or **Run Both & Compare**.")
        render_architecture_diagram()
        return

    # ---- Results ----
    ui.section_heading("Results")
    r1, r2 = st.columns(2, gap="medium")

    with r1:
        with card("perf_seq"):
            ui.card_title(ui.icon("clock", 24), "Sequential (Single Thread)")
            if seq_result:
                ui.stat_grid([
                    ui.stat_card("Time Taken", format_short_seconds(seq_result["time_taken"]), "Single thread", "blue", ui.icon("clock_solid", 28)),
                    ui.stat_card("Total Lines", f"{seq_result['total_lines']:,}", "Lines processed", "blue", ui.icon("file", 28)),
                ])
                st.dataframe(counts_to_dataframe(seq_result["counts"]), hide_index=True, width="stretch")
            else:
                st.write("Not run yet.")

    with r2:
        with card("perf_par"):
            title = f"Multithreaded ({par_result['num_threads_used']} Threads)" if par_result else "Multithreaded"
            ui.card_title(ui.icon("gear", 24), title)
            if par_result:
                ui.stat_grid([
                    ui.stat_card("Time Taken", format_short_seconds(par_result["time_taken"]), f"{par_result['num_threads_used']} threads", "green", ui.icon("clock_solid", 28)),
                    ui.stat_card("Total Lines", f"{par_result['total_lines']:,}", "Lines processed", "green", ui.icon("file", 28)),
                ])
                st.dataframe(counts_to_dataframe(par_result["counts"]), hide_index=True, width="stretch")
                with st.expander("See what each thread did"):
                    for line in par_result.get("thread_log", []):
                        st.text(line)
            else:
                st.write("Not run yet.")

    # ---- Comparison (only when both exist) ----
    if seq_result and par_result:
        ui.section_heading("Sequential vs. Multithreaded")

        seq_time = seq_result["time_taken"]
        par_time = par_result["time_taken"]
        speedup = (seq_time / par_time) if par_time > 0 else float("inf")

        ui.stat_grid([
            ui.stat_card("Sequential Time", format_short_seconds(seq_time), "Single thread", "blue", ui.icon("clock_solid", 28)),
            ui.stat_card("Parallel Time", format_short_seconds(par_time), f"{par_result['num_threads_used']} threads", "green", ui.icon("clock_solid", 28)),
            ui.stat_card("Speedup", f"{speedup:.2f}x", "Sequential \u00f7 Parallel", "purple", ui.icon("speed", 28)),
        ])
        with card("perf_chart"):
            ui.card_title(ui.icon("clock", 24), "Execution Time Comparison")
            ui.time_bar(seq_time, par_time)

        ui.section_heading("What Does This Result Mean?")
        explain_result(speedup)

    render_architecture_diagram()
    st.caption(
        "Sequential processing: one thread reads and classifies every line, one after another. "
        "Parallel processing: the file is split into N chunks, one thread classifies each chunk "
        "concurrently, and results are safely combined using a threading.Lock. See **How It Works** "
        "for the full explanation, including Python's GIL limitation."
    )


def explain_result(speedup):
    """Honest, measured-result explanation (unchanged logic from the original app)."""
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


# ======================================================================
# PAGE 4: HOW IT WORKS
# ======================================================================

def page_how_it_works():
    ui.hero("EXPLAINER", "How It Works",
            "Two engines, one file: how sequential and multithreaded processing differ.", compact=True)

    ui.info_card(
        "A. Sequential Processing",
        "The file is processed using a single loop, in a single thread. Each line is read, checked for "
        "the keywords ERROR / WARNING / INFO, and counted \u2014 one line completes before the next one "
        "starts. This is the baseline we compare the multithreaded version against.",
    )
    ui.info_card(
        "B. Multithreaded Processing",
        "The log file is split into N roughly equal, non-overlapping chunks (N = number of threads "
        "chosen). Each chunk is handed to a separate <code>threading.Thread</code>, which classifies "
        "only its own lines into a local count dictionary that no other thread can see. Once a thread "
        "finishes counting its chunk, it briefly acquires a <code>threading.Lock</code> to add its "
        "local counts into one shared result dictionary. The lock guarantees only one thread updates "
        "the shared dictionary at a time, so no line is ever lost or double-counted.",
    )

    ui.section_heading("C. Sequential vs. Parallel")
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
    st.dataframe(comparison_df, hide_index=True, width="stretch")

    ui.info_card(
        "D. Limitations \u2014 Python's GIL",
        "Python's standard implementation (CPython) has a <b>Global Interpreter Lock (GIL)</b>: only "
        "one thread can execute Python bytecode at any instant, even on a multi-core CPU. For "
        "<b>CPU-bound</b> work \u2014 like the simple string checks used to classify a log line \u2014 "
        "threads mostly take turns rather than truly running at the same time, so multithreading may "
        "give little or no speedup, and can even be slightly slower once thread-creation overhead is "
        "included. The GIL is <b>released</b> during I/O waits (disk, network, database), which is why "
        "threading helps more for I/O-bound work. This app does not hide this limitation \u2014 it "
        "measures real times so you can see the effect for yourself on the Performance Comparison page.",
    )


# ======================================================================
# PAGE 5: ABOUT
# ======================================================================

def page_about():
    ui.hero("COLLEGE PROJECT", "About", "Objective, technology stack and features of this mini-project.", compact=True)

    ui.info_card(
        "Objective",
        "Build a log file analyzer that processes server logs using both sequential and multithreaded "
        "approaches, and honestly compare their real, measured performance \u2014 including cases where "
        "multithreading does not help, due to Python's GIL.",
    )
    ui.info_card(
        "Technology Stack",
        "<ul><li>Python 3</li><li>Streamlit \u2014 web interface</li><li>Pandas \u2014 tables and data handling</li>"
        "<li>Python <code>threading</code> module \u2014 multithreaded engine</li>"
        "<li>HTML/CSS (via Streamlit) \u2014 layout and styling</li></ul>",
    )
    ui.info_card(
        "Major Features",
        "<ul><li>Upload and analyze .txt / .log server log files, or use the bundled sample logs</li>"
        "<li>Sequential (single-threaded) log analysis engine</li>"
        "<li>Multithreaded log analysis engine with safe result merging</li>"
        "<li>Real, measured execution-time comparison (no hard-coded numbers)</li>"
        "<li>Optional simulated I/O delay to fairly demonstrate when threading helps</li>"
        "<li>Log-level distribution tables and charts</li></ul>",
    )
    ui.info_card(
        "Course Information",
        "Mini-project for the subject: <b>Parallel Computing</b> (7th Semester, Computer Science Engineering).",
    )


# ======================================================================
# SIDEBAR + MAIN
# ======================================================================

def render_sidebar():
    with st.sidebar:
        ui.sidebar_brand()
        for name, material_icon in NAV:
            st.button(
                name, key=f"nav_{name}", icon=material_icon, on_click=go_to, args=(name,),
                type="primary" if st.session_state.page == name else "secondary",
                width="stretch",
            )
        if st.session_state.filename:
            ui.html(f'<div class="file-note">Loaded file: <b>{st.session_state.filename}</b></div>')
            st.button("Clear file & results", key="clear_btn", on_click=clear_everything, width="stretch")
        with st.container(key="built_with"):
            ui.sidebar_built_with()


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

    ui.html('<div class="app-footer">Mini Project: Parallel Log File Analyzer &middot; '
            "Subject: Parallel Computing &middot; Built with Python + Streamlit</div>")


if __name__ == "__main__":
    main()
