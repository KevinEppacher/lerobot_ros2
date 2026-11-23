# General Development Guidelines

## Standards

- Follow the Google C++ Style Guide for C++.
- Follow PEP 8 for Python.
- Prefer established language and framework conventions over custom patterns.
- Follow existing repository conventions when they do not conflict with these guidelines.

## Code Quality

- Prefer simple, readable, and maintainable code.
- Minimize code and unnecessary abstractions.
- Follow DRY, KISS, and SOLID principles where applicable.
- Keep functions and classes focused on a single responsibility.
- Prefer standard libraries and existing dependencies over new dependencies.
- Avoid premature optimization and speculative functionality.
- Use descriptive names and explicit interfaces.
- Handle errors explicitly and provide meaningful diagnostics.

## Formatting

- Use English for code, comments, documentation, and commit messages.
- Follow the repository's configured formatters and linters.
- Avoid comments that merely repeat what the code already expresses.
- Document non-obvious behavior, assumptions, and design decisions.

## Changes

- Make the smallest reasonable change.
- Avoid unrelated refactoring.
- Preserve backward compatibility unless explicitly instructed otherwise.
- Update relevant tests and documentation when behavior changes.
- Do not introduce dependencies without justification.

## Testing

- Prefer automated, deterministic tests.
- Test observable behavior rather than implementation details.
- Use existing testing frameworks and conventions.
- Report tests that could not be executed.
