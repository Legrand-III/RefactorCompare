"""Run the whole tool (Main.main) against throwaway repos and check the verdict.

Exit codes: 0 = same behaviour, 1 = difference found, 2 = error.
"""

import Main

FAST = ["--examples", "50"]


def run(repo, file, function, *extra):
    return Main.main([str(repo), "v1", "v2", file, function, *FAST, *extra])


# ---------- refactors that should PASS ----------

def test_equivalent_refactor_passes(make_repo, capsys):
    repo = make_repo(
        {"calc.py": """
            def total(items: list[int]) -> int:
                t = 0
                for x in items:
                    t += x
                return t
        """},
        {"calc.py": """
            def total(items: list[int]) -> int:
                return sum(items)
        """},
    )
    assert run(repo, "calc.py", "total") == 0
    assert "PASS" in capsys.readouterr().out


def test_same_exception_type_counts_as_equivalent(make_repo):
    repo = make_repo(
        {"calc.py": "def div(a: int, b: int) -> float:\n    return a / b\n"},
        {"calc.py": "def div(a: int, b: int) -> float:\n    result = a / b\n    return result\n"},
    )
    assert run(repo, "calc.py", "div") == 0


def test_untyped_function_with_arg_types(make_repo):
    repo = make_repo(
        {"calc.py": "def add(a, b):\n    return a + b\n"},
        {"calc.py": "def add(a, b):\n    ans = a + b\n    return ans\n"},
    )
    assert run(repo, "calc.py", "add", "--arg", "a=int", "--arg", "b=int") == 0


def test_keyword_only_and_default_parameters(make_repo):
    repo = make_repo(
        {"calc.py": "def scale(xs: list[int], *, by: int = 1) -> list[int]:\n"
                    "    return [x * by for x in xs]\n"},
        {"calc.py": "def scale(xs: list[int], *, by: int = 1) -> list[int]:\n"
                    "    out = []\n    for x in xs:\n        out.append(x * by)\n    return out\n"},
    )
    assert run(repo, "calc.py", "scale") == 0


def test_file_in_subfolder_and_dotted_name(make_repo):
    repo = make_repo(
        {"src/shapes.py": "class Sq:\n    @staticmethod\n    def area(s: int) -> int:\n        return s * s\n"},
        {"src/shapes.py": "class Sq:\n    @staticmethod\n    def area(s: int) -> int:\n        return s ** 2\n"},
    )
    assert run(repo, "src/shapes.py", "Sq.area") == 0


# ---------- refactors that should FAIL ----------

def test_behaviour_change_is_caught_with_smallest_input(make_repo, capsys):
    repo = make_repo(
        {"calc.py": "def div(a: int, b: int) -> float:\n    return a / b\n"},
        {"calc.py": "def div(a: int, b: int) -> float:\n    return a / b if b else 0.0\n"},
    )
    assert run(repo, "calc.py", "div") == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "a=0, b=0" in out                      # Hypothesis shrank to the simplest case
    assert "raised ZeroDivisionError" in out
    assert "returned 0.0" in out


def test_wrong_return_value_is_caught(make_repo):
    repo = make_repo(
        {"calc.py": "def add(a: int, b: int) -> int:\n    return a + b\n"},
        {"calc.py": "def add(a: int, b: int) -> int:\n    return b\n"},
    )
    assert run(repo, "calc.py", "add") == 1


def test_change_in_same_named_helper_module_is_caught(make_repo):
    """Both versions import `helpers`; only helpers.py changes.

    If the two versions shared one cached copy of `helpers`, this would
    wrongly pass. Guards the isolation in loader.py.
    """
    main_file = "from helpers import clean\n\ndef tidy(s: str) -> str:\n    return clean(s)\n"
    repo = make_repo(
        {"pkg/text.py": main_file, "pkg/helpers.py": "def clean(s):\n    return s.strip()\n"},
        {"pkg/helpers.py": "def clean(s):\n    return s.strip(' ')\n"},
    )
    assert run(repo, "pkg/text.py", "tidy") == 1


# ---------- errors (exit code 2) ----------

def test_missing_function(make_repo, capsys):
    repo = make_repo({"calc.py": "def f(x: int): return x\n"}, {})
    assert run(repo, "calc.py", "nope") == 2
    assert "nope not found" in capsys.readouterr().err


def test_missing_file(make_repo, capsys):
    repo = make_repo({"calc.py": "def f(x: int): return x\n"}, {})
    assert run(repo, "other.py", "f") == 2
    assert "does not exist" in capsys.readouterr().err


def test_bad_commit(make_repo, capsys):
    repo = make_repo({"calc.py": "def f(x: int): return x\n"}, {})
    assert Main.main([str(repo), "v1", "no-such-commit", "calc.py", "f"]) == 2
    assert "invalid reference" in capsys.readouterr().err


def test_untyped_parameter_without_arg_is_an_error(make_repo, capsys):
    # pytest's stdin is not a terminal, so the tool can't ask and must error out.
    repo = make_repo({"calc.py": "def add(a, b):\n    return a + b\n"}, {})
    assert run(repo, "calc.py", "add") == 2
    assert "--arg a=int" in capsys.readouterr().err


def test_file_that_fails_to_import(make_repo, capsys):
    repo = make_repo(
        {"calc.py": "def f(x: int): return x\n"},
        {"calc.py": "def f(x: int) return x\n"},     # syntax error in version 2
    )
    assert run(repo, "calc.py", "f") == 2
    assert "Version2 failed" in capsys.readouterr().err


# ---------- functions that hang ----------

def test_infinite_loop_is_caught_instead_of_hanging(make_repo, capsys):
    repo = make_repo(
        {"calc.py": "def absval(x: int) -> int:\n    return abs(x)\n"},
        {"calc.py": "def absval(x: int) -> int:\n"
                    "    while x < 0:\n        pass\n    return x\n"},
    )
    assert run(repo, "calc.py", "absval", "--timeout", "0.5") == 1
    out = capsys.readouterr().out
    assert "x=-1" in out
    assert "Version2 did not finish within 0.5s" in out
