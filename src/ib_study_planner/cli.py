"""Command-line interface for the offline study planner."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Sequence, TextIO

from .planner import PlannerError, StudyPlan, build_plan, read_topics


def _positive_cli_integer(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a whole number") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def _date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("must be a valid date in YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a valid date in YYYY-MM-DD format") from None


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_markdown(plan: StudyPlan) -> str:
    """Render a complete Markdown plan with capacity and guidance notes."""
    lines = [
        "# Study plan",
        "",
        f"**Date range:** {plan.start_date.isoformat()} through {plan.exam_date.isoformat()}  ",
        f"**Estimated study time:** {plan.total_requested_minutes} minutes  ",
        f"**Daily limit:** {plan.minutes_per_day} minutes  ",
        f"**Target session length:** up to {plan.session_minutes} minutes",
        "",
        "| Date | Planned study | Minutes |",
        "| --- | --- | ---: |",
    ]
    for day in plan.days:
        if day.sessions:
            work = "; ".join(f"{_markdown_cell(session.topic)} ({session.minutes} min)" for session in day.sessions)
            lines.append(f"| {day.day.isoformat()} | {work} | {day.total_minutes} |")
        else:
            lines.append(f"| {day.day.isoformat()} | Buffer / rest day | 0 |")
    lines.extend([
        "",
        "## Notes",
        "",
        "This is an offline planning aid, not official IB guidance. You supply the topic names and estimates; adjust priorities and time estimates to your actual course and exam requirements.",
    ])
    if plan.spacing_relaxed:
        lines.append("")
        lines.append("**Spacing note:** The requested workload could not fit while limiting each topic to one session per day. Spacing was relaxed where needed; the daily limit, session length limit, total workload, and exam-date boundary are still preserved.")
    lines.append("")
    return "\n".join(lines)


def render_json(plan: StudyPlan) -> str:
    """Render a stable, machine-readable plan."""
    payload = {
        "start_date": plan.start_date.isoformat(),
        "exam_date": plan.exam_date.isoformat(),
        "minutes_per_day": plan.minutes_per_day,
        "session_minutes": plan.session_minutes,
        "total_requested_minutes": plan.total_requested_minutes,
        "total_capacity_minutes": plan.total_capacity_minutes,
        "spacing_relaxed": plan.spacing_relaxed,
        "disclaimer": "Planning aid, not official IB guidance. Adjust priorities to actual course and exam requirements.",
        "days": [
            {
                "date": day.day.isoformat(),
                "total_minutes": day.total_minutes,
                "sessions": [{"topic": session.topic, "minutes": session.minutes} for session in day.sessions],
            }
            for day in plan.days
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ib-study-planner",
        description="Create an offline study plan from your own topic list (not official IB guidance).",
        epilog="Use topic names and estimates from your own course materials; adjust priorities to your actual exam requirements.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan", help="build a date-bounded plan from a CSV file")
    plan_parser.add_argument("topics_csv", metavar="topics.csv", help="CSV columns: topic,priority,estimated_minutes,mastery")
    plan_parser.add_argument("--exam-date", required=True, type=_date, metavar="YYYY-MM-DD", help="last permitted study date")
    plan_parser.add_argument("--minutes-per-day", required=True, type=_positive_cli_integer, metavar="N", help="maximum total study minutes per date")
    plan_parser.add_argument("--start-date", type=_date, default=date.today(), metavar="YYYY-MM-DD", help="first plan date (default: today)")
    plan_parser.add_argument("--session-minutes", type=_positive_cli_integer, default=25, metavar="25", help="maximum length of an individual session (default: 25)")
    plan_parser.add_argument("--output", metavar="PATH", help="write output to a file instead of standard output")
    plan_parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="output format (default: markdown)")
    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = create_parser()
    args = parser.parse_args(argv)
    if args.start_date > args.exam_date:
        parser.error("--start-date must be on or before --exam-date")
    try:
        topics = read_topics(args.topics_csv)
        plan = build_plan(
            topics,
            start_date=args.start_date,
            exam_date=args.exam_date,
            minutes_per_day=args.minutes_per_day,
            session_minutes=args.session_minutes,
        )
        rendered = render_json(plan) if args.format == "json" else render_markdown(plan)
        if args.output:
            try:
                Path(args.output).write_text(rendered, encoding="utf-8")
            except OSError as exc:
                raise PlannerError(f"Cannot write {args.output}: {exc}. Check the path and permissions.") from exc
        else:
            stdout.write(rendered)
        return 0
    except PlannerError as exc:
        print(f"ib-study-planner: error: {exc}", file=stderr)
        return 2
