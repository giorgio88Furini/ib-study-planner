# Scheduling algorithm

The planner uses only the user-provided topic records. It does not contain curricular topic lists or syllabus material.

## Ranking

Each topic receives a fixed weight:

```text
priority × (2 − mastery)
```

Priority ranges from 1 to 5 and mastery from 0 to 1. Thus a higher priority always raises the weight, and a lower mastery raises it as well. The formula uses both inputs without allowing a topic with full mastery to become unselectable. Equal weights are resolved first by the topic least recently scheduled, then by CSV order. These rules make a run deterministic.

## Feasibility

The date range is inclusive. If `D` dates remain and the daily cap is `C`, total available capacity is `D × C`. The sum of all `estimated_minutes` must not exceed that amount. This aggregate check occurs before scheduling and reports the capacity and remediation options on failure.

## Two passes

1. **Spacing-first pass:** Walk each date in order. On a given date, schedule at most one block for any topic. Each block is at most `session_minutes`, the topic's remaining estimate, and that date's remaining capacity. Ranking determines which topic is selected next. This naturally spreads a topic's work across dates when its estimates, session limit, available dates, and daily capacity permit it.
2. **Explicit spacing relaxation:** If any minutes remain after the first pass, revisit the dates with unused capacity and schedule additional blocks, still respecting the session size and daily limits. This can put a topic into multiple blocks on one date. The plan marks `spacing_relaxed` and Markdown output explains why.

The relaxation pass is needed, for example, when one topic requires more than one session per available day. It preserves all minutes rather than silently dropping work, exceeding the cap, or scheduling after the exam. Under the prior aggregate feasibility check, all remaining work fits in the total unused capacity.

## Output

The plan includes every date in the range, including rest/buffer days, with deterministic session order. Markdown is intended for people; JSON exposes dates, minutes, sessions, capacity, and the spacing-relaxation flag for other tools. Neither format is official academic guidance. Users should adapt the generated plan to their real course scope, exam requirements, and availability.
