# testgen — Automated Test Generator

Automatically generates pytest test stubs for Python source files.

## Features

- **AST-based analysis**: Parses Python source files to extract functions, classes, methods, parameters, return types, and docstrings
- **Smart defaults**: Generates sensible test values based on type annotations and parameter names
- **Multiple test strategies**: Basic call, return type, None-input, edge-case, and docstring-based tests
- **Coverage gap detection**: Identifies functions/methods missing test coverage
- **CLI & programmatic**: Use as a CLI tool or Python library

## Installation

```bash
pip install testgen-cli
```

## Quick Start

```bash
# Scan a project for testable units
testgen scan src/

# Generate test stubs (dry run)
testgen generate src/ --dry-run

# Generate and write test files
testgen generate src/ -o tests/

# Find coverage gaps
testgen coverage-gaps src/
```

## CLI Commands

### `testgen generate`

Generate pytest test stubs for Python source files.

```bash
testgen generate <target> [options]

Options:
  --recursive/--no-recursive   Recursively scan directories (default: True)
  --include-private            Include private members
  --include-dunder             Include __dunder__ methods
  --max-tests INT              Max tests per function (default: 6)
  --edge-cases/--no-edge-cases  Generate edge-case tests (default: True)
  --none-checks/--no-none-checks  Generate None-input tests (default: True)
  --type-validation/--no-type-validation  Generate return-type tests (default: True)
  --docstring-tests/--no-docstring-tests  Generate docstring-based tests (default: True)
  -o, --output PATH            Output directory for test files
  --overwrite                  Overwrite existing test files
  --dry-run                    Print generated tests without writing
```

### `testgen scan`

Scan and display testable units found in Python files.

```bash
testgen scan <target> [options]
```

### `testgen coverage-gaps`

Find functions/classes with missing test coverage.

```bash
testgen coverage-gaps <target> [options]
```

## Programmatic Usage

```python
from pathlib import Path
from testgen.analyzer import analyze_file
from testgen.generator import generate_test

# Analyze a source file
module = analyze_file(Path("src/myapp/service.py"))

# Generate test code
test_code = generate_test(module)
print(test_code)

# Or with custom config
from testgen.generator import GeneratorConfig, PytestStubGenerator

config = GeneratorConfig(
    max_tests_per_func=3,
    include_edge_cases=False,
    include_none_checks=True,
)
generator = PytestStubGenerator(config)
code = generator.generate(module)
```

## Generated Test Types

For each function/method, testgen can generate up to 5 test strategies:

1. **Basic call test** (`test_X_runs`) — verifies the function can be called without error
2. **Return type test** (`test_X_return_type`) — checks the return value matches the annotated type
3. **None-input test** (`test_X_none_inputs`) — passes None for optional params to check graceful handling
4. **Edge-case test** (`test_X_edge_cases`) — uses boundary values for numeric/string params
5. **Docstring test** (`test_X_docstring_example`) — placeholder for behavior documented in docstrings

For classes, it also generates an **instantiation test** (`test_ClassName_instantiation`).

## License

MIT
