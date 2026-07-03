# testgen — AGENTS.md

## Overview
Automated pytest test generator for Python source files. Uses AST analysis to extract functions, classes, methods, parameters, return types, and docstrings. Generates sensible test stubs with multiple strategies (basic call, return type, None-input, edge cases, docstring examples). MIT licensed.

## Quick Start
```bash
pip install -e ".[dev]"
testgen --help
```

## Commands
| Command | Description |
|---------|-------------|
| `testgen scan src/` | List testable units in source files |
| `testgen generate src/ -o tests/` | Generate test files |
| `testgen generate src/ --dry-run` | Preview generated tests |
| `testgen coverage-gaps src/` | Find untested functions |

## Development
```bash
# Install dev deps
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v --tb=short

# Lint
ruff check src/ --target-version py310

# Type check
mypy src/
```

## CI/CD
- GitHub Actions: `.github/workflows/ci.yml` (test matrix: 3.10, 3.11, 3.12, 3.13)
- Publish: `.github/workflows/publish.yml` (PyPI on tag)

## Structure
```
src/testgen/
├── __init__.py          # Package exports
├── __main__.py          # Module entry point
├── cli.py               # Typer CLI entry point
├── analyzer.py          # AST analysis (functions, classes, types)
├── generator.py         # Test code generation
├── diff_parser.py       # Diff parsing for incremental generation
└── py.typed             # PEP 561 marker
```

## Dependencies
- Core: typer, rich, astroid, pyyaml
- Dev: pytest, pytest-cov, ruff, mypy

## Testing
```bash
pytest tests/ -v --tb=short
pytest tests/test_cli.py -v
pytest tests/test_generator.py -v
pytest tests/test_analyzer.py -v
```

## Generated Test Types
For each function/method, testgen can generate up to 5 test strategies:
1. **Basic call test** (`test_X_runs`) — verifies the function can be called without error
2. **Return type test** (`test_X_return_type`) — checks return value matches annotated type
3. **None-input test** (`test_X_none_inputs`) — passes None for optional params
4. **Edge-case test** (`test_X_edge_cases`) — boundary values for numeric/string params
5. **Docstring test** (`test_X_docstring_example`) — placeholder for documented behavior

For classes, also generates **instantiation test** (`test_ClassName_instantiation`).

## Configuration
CLI options (see `testgen generate --help`):
- `--recursive/--no-recursive` (default: True)
- `--include-private` (include _private members)
- `--include-dunder` (include __dunder__ methods)
- `--max-tests INT` (default: 6 per function)
- `--edge-cases/--no-edge-cases` (default: True)
- `--none-checks/--no-none-checks` (default: True)
- `--type-validation/--no-type-validation` (default: True)
- `--docstring-tests/--no-docstring-tests` (default: True)
- `-o, --output PATH` (output directory)
- `--overwrite` (overwrite existing test files)
- `--dry-run` (print without writing)

## License
MIT