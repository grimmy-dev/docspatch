"""Tests for ast_compress — pure skeleton compression of Python source."""

import ast

from src.utils.ast_compress import compress_source


def _parseable(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def test_function_body_stripped() -> None:
    src = "def foo():\n    x = 1\n    return x\n"
    out = compress_source(src)
    assert "x = 1" not in out
    assert "return x" not in out
    assert "def foo()" in out


def test_function_signature_retained() -> None:
    src = "def add(a: int, b: int) -> int:\n    return a + b\n"
    out = compress_source(src)
    assert "def add(a: int, b: int) -> int:" in out


def test_type_hints_retained() -> None:
    src = "def greet(name: str) -> str:\n    return 'hello ' + name\n"
    out = compress_source(src)
    assert "name: str" in out
    assert "-> str" in out


def test_function_docstring_retained() -> None:
    src = 'def foo():\n    """Do the thing."""\n    x = 1\n    return x\n'
    out = compress_source(src)
    assert "Do the thing." in out
    assert "x = 1" not in out


def test_module_docstring_retained() -> None:
    src = '"""Top-level module."""\n\ndef foo():\n    pass\n'
    out = compress_source(src)
    assert "Top-level module." in out


def test_inline_comments_stripped() -> None:
    src = "def foo():\n    x = 1  # increment counter\n    return x\n"
    out = compress_source(src)
    assert "increment counter" not in out


def test_class_definition_retained() -> None:
    src = "class MyClass:\n    def method(self) -> None:\n        pass\n"
    out = compress_source(src)
    assert "class MyClass:" in out
    assert "def method(self) -> None:" in out


def test_class_method_body_stripped() -> None:
    src = "class MyClass:\n    def method(self) -> None:\n        x = 42\n        return x\n"
    out = compress_source(src)
    assert "x = 42" not in out


def test_nested_function_signature_retained() -> None:
    src = "def outer():\n    def inner(x: int) -> int:\n        return x + 1\n    return inner\n"
    out = compress_source(src)
    assert "def outer()" in out
    assert "def inner(x: int) -> int:" in out


def test_nested_function_body_stripped() -> None:
    src = "def outer():\n    def inner():\n        secret = 99\n    return inner\n"
    out = compress_source(src)
    assert "secret = 99" not in out


def test_decorated_function_retained() -> None:
    src = "@staticmethod\ndef foo() -> None:\n    pass\n"
    out = compress_source(src)
    assert "@staticmethod" in out
    assert "def foo() -> None:" in out


def test_output_is_valid_python() -> None:
    src = (
        '"""Module doc."""\n\n'
        "class Foo:\n"
        '    """Class doc."""\n\n'
        "    def bar(self, x: int) -> str:\n"
        '        """Bar doc."""\n'
        "        return str(x)\n\n"
        "def standalone(a: list[int]) -> int:\n"
        "    total = sum(a)\n"
        "    return total\n"
    )
    out = compress_source(src)
    assert _parseable(out)


def test_async_function_body_stripped() -> None:
    src = "async def fetch(url: str) -> bytes:\n    data = await download(url)\n    return data\n"
    out = compress_source(src)
    assert "data = await download" not in out
    assert "async def fetch(url: str) -> bytes:" in out
