# Parallel Log File Analyzer

Analyze server log files and compare **sequential** vs **multithreaded** processing.
Built with Python, Streamlit and Pandas. Mini-project for Parallel Computing.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

## Project layout

```
app.py                  UI and page logic (run this)
assets/style.css        All visual styling (navy sidebar, cards, buttons)
.streamlit/config.toml  Theme colours/font, 100 MB upload limit
utils/
  sequential_analyzer.py  single-threaded engine (baseline)
  parallel_analyzer.py    multithreaded engine (chunks + threading.Lock)
  log_utils.py            file validation + small helpers
  ui.py                   icons, hero banner, cards, charts
sample_logs/            small (200), medium (20,000), large (100,000) lines
log_generator.py        create your own sample log
```

## Notes

- Timings are measured live; nothing is hard-coded.
- Because of Python's GIL, pure CPU-bound work often shows little or no speedup
  with threads. Tick **"Simulate I/O delay"** on the Performance Comparison page
  to see the case where threading genuinely helps.
- Edit `assets/style.css` to change colours; the main palette is at the top (`:root`).
