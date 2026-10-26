# ib-study-planner

`ib-study-planner` is an offline, content-neutral command-line planning aid. It turns a CSV of **your own** topic names, priorities, estimated study minutes, and mastery levels into a date-bounded Markdown or JSON plan. It has no runtime dependencies and makes no network calls.

This is a planning aid, not official IB guidance. It does not include, quote, scrape, or claim alignment to any official or copyrighted syllabus. You supply the content. Adjust priorities and time estimates to the requirements of your actual course and exam.

## Requirements and install

Python 3.10 or newer is required. Install the package from the project root:

```bash
python -m pip install .
```

The install provides the `ib-study-planner` command. You can also run it from a source checkout with `PYTHONPATH=src python -m ib_study_planner ...`.

## Input CSV

The CSV must have these columns, in this order:

```csv
topic,priority,estimated_minutes,mastery
Practice topic: data interpretation,5,90,0.25
Practice topic: argument structure,4,60,0.55
```

Each topic name must be non-empty and unique. `priority` is an integer from 1 to 5, `estimated_minutes` is a positive whole number, and `mastery` is a finite number from 0 to 1 inclusive. The included `examples/topics.csv` contains synthetic examples only.

## Usage

```text
ib-study-planner plan topics.csv --exam-date YYYY-MM-DD --minutes-per-day N
```

Options:

- `--start-date YYYY-MM-DD`: first available date; defaults to the current local date.
- `--session-minutes N`: maximum length of an individual session; defaults to 25 minutes.
- `--output PATH`: write to a file instead of standard output.
- `--format markdown|json`: choose output format; Markdown is the default.

For example, from the project root:

```bash
ib-study-planner plan examples/topics.csv \
  --start-date 2026-11-01 --exam-date 2026-11-10 \
  --minutes-per-day 45 --session-minutes 25 --output plan.md
```

JSON output is suitable for downstream tools:

```bash
ib-study-planner plan examples/topics.csv \
  --start-date 2026-11-01 --exam-date 2026-11-10 \
  --minutes-per-day 45 --format json
```

## Scheduling guarantees

- Every requested study minute is allocated, or the command exits with an actionable error.
- The inclusive date range ends on the exam date; nothing is scheduled afterward.
- No day's planned total exceeds `--minutes-per-day`, and no individual block exceeds `--session-minutes`.
- Higher priority and lower mastery increase a topic's scheduling rank. Equal scores are resolved deterministically.
- The first scheduling pass limits each topic to one session per day, spreading work across days when possible. If that spacing constraint alone prevents full allocation, it is explicitly relaxed while retaining the daily cap, session size limit, and total requested minutes.
- Plans are deterministic for the same CSV and arguments. The default start date naturally changes with the calendar date; provide `--start-date` for reproducible output.

The planner does not account for weekdays, holidays, breaks, learning curves, or actual course scope. Review the output and adapt it to your schedule and exam needs.

## Development

Run the standard-library test suite from the project root:

```bash
python -m unittest discover -s tests -v
```

See [the algorithm notes](docs/algorithm.md), [contribution guide](CONTRIBUTING.md), and [security policy](SECURITY.md).
