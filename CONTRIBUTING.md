# Contributing

Contributions are welcome for correctness, accessibility, documentation, and maintainability.

## Development checks

- Use Python 3.10-compatible syntax and standard-library runtime code.
- Run `python -m unittest discover -s tests -v` from the project root before submitting a change.
- Add or update tests for observable behavior, especially capacity, date boundaries, malformed input, and deterministic output.
- Keep CLI errors actionable and avoid writing files unless a user explicitly supplies `--output`.

## Content and privacy

This project is deliberately content-neutral. Do not add official/copyrighted IB syllabus text, extracted topic lists, or claims that the planner represents official guidance. Examples must be synthetic. CSV topic names are user data and are processed locally; do not add telemetry, network calls, or external services.

## Changes

Keep changes focused and document user-visible behavior in the README or algorithm notes. Do not claim test, compatibility, or security results that have not been verified.
