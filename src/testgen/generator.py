"""Test code generator — produces pytest test stubs from ModuleInfo."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .analyzer import ClassInfo, FuncInfo, ModuleInfo, ParamInfo

# ── Type → default value mapping ──────────────────────────────────────────────

TYPE_DEFAULTS: dict[str, str] = {
    "int": "0",
    "float": "0.0",
    "str": '""',
    "bool": "False",
    "list": "[]",
    "dict": "{}",
    "set": "set()",
    "tuple": "()",
    "bytes": 'b""',
    "None": "None",
    "Path": "Path('.')",
    "Any": "None",
}

TYPE_IMPORTS: dict[str, str] = {
    "Path": "pathlib",
    "Any": "typing",
    "Optional": "typing",
    "Union": "typing",
    "List": "typing",
    "Dict": "typing",
    "Set": "typing",
    "Tuple": "typing",
}

SIMPLE_TYPE_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9]*$")

# ── Hypothesis strategy mapping ───────────────────────────────────────────────

HYPOTHESIS_STRATEGIES: dict[str, str] = {
    "int": "st.integers()",
    "float": "st.floats(allow_nan=False, allow_infinity=False)",
    "str": "st.text()",
    "bool": "st.booleans()",
    "list": "st.lists(st.none())",
    "dict": "st.dictionaries(st.text(), st.none())",
    "bytes": "st.binary()",
}


@dataclass
class GeneratorConfig:
    """Configuration for test generation."""

    fixture_style: str = "function"  # function, class, or both
    include_docstring_tests: bool = True
    include_edge_cases: bool = True
    include_type_validation: bool = True
    include_none_checks: bool = True
    include_hypothesis: bool = False
    max_tests_per_func: int = 6
    overwrite: bool = False
    header_comment: bool = True


class PytestStubGenerator:
    """Generates pytest test stubs from module analysis."""

    def __init__(self, config: GeneratorConfig | None = None):
        self.config = config or GeneratorConfig()
        self._needed_imports: set[str] = set()
        self._needed_from_imports: dict[str, set[str]] = {}
        self._fixtures: list[str] = []  # collected fixture definitions

    def generate(self, module: ModuleInfo) -> str:
        """Generate a complete test file for a module."""
        self._needed_imports = set()
        self._needed_from_imports = {}
        self._fixtures = []

        lines: list[str] = []

        # Header
        if self.config.header_comment:
            lines.append(f'"""Auto-generated tests for {module.module_name}."""')
            lines.append("")

        # Standard imports
        self._needed_imports.add("pytest")

        # Source import
        self._add_from_import(module.module_name, "*")

        # Generate test functions/classes
        test_items: list[str] = []

        for func in module.functions:
            test_items.extend(self._generate_function_tests(func, module))

        for cls in module.classes:
            test_items.extend(self._generate_class_tests(cls, module))

        if not test_items and not self._fixtures:
            lines.append("# No testable units found")
            return "\n".join(lines)

        # Assemble imports section
        import_lines = self._assemble_imports(module)
        lines.extend(import_lines)
        lines.append("")
        lines.append("")

        # Add fixtures (if using class fixture style)
        if self._fixtures and self.config.fixture_style in ("class", "both"):
            lines.extend("\n\n".join(self._fixtures).split("\n"))
            lines.append("")
            lines.append("")

        # Add test items
        lines.extend("\n\n".join(test_items).split("\n"))
        lines.append("")  # trailing newline

        return "\n".join(lines)

    def _add_from_import(self, module: str, name: str) -> None:
        """Track a 'from X import Y' requirement."""
        if module not in self._needed_from_imports:
            self._needed_from_imports[module] = set()
        self._needed_from_imports[module].add(name)

    def _assemble_imports(self, module: ModuleInfo) -> list[str]:
        """Build the import section of the test file."""
        lines: list[str] = []

        # Standard library
        for imp in sorted(self._needed_imports):
            lines.append(f"import {imp}")

        # from imports
        for mod, names in sorted(self._needed_from_imports.items()):
            name_str = ", ".join(sorted(names))
            lines.append(f"from {mod} import {name_str}")

        return lines

    def _generate_function_tests(self, func: FuncInfo, module: ModuleInfo) -> list[str]:
        """Generate test cases for a standalone function."""
        tests: list[str] = []
        test_count = 0

        func_label = func.name
        if func.parent_class:
            func_label = f"{func.parent_class}_{func.name}"

        # 1. Basic call test — does it run without error?
        if test_count < self.config.max_tests_per_func:
            tests.append(self._gen_basic_call_test(func, func_label, module))
            test_count += 1

        # 2. Return type test
        if func.return_annotation and self.config.include_type_validation and test_count < self.config.max_tests_per_func:
            tests.append(self._gen_return_type_test(func, func_label, module))
            test_count += 1

        # 3. None/empty input test
        if self.config.include_none_checks and self._has_optional_params(func) and test_count < self.config.max_tests_per_func:
            tests.append(self._gen_none_input_test(func, func_label, module))
            test_count += 1

        # 4. Edge case test
        if self.config.include_edge_cases and test_count < self.config.max_tests_per_func:
            tests.append(self._gen_edge_case_test(func, func_label, module))
            test_count += 1

        # 5. Docstring-based test
        if func.docstring and self.config.include_docstring_tests and test_count < self.config.max_tests_per_func:
            tests.append(self._gen_docstring_test(func, func_label, module))
            test_count += 1

        # 6. Hypothesis property-based test
        if self.config.include_hypothesis and self._has_hypothesis_params(func) and test_count < self.config.max_tests_per_func:
            tests.append(self._gen_hypothesis_test(func, func_label, module))
            test_count += 1

        return tests

    def _generate_class_tests(self, cls: ClassInfo, module: ModuleInfo) -> list[str]:
        """Generate test cases for a class and its methods."""
        tests: list[str] = []

        # Class instantiation test (or fixture if class fixture style)
        if not cls.is_abstract:
            if self.config.fixture_style in ("class", "both"):
                self._gen_class_fixture(cls, module)
                if self.config.fixture_style == "both":
                    tests.append(self._gen_class_instantiation_test(cls, module))
            else:
                tests.append(self._gen_class_instantiation_test(cls, module))

        # Method tests
        for method in cls.methods:
            if method.is_abstract:
                continue
            method_tests = self._generate_function_tests(method, module)
            tests.extend(method_tests)

        return tests

    # ── Fixture generation ─────────────────────────────────────────────────────

    def _gen_class_fixture(self, cls: ClassInfo, module: ModuleInfo) -> None:
        """Generate a @pytest.fixture for a class and register it."""
        fixture_name = cls.name.lower()
        init_args = self._build_init_args(cls)

        lines = [
            "@pytest.fixture",
            f"def {fixture_name}():",
            f'    """Fixture providing a {cls.name} instance."""',
            f"    return {cls.name}({init_args})",
        ]
        self._fixtures.append("\n".join(lines))

    # ── Hypothesis test generation ─────────────────────────────────────────────

    def _has_hypothesis_params(self, func: FuncInfo) -> bool:
        """Check if a function has params that can benefit from Hypothesis."""
        return any(
            p.annotation in HYPOTHESIS_STRATEGIES
            for p in func.params
            if p.name not in ("self", "cls")
        )

    def _gen_hypothesis_test(self, func: FuncInfo, label: str, module: ModuleInfo) -> str:
        """Generate a Hypothesis property-based test stub."""
        self._add_from_import("hypothesis", "given")
        self._add_from_import("hypothesis.strategies", "st")

        test_name = f"test_{label}_property_based"

        # Build @given decorators
        given_parts: list[str] = []
        param_strs: list[str] = []
        for p in func.params:
            if p.name in ("self", "cls"):
                continue
            if p.is_var_positional or p.is_var_keyword:
                continue
            strategy = HYPOTHESIS_STRATEGIES.get(p.annotation or "", "st.none()")
            given_parts.append(strategy)
            param_strs.append(p.name)

        given_decorator = ", ".join(given_parts)
        given_line = f"@given({given_decorator})"
        param_line = ", ".join(param_strs)

        call_expr = self._build_call_expr(func, param_line)

        ret_assert = ""
        if func.return_annotation:
            ret = func.return_annotation
            stripped = ret.replace(" | None", "")
            if stripped.startswith("Optional[") and stripped.endswith("]"):
                stripped = stripped[len("Optional["):-1]
            if stripped not in ("None", "Any"):
                base_type = stripped.split("[")[0] if "[" in stripped else stripped
                if base_type in ("dict", "list", "set", "tuple", "frozenset", "str", "int", "float", "bool", "bytes"):
                    ret_assert = f"    assert isinstance(result, {base_type})"

        lines = [
            given_line,
            f"def {test_name}({param_line}):",
            f'    """Property-based test for {func.name}."""',
            f"    result = {call_expr}",
        ]
        if ret_assert:
            lines.append(ret_assert)
        else:
            lines.append("    # TODO: add property assertions")

        return "\n".join(lines)

    # ── Existing test generators (unchanged logic) ────────────────────────────

    def _gen_basic_call_test(self, func: FuncInfo, label: str, module: ModuleInfo) -> str:
        """Generate a test that calls the function with default args."""
        test_name = f"test_{label}_runs"
        args_str = self._build_call_args(func)
        call_expr = self._build_call_expr(func, args_str)

        doc_comment = f" # {func.docstring.split(chr(10))[0].strip()}" if func.docstring else ""

        lines = [
            f"def {test_name}():",
            f'    """Test that {func.name} runs without error."""',
            doc_comment,
            f"    result = {call_expr}",
            "    # TODO: assert specific behavior",
        ]
        return "\n".join(line for line in lines if line.strip())

    def _gen_return_type_test(self, func: FuncInfo, label: str, module: ModuleInfo) -> str:
        """Generate a test that checks the return type."""
        ret = func.return_annotation
        if not ret:
            return ""

        test_name = f"test_{label}_return_type"
        args_str = self._build_call_args(func)
        call_expr = self._build_call_expr(func, args_str)

        # Handle Union/Optional return types
        stripped = ret.replace(" | None", "")
        if stripped.startswith("Optional[") and stripped.endswith("]"):
            stripped = stripped[len("Optional["):-1]
        check_type = stripped
        if check_type in ("None", "Any"):
            return ""

        # For generic types like dict[str, Any], use the base type for isinstance
        base_type = check_type.split("[")[0] if "[" in check_type else check_type
        if base_type in ("dict", "list", "set", "tuple", "frozenset", "str", "int", "float", "bool", "bytes"):
            type_check = f"isinstance(result, {base_type})"
        else:
            type_check = f"isinstance(result, {check_type})"

        if "None" in ret or "Optional" in ret:
            type_check = f"result is None or {type_check}"

        # Add type imports if needed
        if base_type in TYPE_IMPORTS:
            self._add_from_import(TYPE_IMPORTS[base_type], base_type)

        lines = [
            f"def {test_name}():",
            f'    """Test that {func.name} returns {ret}."""',
            f"    result = {call_expr}",
            f"    assert {type_check}",
        ]
        return "\n".join(lines)

    def _gen_none_input_test(self, func: FuncInfo, label: str, module: ModuleInfo) -> str:
        """Generate a test that passes None for optional params."""
        test_name = f"test_{label}_none_inputs"
        args_str = self._build_call_args_optional_only(func)
        call_expr = self._build_call_expr(func, args_str)

        lines = [
            f"def {test_name}():",
            f'    """Test {func.name} with None for optional params — should not crash."""',
            f"    result = {call_expr}",
            "    # Should handle None gracefully or raise a clear error",
        ]
        return "\n".join(lines)

    def _gen_edge_case_test(self, func: FuncInfo, label: str, module: ModuleInfo) -> str:
        """Generate a test with edge-case inputs."""
        test_name = f"test_{label}_edge_cases"
        edge_args = self._build_edge_case_args(func)
        call_expr = self._build_call_expr(func, edge_args)

        lines = [
            f"def {test_name}():",
            f'    """Test {func.name} with edge-case inputs."""',
            f"    result = {call_expr}",
            "    # TODO: verify edge-case handling",
        ]
        return "\n".join(lines)

    def _gen_docstring_test(self, func: FuncInfo, label: str, module: ModuleInfo) -> str:
        """Generate a test based on docstring examples."""
        test_name = f"test_{label}_docstring_example"
        doc_first_line = func.docstring.split("\n")[0].strip() if func.docstring else ""

        lines = [
            f"def {test_name}():",
            f'    """Test {func.name} — verify docstring behavior."""',
            f"    # Docstring: {doc_first_line}",
            "    # TODO: implement test based on documented behavior",
        ]
        return "\n".join(lines)

    def _gen_class_instantiation_test(self, cls: ClassInfo, module: ModuleInfo) -> str:
        """Generate a test that instantiates a class."""
        test_name = f"test_{cls.name}_instantiation"
        init_args = self._build_init_args(cls)

        # Check for required params in __init__
        init_method = next((m for m in cls.methods if m.name == "__init__"), None)

        lines = [
            f"def {test_name}():",
            f'    """Test that {cls.name} can be instantiated."""',
        ]

        if init_method:
            required = [p for p in init_method.params if p.name != "self" and p.default is None and not p.is_var_keyword]
            if required:
                lines.append(f"    # Requires: {', '.join(p.name for p in required)}")

        lines.append(f"    instance = {cls.name}({init_args})")
        lines.append("    assert instance is not None")

        return "\n".join(lines)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _build_call_expr(self, func: FuncInfo, args_str: str) -> str:
        """Build a function call expression string."""
        if func.parent_class and func.kind == "method":
            # If using fixture style, use fixture name instead of Class(...)
            if self.config.fixture_style in ("class", "both"):
                fixture_name = func.parent_class.lower()
                return f"{fixture_name}.{func.name}({args_str})"
            return f"{func.parent_class}(...).{func.name}({args_str})"
        elif func.parent_class and func.kind in ("classmethod", "staticmethod"):
            return f"{func.parent_class}.{func.name}({args_str})"
        else:
            return f"{func.name}({args_str})"

    def _build_call_args(self, func: FuncInfo) -> str:
        """Build a comma-separated string of argument values for a function call."""
        args: list[str] = []
        for p in func.params:
            if p.name == "self" or p.name == "cls":
                continue
            if p.is_var_positional or p.is_var_keyword:
                continue
            args.append(self._param_value(p))
        return ", ".join(args)

    def _build_call_args_optional_only(self, func: FuncInfo) -> str:
        """Build args where optional params get None."""
        args: list[str] = []
        for p in func.params:
            if p.name == "self" or p.name == "cls":
                continue
            if p.is_var_positional or p.is_var_keyword:
                continue
            if p.default is not None:
                args.append(f"{p.name}=None")
            else:
                args.append(self._param_value(p))
        return ", ".join(args)

    def _build_edge_case_args(self, func: FuncInfo) -> str:
        """Build args with edge-case values for numeric/string params."""
        args: list[str] = []
        for p in func.params:
            if p.name == "self" or p.name == "cls":
                continue
            if p.is_var_positional or p.is_var_keyword:
                continue
            edge_val = self._edge_case_value(p)
            if p.is_keyword_only or p.default is not None:
                args.append(f"{p.name}={edge_val}")
            else:
                args.append(edge_val)
        return ", ".join(args)

    def _build_init_args(self, cls: ClassInfo) -> str:
        """Build constructor args for a class."""
        init_method = next((m for m in cls.methods if m.name == "__init__"), None)
        if not init_method:
            return ""

        args: list[str] = []
        for p in init_method.params:
            if p.name == "self":
                continue
            if p.is_var_positional or p.is_var_keyword:
                continue
            val = self._param_value(p)
            if p.is_keyword_only or p.default is not None:
                args.append(f"{p.name}={val}")
            else:
                args.append(val)
        return ", ".join(args)

    def _param_value(self, param: ParamInfo) -> str:
        """Generate a sensible default value for a parameter."""
        if param.default is not None:
            return param.default

        ann = param.annotation
        if ann:
            # Direct match
            if ann in TYPE_DEFAULTS:
                val = TYPE_DEFAULTS[ann]
                if ann == "Path":
                    self._add_from_import("pathlib", "Path")
                return val

            # Optional[X] → None
            if ann.startswith("Optional["):
                return "None"

            # X | None → None
            if "| None" in ann or "|None" in ann:
                return "None"

            # list[X], dict[X, Y] etc.
            base = ann.split("[")[0]
            if base in TYPE_DEFAULTS:
                return TYPE_DEFAULTS[base]

        # Fallbacks by name convention
        name_lower = param.name.lower()
        if "path" in name_lower or "file" in name_lower:
            self._add_from_import("pathlib", "Path")
            return 'Path(".")'
        if "name" in name_lower or "title" in name_lower:
            return '"test"'
        if "count" in name_lower or "num" in name_lower or "size" in name_lower or "limit" in name_lower:
            return "1"
        if "flag" in name_lower or "enable" in name_lower or "verbose" in name_lower:
            return "False"
        if "timeout" in name_lower:
            return "30"
        if "url" in name_lower:
            return '"http://localhost"'
        if "port" in name_lower:
            return "8080"

        return "None"

    def _edge_case_value(self, param: ParamInfo) -> str:
        """Generate an edge-case value for a parameter."""
        ann = param.annotation
        if ann == "int":
            return "-1"
        if ann == "float":
            return "-1.0"
        if ann == "str":
            return '""'
        if ann == "bool":
            return "True"
        if ann == "list":
            return "[]"
        if ann == "dict":
            return "{}"
        # For untyped params, try name-based heuristics
        name_lower = param.name.lower()
        if "count" in name_lower or "num" in name_lower or "size" in name_lower or "limit" in name_lower:
            return "0"
        if "name" in name_lower:
            return '""'
        # If it has a default, try the opposite
        if param.default == "False":
            return "True"
        if param.default == "True":
            return "False"
        if param.default == "0":
            return "1"
        return "None"

    def _has_optional_params(self, func: FuncInfo) -> bool:
        """Check if a function has any optional parameters (besides self/cls)."""
        return any(
            p.default is not None
            or (p.annotation and ("Optional" in p.annotation or "| None" in p.annotation))
            for p in func.params
            if p.name not in ("self", "cls")
        )


def generate_test(module: ModuleInfo, config: GeneratorConfig | None = None) -> str:
    """Convenience function to generate tests for a module."""
    generator = PytestStubGenerator(config)
    return generator.generate(module)
