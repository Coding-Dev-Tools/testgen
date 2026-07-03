"""AST-based analyzer — extracts testable units from Python source files."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParamInfo:
    """Metadata about a function/method parameter."""

    name: str
    annotation: str | None = None
    default: str | None = None
    is_positional_only: bool = False
    is_keyword_only: bool = False
    is_var_positional: bool = False  # *args
    is_var_keyword: bool = False  # **kwargs


@dataclass
class FuncInfo:
    """Metadata about a testable function or method."""

    name: str
    kind: str = "function"  # function, method, staticmethod, classmethod
    params: list[ParamInfo] = field(default_factory=list)
    return_annotation: str | None = None
    docstring: str | None = None
    decorators: list[str] = field(default_factory=list)
    is_abstract: bool = False
    is_private: bool = False
    is_dunder: bool = False
    parent_class: str | None = None
    line_number: int = 0


@dataclass
class ClassInfo:
    """Metadata about a class."""

    name: str
    bases: list[str] = field(default_factory=list)
    methods: list[FuncInfo] = field(default_factory=list)
    docstring: str | None = None
    is_abstract: bool = False
    is_dataclass: bool = False
    line_number: int = 0


@dataclass
class ModuleInfo:
    """Analysis result for a single Python module."""

    path: Path
    module_name: str
    functions: list[FuncInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    docstring: str | None = None


def _annotation_to_str(node: ast.expr | None) -> str | None:
    """Convert an AST annotation node to a string representation."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_annotation_to_str(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        base = _annotation_to_str(node.value)
        slice_str = _annotation_to_str(node.slice)
        return f"{base}[{slice_str}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _annotation_to_str(node.left)
        right = _annotation_to_str(node.right)
        return f"{left} | {right}"
    if isinstance(node, ast.Tuple):
        parts = [_annotation_to_str(elt) for elt in node.elts]
        return ", ".join(p for p in parts if p)
    if isinstance(node, ast.Index):  # Python 3.8 compat
        # ast.Index was deprecated in Python 3.9, slice is directly accessible
        return _annotation_to_str(getattr(node, "value", node))
    # Fallback
    try:
        return ast.unparse(node)
    except Exception:
        return "Any"


