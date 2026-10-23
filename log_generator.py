"""
log_generator.py
------------------------------------------------------
A small standalone script to CREATE sample server log files for
testing the analyzer. You don't need to run this yourself unless
you want to generate a NEW/bigger log file — three ready-made
sample files are already provided in the sample_logs/ folder.

Run it from the terminal like this:
    python log_generator.py

It will ask you how many log lines you want to generate, then
create a file called "generated_log.txt" inside sample_logs/.
------------------------------------------------------
"""

import random
from datetime import datetime, timedelta

# Realistic-looking sample log messages for each category
INFO_MESSAGES = [
    "User logged in successfully",
    "File uploaded successfully",
    "Database connection established",
    "Cache refreshed",
    "Scheduled backup completed",
    "New user account created",
    "Payment processed successfully",
    "Session started for user",
    "Email sent successfully",
    "Report generated successfully",
]

WARNING_MESSAGES = [
    "Disk space running low",
    "API response time is high",
    "Deprecated function called",
    "Memory usage above 75 percent",
    "Retrying failed network request",
    "Configuration file missing, using defaults",
    "Slow database query detected",
    "Too many login attempts detected",
    "Cache miss rate is high",
    "Unusual traffic pattern detected",
]

ERROR_MESSAGES = [
    "Database connection failed",
    "Null pointer exception occurred",
    "File not found",
    "Unauthorized access attempt blocked",
    "Payment gateway timeout",
    "Server returned 500 internal error",
    "Failed to write to disk",
    "Out of memory error",
    "Invalid user credentials",
    "Service unavailable",
]


def generate_log_file(file_path, num_lines=10000, error_ratio=0.1, warning_ratio=0.2):
    """
    Generate a fake but realistic server log file.

    Parameters
    ----------
    file_path : str
        Where to save the generated log file.
    num_lines : int
        How many log lines to generate.
    error_ratio : float
        Approximate fraction of lines that should be ERROR (0.1 = 10%)
    warning_ratio : float
        Approximate fraction of lines that should be WARNING (0.2 = 20%)
        The rest of the lines will be INFO.
    """
    start_time = datetime.now() - timedelta(days=1)

    lines = []
    for i in range(num_lines):
        # Decide the category randomly based on the given ratios
        r = random.random()
        if r < error_ratio:
            level = "ERROR"
            message = random.choice(ERROR_MESSAGES)
        elif r < error_ratio + warning_ratio:
            level = "WARNING"
            message = random.choice(WARNING_MESSAGES)
        else:
            level = "INFO"
            message = random.choice(INFO_MESSAGES)

        timestamp = start_time + timedelta(seconds=i * random.randint(1, 3))
        line = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} {level} {message} [req_id={1000 + i}]"
        lines.append(line)

    with open(file_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Generated {num_lines} log lines -> {file_path}")


if __name__ == "__main__":
    # Simple interactive prompt when run directly from the terminal
    try:
        n = input("How many log lines do you want to generate? (default 10000): ").strip()
        n = int(n) if n else 10000
    except ValueError:
        n = 10000

    generate_log_file("sample_logs/generated_log.txt", num_lines=n)
