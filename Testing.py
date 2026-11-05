"""Property test that two versions of a function behave the same.

Hypothesis generates inputs from the function's parameter types, calls both
versions with the same inputs, and checks they give the same result (or both
raise the same kind of exception). On a mismatch Hypothesis shrinks the input
to the simplest one it can find that still shows the difference.
"""

import inspect
import math
import typing

from hypothesis import HealthCheck, given, settings, strategies as st

from runner import call

POSITIONAL = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)


class StrategyError(RuntimeError):
    pass


def parse_type(text):
    """Turn a type written by the user ("int", "list[str]", "Optional[float]") into a type."""
    namespace = {name: getattr(typing, name) for name in typing.__all__}
    namespace.update(__builtins__ if isinstance(__builtins__, dict) else vars(__builtins__))
    try:
        return eval(text, {"__builtins__": {}}, namespace)
    except Exception as exc:
        raise StrategyError(f"could not understand type {text!r}: {exc}") from None


def build_strategies(func, arg_types=None, ask=None):
    """Work out a Hypothesis strategy for every parameter of `func`.

    Types come from, in order: `arg_types` (user overrides), the function's
    type hints, or `ask(param_name)` if given. Parameters that have a default
    value and no known type are left out, so the default gets used.

    Returns (positional_names, positional_strategies, keyword_strategies).
    """
    arg_types = dict(arg_types or {})
    sig = inspect.signature(func)
    try:
        hints = typing.get_type_hints(func)
    except Exception:
        hints = {}

    pos_names, pos_strats, kw_strats = [], [], {}
    missing = []
    for name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if name in arg_types:
            tp = arg_types.pop(name)
        elif name in hints:
            tp = hints[name]
        elif param.default is not inspect.Parameter.empty:
            continue
        elif ask is not None:
            tp = ask(name)
        else:
            missing.append(name)
            continue

        strategy = st.from_type(tp)
        if param.kind in POSITIONAL:
            pos_names.append(name)
            pos_strats.append(strategy)
        else:
            kw_strats[name] = strategy

    if missing:
        raise StrategyError(
            "no type known for parameter(s) " + ", ".join(missing)
            + ". Add type hints or pass e.g. --arg " + missing[0] + "=int"
        )
    if arg_types:
        raise StrategyError("--arg given for unknown parameter(s): " + ", ".join(arg_types))
    return pos_names, pos_strats, kw_strats


def same_value(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    try:
        return bool(a == b)
    except Exception:
        return repr(a) == repr(b)


def same_outcome(o1, o2):
    return o1[0] == o2[0] and same_value(o1[1], o2[1])


def describe(outcome):
    kind, value = outcome
    if kind == "raised":
        return f"raised {getattr(value, '__name__', value)}"
    if kind == "timed out":
        return f"did not finish within {value:g}s (infinite loop?)"
    if kind == "crashed":
        return f"crashed its process (exit code {value})"
    return f"returned {value!r}"


def compare(func1, func2, arg_types=None, ask=None, max_examples=500, run1=None, run2=None):
    """Return (equivalent: bool, message: str).

    `run1` / `run2` are optional callables (args, kwargs) -> outcome used to
    run each version, e.g. a runner.VersionRunner that runs it in a separate
    process with a time limit. By default the functions are called directly.
    """
    run1 = run1 or (lambda args, kwargs: call(func1, args, kwargs))
    run2 = run2 or (lambda args, kwargs: call(func2, args, kwargs))
    pos_names, pos_strats, kw_strats = build_strategies(func1, arg_types, ask)

    sig2_names = list(inspect.signature(func2).parameters)
    if pos_names and sig2_names[: len(pos_names)] != pos_names:
        print(f"Note: parameter names differ: {pos_names} vs {sig2_names}. "
              "Arguments are passed by position.")

    print("Generating inputs:")
    for name, strategy in zip(pos_names, pos_strats):
        print(f"  {name}: {strategy}")
    for name, strategy in kw_strats.items():
        print(f"  {name}: {strategy}")

    @settings(
        max_examples=max_examples,
        deadline=None,
        database=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(args=st.tuples(*pos_strats), kwargs=st.fixed_dictionaries(kw_strats))
    def versions_agree(args, kwargs):
        o1 = run1(args, kwargs)
        o2 = run2(args, kwargs)
        if not same_outcome(o1, o2):
            shown = [f"{n}={v!r}" for n, v in zip(pos_names, args)]
            shown += [f"{n}={v!r}" for n, v in kwargs.items()]
            raise AssertionError(
                f"Smallest input found: ({', '.join(shown)})\n"
                f"  Version1 {describe(o1)}\n"
                f"  Version2 {describe(o2)}"
            )

    try:
        versions_agree()
    except AssertionError as exc:
        return False, str(exc)
    return True, f"{max_examples} generated inputs gave the same result in both versions"
