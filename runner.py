"""Run one version's function in its own process, so a call can be stopped.

A function stuck in an infinite loop can't be interrupted from inside the
same Python process. Each version therefore gets a worker process that loads
the function once and then runs calls on request. If a call takes longer than
`timeout` seconds the worker is killed, a fresh one is started for the next
call, and the call's outcome is reported as ("timed out", timeout).
"""

import copy
import multiprocessing
import pickle

from loader import LoadError, load_function

# Generous limit for starting a worker and importing the user's file.
STARTUP_TIMEOUT = 60


def call(func, args, kwargs):
    """Run func and describe what happened, so two runs can be compared.

    Exceptions are recorded by class name, so the "same" exception class
    defined separately in each version still counts as the same.
    """
    try:
        return ("returned", func(*copy.deepcopy(args), **copy.deepcopy(kwargs)))
    except Exception as exc:
        return ("raised", type(exc).__qualname__)


class ReprValue:
    """Stand-in for a return value that couldn't be sent back from the worker."""

    def __init__(self, text):
        self.text = text

    def __eq__(self, other):
        return isinstance(other, ReprValue) and self.text == other.text

    def __repr__(self):
        return self.text


def _worker(conn, version_root, file_path, func_name, tag):
    try:
        func = load_function(version_root, file_path, func_name, tag)
    except LoadError as exc:
        conn.send(("error", str(exc)))
        return
    conn.send(("ready", None))

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
        conn.send((payload, repr(outcome[1])))


class VersionRunner:
    """Calls `func_name` from one checkout in a separate, killable process."""

    def __init__(self, version_root, file_path, func_name, tag, timeout):
        self.target = (str(version_root), file_path, func_name, tag)
        self.tag = tag
        self.timeout = timeout
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
            raise LoadError(f"starting {self.tag} took longer than {STARTUP_TIMEOUT}s")
        try:
            status, detail = parent_conn.recv()
        except EOFError:
            self._kill()
            raise LoadError(f"the {self.tag} worker process exited while starting") from None
        if status == "error":
            self._kill()
            raise LoadError(detail)

    def _kill(self):
        if self._proc is not None:
            self._proc.kill()
            self._proc.join()
            self._conn.close()
        self._proc = self._conn = None

    def __call__(self, args, kwargs):
        """Return the outcome of func(*args, **kwargs), like `call` does."""
        if self._proc is None:
            self._start()
        self._conn.send((args, kwargs))

        if not self._conn.poll(self.timeout):
            self._kill()
            return ("timed out", self.timeout)
        try:
            payload, text = self._conn.recv()
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
        return ("returned", ReprValue(text))

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