def _default_to_str(node: ast.expr | None) -> str | None:
    """Convert a default value AST node to a string."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.List):
        return "[]"
    if isinstance(node, ast.Dict):
        return "{}"
    if isinstance(node, ast.Set):
        return "set()"
    if isinstance(node, ast.Tuple):
        return "()"
    if isinstance(node, ast.Call):
        func_name = _annotation_to_str(node.func) or "dict"
        return f"{func_name}()"
    try:
        return ast.unparse(node)
    except Exception:
        return "None"


def _parse_params(args: ast.arguments) -> list[ParamInfo]:
    """Extract parameter info from an ast.arguments node."""
    params: list[ParamInfo] = []

    # Positional-only
    for arg in args.posonlyargs:
        params.append(ParamInfo(
            name=arg.arg,
            annotation=_annotation_to_str(arg.annotation),
            is_positional_only=True,
        ))

    # Regular positional + keyword
    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        default_idx = i - defaults_offset
        default = _default_to_str(args.defaults[default_idx]) if default_idx >= 0 else None
        params.append(ParamInfo(
            name=arg.arg,
            annotation=_annotation_to_str(arg.annotation),
            default=default,
        ))

    # *args
    if args.vararg:
        params.append(ParamInfo(
            name=args.vararg.arg,
            annotation=_annotation_to_str(args.vararg.annotation),
            is_var_positional=True,
        ))

    # Keyword-only
    for i, arg in enumerate(args.kwonlyargs):
        default = _default_to_str(args.kw_defaults[i]) if i < len(args.kw_defaults) and args.kw_defaults[i] else None
        params.append(ParamInfo(
            name=arg.arg,
            annotation=_annotation_to_str(arg.annotation),
            default=default,
            is_keyword_only=True,
        ))

    # **kwargs
    if args.kwarg:
        params.append(ParamInfo(
            name=args.kwarg.arg,
            annotation=_annotation_to_str(args.kwarg.annotation),
            is_var_keyword=True,
        ))

    return params


def _get_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    """Extract decorator names from a function or class node."""
    decorators = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(f"{_annotation_to_str(dec.value)}.{dec.attr}" or dec.attr)
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(dec.func.attr)
    return decorators


class ModuleAnalyzer:
    """Analyzes a Python module to extract testable units."""

    def __init__(self, include_private: bool = False, include_dunder: bool = False):
        self.include_private = include_private
        self.include_dunder = include_dunder

    def analyze_file(self, path: Path) -> ModuleInfo:
        """Analyze a Python file and return structured metadata."""
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        module_name = self._path_to_module(path)
        module_info = ModuleInfo(path=path, module_name=module_name)

        # Module-level docstring
        module_info.docstring = ast.get_docstring(tree)

        # Module-level imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                module_info.imports.append(ast.unparse(node))

        # Walk top-level nodes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                func = self._parse_function(node)
                if func:
                    module_info.functions.append(func)
            elif isinstance(node, ast.ClassDef):
                cls = self._parse_class(node)
                if cls:
                    module_info.classes.append(cls)

        return module_info

    def _path_to_module(self, path: Path) -> str:
        """Convert a file path to a dotted module name."""
        parts = list(path.with_suffix("").parts)
        # Find 'src' or the first package root
        for i, part in enumerate(parts):
            if part == "src" and i + 1 < len(parts):
                return ".".join(parts[i + 1 :])
        return ".".join(parts)

    def _parse_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, parent_class: str | None = None
    ) -> FuncInfo | None:
        """Parse a function definition into FuncInfo."""
        name = node.name
        is_private = name.startswith("_") and not name.startswith("__")
        is_dunder = name.startswith("__") and name.endswith("__")

        if is_private and not self.include_private:
            return None
        if is_dunder and not self.include_dunder:
            return None

        decorators = _get_decorators(node)
        kind = "function"
        if parent_class:
            kind = "method"
            if "staticmethod" in decorators:
                kind = "staticmethod"
            elif "classmethod" in decorators:
                kind = "classmethod"

        is_abstract = "abstractmethod" in decorators

        return FuncInfo(
            name=name,
            kind=kind,
            params=_parse_params(node.args),
            return_annotation=_annotation_to_str(node.returns),
            docstring=ast.get_docstring(node),
            decorators=decorators,
            is_abstract=is_abstract,
            is_private=is_private,
            is_dunder=is_dunder,
            parent_class=parent_class,
            line_number=node.lineno,
        )

    def _parse_class(self, node: ast.ClassDef) -> ClassInfo | None:
        """Parse a class definition into ClassInfo."""
        name = node.name
        is_private = name.startswith("_")

        if is_private and not self.include_private:
            return None

        bases = [_annotation_to_str(base) or "object" for base in node.bases]
        decorators = _get_decorators(node) if hasattr(node, "decorator_list") else []

        is_abstract = any(
            isinstance(stmt, ast.FunctionDef)
            and "abstractmethod" in _get_decorators(stmt)
            for stmt in node.body
        )

        is_dataclass = "dataclass" in decorators

        cls = ClassInfo(
            name=name,
            bases=bases,
            docstring=ast.get_docstring(node),
            is_abstract=is_abstract,
            is_dataclass=is_dataclass,
            line_number=node.lineno,
        )

        # Parse methods
        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
                func = self._parse_function(stmt, parent_class=name)
                if func:
                    cls.methods.append(func)

        return cls


def analyze_file(path: Path, include_private: bool = False, include_dunder: bool = False) -> ModuleInfo:
    """Convenience function to analyze a single file."""
    analyzer = ModuleAnalyzer(include_private=include_private, include_dunder=include_dunder)
    return analyzer.analyze_file(path)
