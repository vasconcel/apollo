"""
APOLLO Architectural Fitness Framework

Centralized deterministic validation helpers for architectural governance.
Used exclusively by tests — no runtime coupling into application flow.

Every helper is a pure function operating on static source inspection.
No side effects, no framework assumptions, no UI/advisory/persistence imports.
"""

import ast
import inspect
from pathlib import Path
from typing import List, Type, Any


def get_source(obj) -> str:
    """Get source code of an object for inspection."""
    return inspect.getsource(obj)


def assert_source_lacks(source: str, forbidden: List[str], label: str = "") -> None:
    """Assert none of the forbidden strings appear in source code.

    Uses string containment check. Suitable for quick checks that a
    source file does not reference specific identifiers.
    """
    for item in forbidden:
        assert item not in source, (
            f"{label} must not reference '{item}'"
        )


def assert_source_has(source: str, expected: List[str], label: str = "") -> None:
    """Assert all expected strings appear in source code."""
    for item in expected:
        assert item in source, (
            f"{label} must contain '{item}'"
        )


def assert_module_ast_lacks_imports(
    module_path: Path,
    forbidden: List[str],
    label: str = "",
) -> None:
    """Assert module AST contains none of the forbidden imports.

    Walks the AST tree checking ImportFrom and Import nodes.
    - ImportFrom modules are checked with startswith (catches submodules).
    - Import names are checked with exact match.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for banned in forbidden:
                if banned.startswith("src."):
                    assert not module.startswith(banned), (
                        f"{label} must not import '{module}'"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for banned in forbidden:
                    if not banned.startswith("src."):
                        assert alias.name != banned, (
                            f"{label} must not import '{alias.name}'"
                        )


def assert_is_stateless(cls: Type) -> None:
    """Assert a class is stateless (multiple instances are identical types).

    Checks only that the class can be instantiated without arguments and
    that instances have the same type. Services with required constructor
    parameters cannot use this helper directly.
    """
    s1 = cls()
    s2 = cls()
    assert type(s1) == type(s2), f"{cls.__name__} is not stateless"


def source_path(cls: Type) -> Path:
    """Get the source file path for a class or module."""
    return Path(inspect.getfile(cls))


def resolve_source_path(test_file: str, *parts: str) -> Path:
    """Resolve a source path relative to the tests/ directory.

    Usage in test files:
        path = resolve_source_path(__file__, 'src', 'core', 'myservice.py')
    """
    return Path(test_file).parent.parent.joinpath(*parts)
