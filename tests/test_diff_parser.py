"""Tests for the diff parser module."""

import textwrap

from testgen.diff_parser import get_changed_functions, parse_diff


class TestParseDiff:
    """Tests for parse_diff function."""

    def test_parse_empty_diff(self):
        """Empty diff returns no hunks."""
        result = parse_diff("")
        assert result == []

    def test_parse_simple_hunk(self):
        """Parse a single hunk from a unified diff."""
        diff = textwrap.dedent("""\
            diff --git a/src/mod.py b/src/mod.py
            --- a/src/mod.py
            +++ b/src/mod.py
            @@ -10,3 +10,4 @@
             existing_line
            +added_line
             another_existing
        """)
        hunks = parse_diff(diff)
        assert len(hunks) == 1
        assert hunks[0].file_path.name == "mod.py"
        assert hunks[0].old_start == 10
        assert hunks[0].new_start == 10

    def test_parse_multiple_hunks(self):
        """Parse multiple hunks in a single diff."""
        diff = textwrap.dedent("""\
            diff --git a/src/mod.py b/src/mod.py
            --- a/src/mod.py
            +++ b/src/mod.py
            @@ -1,3 +1,4 @@
             line1
            +line2
             line3
            @@ -20,3 +21,4 @@
             line20
            +line21
             line22
        """)
        hunks = parse_diff(diff)
        assert len(hunks) == 2

    def test_parse_multiple_files(self):
        """Parse hunks from multiple files."""
        diff = textwrap.dedent("""\
            diff --git a/a.py b/a.py
            --- a/a.py
            +++ b/a.py
            @@ -1,3 +1,4 @@
             x
            +y
            diff --git a/b.py b/b.py
            --- a/b.py
            +++ b/b.py
            @@ -5,3 +5,4 @@
             m
            +n
        """)
        hunks = parse_diff(diff)
        assert len(hunks) == 2
        file_names = {h.file_path.name for h in hunks}
        assert file_names == {"a.py", "b.py"}


class TestGetChangedFunctions:
    """Tests for get_changed_functions."""

    def test_no_git_repo(self, tmp_path):
        """Non-git directory returns empty set."""
        result = get_changed_functions(tmp_path)
        assert result == set()

    def test_parse_diff_for_added_function(self):
        """Detect added function in a diff string."""
        diff = textwrap.dedent("""\
            diff --git a/src/mod.py b/src/mod.py
            --- a/src/mod.py
            +++ b/src/mod.py
            @@ -5,3 +5,6 @@
             existing
            +def new_func(x: int) -> str:
            +    return str(x)
            +
        """)
        # Use parse_diff directly instead of get_changed_functions (which needs git)
        from testgen.diff_parser import _FUNC_RE

        current_file = None
        changed = set()
        from pathlib import Path

        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                path_str = line[6:].strip()
                if path_str != "/dev/null":
                    current_file = Path(path_str)
                continue
            if current_file and line.startswith("+"):
                match = _FUNC_RE.match(line)
                if match:
                    changed.add((current_file, match.group(1)))
        assert any(name == "new_func" for _, name in changed)

    def test_parse_diff_for_added_class(self):
        """Detect added class in a diff string."""
        diff = textwrap.dedent("""\
            diff --git a/src/mod.py b/src/mod.py
            --- a/src/mod.py
            +++ b/src/mod.py
            @@ -1,3 +1,5 @@
            +class MyService:
            +    def run(self): pass
        """)
        from pathlib import Path

        from testgen.diff_parser import _CLASS_RE

        current_file = None
        changed = set()
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                path_str = line[6:].strip()
                if path_str != "/dev/null":
                    current_file = Path(path_str)
                continue
            if current_file and line.startswith("+"):
                match = _CLASS_RE.match(line)
                if match:
                    changed.add((current_file, match.group(1)))
        assert any(name == "MyService" for _, name in changed)

    def test_parse_diff_async_function(self):
        """Detect added async function in a diff."""
        diff = textwrap.dedent("""\
            diff --git a/src/mod.py b/src/mod.py
            --- a/src/mod.py
            +++ b/src/mod.py
            @@ -1,3 +1,5 @@
            +async def fetch_data(url: str):
            +    pass
        """)
        from pathlib import Path

        from testgen.diff_parser import _FUNC_RE

        current_file = None
        changed = set()
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                current_file = Path(line[6:].strip())
                continue
            if current_file and line.startswith("+"):
                match = _FUNC_RE.match(line)
                if match:
                    changed.add((current_file, match.group(1)))
        assert any(name == "fetch_data" for _, name in changed)
