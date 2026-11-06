"""Run each version's function in its own long-lived worker process.

The main process never imports the code being compared. Each version gets a
worker (started with the "spawn" method, so it behaves the same on Windows)
that imports the function once, reports its parameters, and then runs calls
on request. Because every version lives in its own process:

- the versions can't share cached modules, even ones imported inside a
  function body, and can't see each other's global state;
- a call that never returns is stopped after `timeout` seconds and reported
  as ("timed out", timeout); a fresh worker takes over for the next call;
- sys.exit() is reported as ("exited", code), and a hard crash of the
  worker as ("crashed", exit_code), instead of taking the tool down.
"""

import copy
import inspect
import multiprocessing
import pickle
import typing

from loader import LoadError, load_function

# Limit for starting a worker and importing the user's file.
STARTUP_TIMEOUT = 60


def call(func, args, kwargs):
    """Run func and describe what happened, so two runs can be compared.

    Exceptions are recorded by class name, so the "same" exception class
    defined separately in each version still counts as the same.
    """
    try:
        return ("returned", func(*copy.deepcopy(args), **copy.deepcopy(kwargs)))
    except SystemExit as exc:
        return ("exited", exc.code)
    except Exception as exc:
        return ("raised", type(exc).__qualname__)


def describe_parameters(func):
    """List func's parameters as plain data that can be sent between processes.

    Each entry is a dict with "name", "kind" ("positional", "keyword" or
    "var"), "has_default" and "hint" (the type hint pickled to bytes, or None).
    """
    try:
        hints = typing.get_type_hints(func)
    except Exception:
        hints = {}
    params = []
    for name, param in inspect.signature(func).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            kind = "var"
        elif param.kind == param.KEYWORD_ONLY:
            kind = "keyword"
        else:
            kind = "positional"
        hint = None
        if name in hints:
            try:
                hint = pickle.dumps(hints[name])
            except Exception:
                hint = pickle.dumps(UnusableHint(repr(hints[name])))
        params.append({
            "name": name,
            "kind": kind,
            "has_default": param.default is not param.empty,
            "hint": hint,
        })
    return params


class UnusableHint:
    """A type hint that only makes sense inside its own version (e.g. a class
    defined in the user's code), so inputs can't be generated from it."""

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


def decode_hint(hint):
    if hint is None:
        return None
    try:
        return pickle.loads(hint)
    except Exception:
        return UnusableHint("a type defined in the code being compared")


class ReprValue:
    """Stand-in for a return value that couldn't be sent back from the worker
    (e.g. an instance of a class defined in the user's code). Compared by repr."""

    def __init__(self, text):
        self.text = text

    def __eq__(self, other):
        return isinstance(other, ReprValue) and self.text == other.text

    def __repr__(self):
        return self.text


def _worker(conn, version_root, file_path, func_name, tag):
    try:
        func = load_function(version_root, file_path, func_name, tag)
        params = describe_parameters(func)
    except (LoadError, ValueError, TypeError) as exc:
        conn.send(("error", str(exc)))
        return
    except SystemExit as exc:
        conn.send(("error", f"importing {file_path} from {tag} called sys.exit({exc.code!r})"))
        return
    conn.send(("ready", params))

    while True:
        try:
            request = conn.recv()
        except EOFError:
            return
        if request is None:
            return
        outcome = call(func, *request)
        try:
            payload = pickle.dumps(outcome)
        except Exception:
            payload = None
        conn.send((payload, outcome[0], repr(outcome[1])))


class LocalRunner:
    """Calls a function directly in this process. Used for plain functions,
    e.g. in unit tests; it has no timeout or crash protection."""

    def __init__(self, func):
        self.func = func
        self.parameters = describe_parameters(func)

    def __call__(self, args, kwargs):
        return call(self.func, args, kwargs)


def as_runner(obj):
    return obj if isinstance(obj, (LocalRunner, VersionRunner)) else LocalRunner(obj)


class VersionRunner:
    """Calls `func_name` from one checkout in a separate, killable process.

    `parameters` describes the function's parameters (see describe_parameters).
    Calling the runner with (args, kwargs) returns an outcome like `call` does.
    """

    def __init__(self, version_root, file_path, func_name, tag, timeout):
        self.target = (str(version_root), file_path, func_name, tag)
        self.tag = tag
        self.timeout = timeout
        self.parameters = None
        self._ctx = multiprocessing.get_context("spawn")
        self._proc = None
        self._conn = None
        self._start()

    def _start(self):
        parent_conn, child_conn = self._ctx.Pipe()
        proc = self._ctx.Process(target=_worker, args=(child_conn, *self.target), daemon=True)
        proc.start()
        child_conn.close()
        self._proc, self._conn = proc, parent_conn

        if not parent_conn.poll(STARTUP_TIMEOUT):
            self._kill()
            raise LoadError(f"importing {self.target[1]} from {self.tag} "
                            f"took longer than {STARTUP_TIMEOUT}s")
        try:
            status, detail = parent_conn.recv()
        except EOFError:
            proc.join()
            code = proc.exitcode
            self._kill()
            raise LoadError(f"the {self.tag} process exited while importing "
                            f"{self.target[1]} (exit code {code})") from None
        if status == "error":
            self._kill()
            raise LoadError(detail)
        self.parameters = detail

    def _kill(self):
        if self._proc is not None:
            self._proc.kill()
            self._proc.join()
            self._conn.close()
        self._proc = self._conn = None

    def __call__(self, args, kwargs):
        if self._proc is None:
            self._start()
        self._conn.send((args, kwargs))

        if not self._conn.poll(self.timeout):
            self._kill()
            return ("timed out", self.timeout)
        try:
            payload, kind, text = self._conn.recv()
        except EOFError:
            self._proc.join()
            code = self._proc.exitcode
            self._kill()
            return ("crashed", code)

        if payload is not None:
            try:
                return pickle.loads(payload)
            except Exception:
                pass
        return (kind, ReprValue(text))

    def close(self):
        if self._proc is not None:
            try:
                self._conn.send(None)
            except OSError:
                pass
            self._proc.join(1)
            self._kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
