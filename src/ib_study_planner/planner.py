"""Validation and deterministic scheduling for user-supplied study topics."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, TextIO


class PlannerError(ValueError):
    """An actionable input or workload error raised by the planner."""


@dataclass(frozen=True)
class Topic:
    name: str
    priority: int
    estimated_minutes: int
    mastery: float

    @property
    def rank_score(self) -> float:
        """Higher priority and lower mastery both increase scheduling weight."""
        return self.priority * (2.0 - self.mastery)


@dataclass(frozen=True)
class Session:
    topic: str
    minutes: int


@dataclass(frozen=True)
class DayPlan:
    day: date
    sessions: tuple[Session, ...]

    @property
    def total_minutes(self) -> int:
        return sum(session.minutes for session in self.sessions)


@dataclass(frozen=True)
class StudyPlan:
    start_date: date
    exam_date: date
    minutes_per_day: int
    session_minutes: int
    total_requested_minutes: int
    days: tuple[DayPlan, ...]
    spacing_relaxed: bool

    @property
    def total_capacity_minutes(self) -> int:
        return len(self.days) * self.minutes_per_day


def _positive_integer(value: str, field: str, row_number: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise PlannerError(f"CSV row {row_number}: {field} must be a whole number; got {value!r}.") from None
    if str(parsed) != value.strip() or parsed <= 0:
        raise PlannerError(f"CSV row {row_number}: {field} must be a positive whole number; got {value!r}.")
    return parsed


def read_topics(source: str | Path | TextIO) -> list[Topic]:
    """Read and validate a CSV with exactly the required topic columns."""
    close_after = False
    if hasattr(source, "read"):
        handle = source  # type: ignore[assignment]
        label = getattr(handle, "name", "CSV input")
    else:
        label = str(source)
        try:
            handle = open(source, "r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise PlannerError(f"Cannot read {label}: {exc}. Check the path and permissions.") from exc
        close_after = True

    try:
        reader = csv.DictReader(handle, strict=True)
        required = ["topic", "priority", "estimated_minutes", "mastery"]
        headers = reader.fieldnames
        if headers is None:
            raise PlannerError(f"{label}: CSV is empty; include the header: {','.join(required)}.")
        normalized = [header.strip() if header else "" for header in headers]
        if normalized != required:
            raise PlannerError(
                f"{label}: expected columns in this order: {','.join(required)}; found: {','.join(normalized)}."
            )
        reader.fieldnames = required

        topics: list[Topic] = []
        names: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise PlannerError(f"CSV row {row_number}: too many fields; expected four columns.")
            if all(value is None or not value.strip() for value in row.values()):
                continue
            if any(value is None for value in row.values()):
                raise PlannerError(f"CSV row {row_number}: incomplete row; provide all four columns.")
            name = row["topic"].strip()
            if not name:
                raise PlannerError(f"CSV row {row_number}: topic cannot be empty.")
            if name in names:
                raise PlannerError(f"CSV row {row_number}: duplicate topic {name!r}; use unique topic names.")
            priority = _positive_integer(row["priority"].strip(), "priority", row_number)
            if priority > 5:
                raise PlannerError(f"CSV row {row_number}: priority must be between 1 and 5; got {priority}.")
            minutes = _positive_integer(row["estimated_minutes"].strip(), "estimated_minutes", row_number)
            mastery_text = row["mastery"].strip()
            try:
                mastery = float(mastery_text)
            except ValueError:
                raise PlannerError(f"CSV row {row_number}: mastery must be a number between 0 and 1; got {mastery_text!r}.") from None
            if not math.isfinite(mastery) or not 0.0 <= mastery <= 1.0:
                raise PlannerError(f"CSV row {row_number}: mastery must be between 0 and 1 inclusive; got {mastery_text!r}.")
            names.add(name)
            topics.append(Topic(name, priority, minutes, mastery))
        if not topics:
            raise PlannerError(f"{label}: no topic rows found; add at least one topic.")
        return topics
    except csv.Error as exc:
        raise PlannerError(f"{label}: malformed CSV: {exc}.") from exc
    finally:
        if close_after:
            handle.close()


def build_plan(
    topics: Iterable[Topic],
    *,
    start_date: date,
    exam_date: date,
    minutes_per_day: int,
    session_minutes: int = 25,
) -> StudyPlan:
    """Allocate every estimated minute on or before the exam, respecting daily capacity."""
    topic_list = list(topics)
    if not topic_list:
        raise PlannerError("At least one topic is required.")
    if start_date > exam_date:
        raise PlannerError("Start date must be on or before the exam date.")
    if minutes_per_day <= 0:
        raise PlannerError("minutes-per-day must be a positive integer.")
    if session_minutes <= 0:
        raise PlannerError("session-minutes must be a positive integer.")

    days_count = (exam_date - start_date).days + 1
    requested = sum(topic.estimated_minutes for topic in topic_list)
    capacity = days_count * minutes_per_day
    if requested > capacity:
        raise PlannerError(
            f"Impossible workload: {requested} study minutes requested, but only {capacity} minutes are available "
            f"from {start_date.isoformat()} through {exam_date.isoformat()} ({days_count} days × "
            f"{minutes_per_day} minutes/day). Increase the date range or daily capacity, or reduce estimates."
        )

    dates = [start_date + timedelta(days=offset) for offset in range(days_count)]
    remaining = {topic.name: topic.estimated_minutes for topic in topic_list}
    original_order = {topic.name: index for index, topic in enumerate(topic_list)}
    assignments: dict[date, list[Session]] = {day: [] for day in dates}
    last_scheduled: dict[str, date | None] = {topic.name: None for topic in topic_list}

    def ranked_candidates(exclude: set[str] | None = None) -> list[Topic]:
        excluded = exclude or set()
        return sorted(
            (topic for topic in topic_list if remaining[topic.name] > 0 and topic.name not in excluded),
            key=lambda topic: (
                -topic.rank_score,
                last_scheduled[topic.name] or date.min,
                original_order[topic.name],
            ),
        )

    # Spacing-first pass: schedule at most one session per topic per day.
    for day in dates:
        capacity_left = minutes_per_day
        scheduled_today: set[str] = set()
        while capacity_left > 0:
            candidates = ranked_candidates(scheduled_today)
            if not candidates:
                break
            topic = candidates[0]
            amount = min(session_minutes, remaining[topic.name], capacity_left)
            assignments[day].append(Session(topic.name, amount))
            remaining[topic.name] -= amount
            capacity_left -= amount
            scheduled_today.add(topic.name)
            last_scheduled[topic.name] = day

    spacing_relaxed = any(value > 0 for value in remaining.values())
    # Relax only when the spacing-first pass cannot fit the workload. Keep every
    # block at or below session_minutes and never exceed the daily cap.
    if spacing_relaxed:
        for day in dates:
            capacity_left = minutes_per_day - sum(item.minutes for item in assignments[day])
            while capacity_left > 0:
                candidates = ranked_candidates()
                if not candidates:
                    break
                topic = candidates[0]
                amount = min(session_minutes, remaining[topic.name], capacity_left)
                assignments[day].append(Session(topic.name, amount))
                remaining[topic.name] -= amount
                capacity_left -= amount
                last_scheduled[topic.name] = day

    if any(value for value in remaining.values()):
        raise PlannerError("Unable to allocate the workload within the daily limits; reduce estimates or extend the dates.")

    day_plans = tuple(DayPlan(day, tuple(assignments[day])) for day in dates)
    return StudyPlan(start_date, exam_date, minutes_per_day, session_minutes, requested, day_plans, spacing_relaxed)
