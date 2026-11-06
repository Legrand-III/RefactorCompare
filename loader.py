"""Import one function from one version of the code.

Meant to run inside that version's own worker process (see runner.py), so
there is no need to keep the two versions' modules apart here: each process
has its own module cache, and the version's folders can stay on sys.path for
imports made later, e.g. inside the function body.
"""

import importlib.util
import sys
from pathlib import Path


class LoadError(RuntimeError):
    pass


def load_function(version_root, file_path, func_name, tag):
    """Return the callable `func_name` from `file_path` inside `version_root`.

    `func_name` may be dotted (e.g. "Calculator.add") to reach a class's
    static method or class method.
    """
    root = Path(version_root).resolve()
    full = (root / file_path).resolve()
    if not full.is_file():
        raise LoadError(f"{file_path} does not exist in {tag}")

    sys.path[:0] = [str(full.parent), str(root)]
    module_name = f"_refactorcompare_{full.stem}"
    spec = importlib.util.spec_from_file_location(module_name, full)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise LoadError(f"importing {file_path} from {tag} failed: {exc!r}") from exc

    obj = module
    for part in func_name.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            raise LoadError(f"{func_name} not found in {file_path} ({tag})") from None
    if not callable(obj):
        raise LoadError(f"{func_name} in {file_path} ({tag}) is not callable")
    return obj
