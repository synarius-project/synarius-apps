# Contributing to Synarius Apps

Thank you for your interest in contributing!

**Canonical, cross-repository conventions** (Python version, repo boundaries, style, tests, PRs) are documented in the **[Synarius programming guidelines](https://synarius-project.github.io/synarius-guidelines/programming_guidelines.html)** (Sphinx site — same content as the [synarius-guidelines](https://github.com/synarius-project/synarius-guidelines) repository).

## This repository

- **synarius-apps** provides the DataViewer, ParaWiz, and shared Qt tooling (`synariustools`). It depends on **synarius-core** and does **not** require Synarius Studio.
- Keep measurement / file I/O logic in **synarius-core** where appropriate; UI and app wiring belong here.

## Getting started

1. Fork the repository and create a feature branch.
2. Install in development mode (see [README.md](README.md) — local editable **synarius-core** is often required).
3. Run tests (e.g. `pytest`) before opening a PR.
4. Ensure CI passes.

## Legal

See [CLA.md](CLA.md) in this repository for the Contributor License Agreement.
