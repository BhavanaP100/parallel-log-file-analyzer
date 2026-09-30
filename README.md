# Parallel Log File Analyzer Using Multithreading

A mini-project for the **Parallel Computing** subject. It analyzes server
log files two ways — **sequentially** (one thread) and **in parallel**
(multiple threads) — and compares real, measured execution times so you
can see for yourself where multithreading helps in Python, and where it
doesn't.

---

## 1. Folder Structure

```
parallel_log_analyzer/
│
├── app.py                        # Main Streamlit web app (RUN THIS)
├── log_generator.py               # Script to generate sample log files
├── requirements.txt                # Python dependencies
├── README.md                       # This file
│
├── utils/
│   ├── __init__.py
│   ├── sequential_analyzer.py     # Single-threaded analysis logic
│   └── parallel_analyzer.py       # Multithreaded analysis logic
│
└── sample_logs/
    ├── small_log.txt              # 200 lines
    ├── medium_log.txt             # 20,000 lines
    └── large_log.txt              # 100,000 lines
```

---

## 2. Install Python (if not already installed)

1. Go to https://www.python.org/downloads/
2. Download **Python 3.10 or newer** for Windows.
3. Run the installer. **IMPORTANT:** On the first screen, check the box
   that says **"Add Python to PATH"** before clicking Install.
4. Verify installation — open Command Prompt and type:
   ```
   python --version
   ```
   You should see something like `Python 3.11.5`.

---

## 3. Open the Project in VS Code

1. Install [VS Code](https://code.visualstudio.com/) if you don't have it.
2. Install the **Python extension** in VS Code (from the Extensions tab,
   search "Python", install the one by Microsoft).
3. Open VS Code → File → Open Folder → select the `parallel_log_analyzer`
   folder.
4. Open a terminal inside VS Code: **Terminal → New Terminal**.

---

## 4. Set Up a Virtual Environment (recommended but optional)

In the VS Code terminal:
```bash
python -m venv venv
venv\Scripts\activate
```
(On Mac/Linux use `source venv/bin/activate` instead.)

You should now see `(venv)` at the start of your terminal line.

---

## 5. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `streamlit` — for the web interface
- `pandas` — for tables and charts

---

## 6. Run the Application

```bash
streamlit run app.py
```

Your browser should automatically open `http://localhost:8501`.
If it doesn't, copy that link into your browser manually.

---

## 7. Using the App

1. In the sidebar, choose the **number of threads** (default 4).
2. Upload a log file — use `sample_logs/large_log.txt` for the clearest
   demonstration, or upload your own `.txt`/`.log` file.
3. Click **"Run BOTH and Compare"**.
4. View:
   - Total lines processed
   - INFO / WARNING / ERROR counts (table + bar chart)
   - Sequential time vs Parallel time
   - Speedup value and an honest explanation of the result

**Bonus experiment:** Turn on **"Simulate I/O delay per line"** in the
sidebar and re-run. This simulates a scenario like each log line
triggering a small network call or database write. You will see a real,
substantial speedup here — this demonstrates that Python's threading
genuinely helps for I/O-bound work, even though it does not help much
for pure CPU-bound work (see `DOCUMENTATION.md` for why — this is the
GIL, Global Interpreter Lock).

---

## 8. Generating Your Own (Bigger) Log File

```bash
python log_generator.py
```
It will ask how many lines to generate, then save the file to
`sample_logs/generated_log.txt`, which you can then upload in the app.

---

## 9. Troubleshooting Common Errors

| Error | Cause | Fix |
|---|---|---|
| `'streamlit' is not recognized as an internal or external command` | Streamlit not installed, or venv not activated | Run `pip install -r requirements.txt` again, and make sure `(venv)` shows in your terminal |
| `ModuleNotFoundError: No module named 'utils'` | You ran the app from the wrong folder | Make sure your terminal is inside the `parallel_log_analyzer` folder before running `streamlit run app.py` |
| `python : command not found` | Python not added to PATH during install | Reinstall Python and check "Add Python to PATH", or use `py` instead of `python` on Windows |
| Browser doesn't open automatically | Firewall/OS setting | Manually open `http://localhost:8501` in your browser |
| Port 8501 already in use | Another Streamlit app is running | Run `streamlit run app.py --server.port 8502` and open that port instead |
| Uploaded file shows 0 lines | File encoding issue | Make sure the file is a plain `.txt`/`.log` file, not a `.docx` or `.pdf` |
| Threads seem to give no speedup (or are slower) | This is EXPECTED for pure CPU-bound work in Python because of the GIL | This is not a bug — read Section 6.5 ("GIL") in `DOCUMENTATION.md`. Try the "Simulate I/O delay" option to see genuine speedup. |

---

## 10. Key Files to Understand for Viva

- `utils/sequential_analyzer.py` — the single-threaded baseline
- `utils/parallel_analyzer.py` — the multithreaded version (chunking,
  thread creation, safe merging with a Lock)
- `app.py` — connects both to the Streamlit interface

See `DOCUMENTATION.md` for the full project report and `VIVA_QUESTIONS.md`
for 20 likely viva questions with answers.
