from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import date
from pathlib import Path

from ib_study_planner.cli import main, render_json, render_markdown
from ib_study_planner.planner import PlannerError, Topic, build_plan, read_topics


class ReadTopicsTests(unittest.TestCase):
    def test_reads_valid_csv_and_trims_values(self) -> None:
        topics = read_topics(io.StringIO("topic,priority,estimated_minutes,mastery\n Alpha ,5,30,0.25\n"))
        self.assertEqual(topics, [Topic("Alpha", 5, 30, 0.25)])

    def test_rejects_wrong_or_reordered_headers(self) -> None:
        for header in ("topic,priority,mastery,estimated_minutes", "topic,priority,estimated_minutes"):
            with self.subTest(header=header), self.assertRaisesRegex(PlannerError, "expected columns"):
                read_topics(io.StringIO(header + "\n"))

    def test_rejects_bad_priority_estimate_and_mastery(self) -> None:
        for row, expected in (
            ("Topic,0,10,0.5", "priority must be a positive"),
            ("Topic,6,10,0.5", "priority must be between 1 and 5"),
            ("Topic,3,0,0.5", "estimated_minutes must be a positive"),
            ("Topic,3,10,1.1", "mastery must be between 0 and 1"),
            ("Topic,3,10,nan", "mastery must be between 0 and 1"),
            ("Topic,3,10,nope", "mastery must be a number"),
        ):
            with self.subTest(row=row), self.assertRaisesRegex(PlannerError, expected):
                read_topics(io.StringIO("topic,priority,estimated_minutes,mastery\n" + row + "\n"))

    def test_rejects_duplicate_empty_incomplete_and_extra_rows(self) -> None:
        header = "topic,priority,estimated_minutes,mastery\n"
        cases = (
            (header + "X,2,5,0.5\nX,1,5,0.2\n", "duplicate topic"),
            (header + ",2,5,0.5\n", "topic cannot be empty"),
            (header + "X,2,5\n", "incomplete row"),
            (header + "X,2,5,0.5,extra\n", "too many fields"),
            (header, "no topic rows"),
        )
        for text, expected in cases:
            with self.subTest(text=text), self.assertRaisesRegex(PlannerError, expected):
                read_topics(io.StringIO(text))

    def test_reads_bom_csv_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "topics.csv"
            path.write_text("\ufefftopic,priority,estimated_minutes,mastery\nA,1,1,0\n", encoding="utf-8")
            self.assertEqual(read_topics(path)[0].name, "A")

    def test_missing_file_has_actionable_error(self) -> None:
        with self.assertRaisesRegex(PlannerError, "Check the path"):
            read_topics("missing-topics.csv")


class BuildPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = date(2026, 1, 1)

    def make_plan(self, topics: list[Topic], days: int, per_day: int, session: int = 25):
        return build_plan(
            topics,
            start_date=self.start,
            exam_date=date(2026, 1, days),
            minutes_per_day=per_day,
            session_minutes=session,
        )

    def test_allocates_every_minute_respects_caps_and_stops_on_exam(self) -> None:
        plan = self.make_plan([Topic("A", 5, 31, 0.1), Topic("B", 2, 19, 0.8)], 3, 20, 15)
        self.assertEqual(sum(day.total_minutes for day in plan.days), 50)
        self.assertEqual(plan.total_requested_minutes, 50)
        self.assertEqual([day.day for day in plan.days], [date(2026, 1, d) for d in (1, 2, 3)])
        self.assertTrue(all(day.total_minutes <= 20 for day in plan.days))
        self.assertTrue(all(session.minutes <= 15 for day in plan.days for session in day.sessions))
        self.assertTrue(all(session.minutes > 0 for day in plan.days for session in day.sessions))

    def test_high_priority_and_low_mastery_rank_first(self) -> None:
        plan = self.make_plan([Topic("Low rank", 1, 5, 1.0), Topic("High rank", 5, 5, 0.0)], 1, 10, 5)
        self.assertEqual(plan.days[0].sessions[0].topic, "High rank")

    def test_spreads_topic_when_possible_without_relaxation(self) -> None:
        plan = self.make_plan([Topic("A", 5, 50, 0.2), Topic("B", 4, 50, 0.4)], 4, 25, 25)
        self.assertFalse(plan.spacing_relaxed)
        dates_for_a = [day.day for day in plan.days if any(s.topic == "A" for s in day.sessions)]
        self.assertEqual(len(dates_for_a), 2)
        self.assertEqual(len(set(dates_for_a)), 2)

    def test_relaxes_spacing_when_needed_but_preserves_total_and_daily_cap(self) -> None:
        plan = self.make_plan([Topic("A", 5, 60, 0.1)], 2, 30, 10)
        self.assertTrue(plan.spacing_relaxed)
        self.assertEqual(sum(day.total_minutes for day in plan.days), 60)
        self.assertTrue(all(day.total_minutes <= 30 for day in plan.days))
        self.assertTrue(any(sum(s.topic == "A" for s in day.sessions) > 1 for day in plan.days))

    def test_rejects_impossible_workload_with_capacity_details(self) -> None:
        with self.assertRaisesRegex(PlannerError, "60 study minutes.*only 50 minutes"):
            self.make_plan([Topic("A", 1, 60, 0.5)], 2, 25)

    def test_rejects_invalid_date_and_limits(self) -> None:
        with self.assertRaisesRegex(PlannerError, "Start date"):
            build_plan([Topic("A", 1, 1, 0)], start_date=date(2026, 1, 2), exam_date=date(2026, 1, 1), minutes_per_day=1)
        with self.assertRaisesRegex(PlannerError, "minutes-per-day"):
            self.make_plan([Topic("A", 1, 1, 0)], 1, 0)
        with self.assertRaisesRegex(PlannerError, "session-minutes"):
            self.make_plan([Topic("A", 1, 1, 0)], 1, 1, 0)

    def test_deterministic_output(self) -> None:
        topics = [Topic("A", 3, 15, 0.3), Topic("B", 3, 15, 0.3)]
        first = self.make_plan(topics, 2, 20)
        second = self.make_plan(topics, 2, 20)
        self.assertEqual(first, second)


class CliTests(unittest.TestCase):
    def test_cli_markdown_smoke_and_disclaimer(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        code = main([
            "plan", "examples/topics.csv", "--start-date", "2026-05-01", "--exam-date", "2026-05-10",
            "--minutes-per-day", "45", "--session-minutes", "25",
        ], stdout=stdout, stderr=stderr)
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertIn("# Study plan", stdout.getvalue())
        self.assertIn("not official IB guidance", stdout.getvalue())
        self.assertIn("2026-05-10", stdout.getvalue())

    def test_cli_json_and_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan.json"
            code = main([
                "plan", "examples/topics.csv", "--start-date", "2026-05-01", "--exam-date", "2026-05-10",
                "--minutes-per-day", "45", "--format", "json", "--output", str(output),
            ], stdout=io.StringIO(), stderr=io.StringIO())
            self.assertEqual(code, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["exam_date"], "2026-05-10")
            self.assertIn("days", payload)

    def test_cli_invalid_argument_and_workload_return_error(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
            main(["plan", "examples/topics.csv", "--exam-date", "not-a-date", "--minutes-per-day", "10"], stderr=stderr)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("YYYY-MM-DD", stderr.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.csv"
            path.write_text("topic,priority,estimated_minutes,mastery\nA,5,1000,0.1\n", encoding="utf-8")
            stderr = io.StringIO()
            code = main(["plan", str(path), "--start-date", "2026-01-01", "--exam-date", "2026-01-02", "--minutes-per-day", "20"], stderr=stderr)
            self.assertEqual(code, 2)
            self.assertIn("Impossible workload", stderr.getvalue())

    def test_markdown_escapes_topic_pipe(self) -> None:
        plan = build_plan([Topic("A | B", 1, 5, 1)], start_date=date(2026, 1, 1), exam_date=date(2026, 1, 1), minutes_per_day=5)
        self.assertIn("A \\| B", render_markdown(plan))
        self.assertIn("Planning aid", render_json(plan))


if __name__ == "__main__":
    unittest.main()
