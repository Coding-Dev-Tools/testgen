# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-30

### Added
- Automated test generator — scans Python source files and generates pytest stubs
- AST-based analyzer extracts testable units (functions, classes, methods)
- Support for type annotations, default values, and parameter kinds
- Multiple test types: basic call, return type, None inputs, edge cases, docstring, Hypothesis
- `generate` command with `--dry-run`, `--diff`, `--recursive`, `--overwrite` options
- `scan` command to display testable units
- `coverage-gaps` command to find untested functions/classes
- Configurable fixture style (function, class, both)
- CI and PyPI publish workflows