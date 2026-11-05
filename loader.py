"""Import one function from one version of the code, isolated from the other.

Both versions usually contain modules with the same names (e.g. both have
`Math.py` or `utils.py`). A plain `import` would cache the first one in
sys.modules and silently hand it to the second version too, so each file is
loaded under a unique module name and any modules it imports from its own
checkout are removed from the cache again afterwards.
"""

import importlib.util
import sys
from pathlib import Path


class LoadError(RuntimeError):
    pass


def _is_inside(path, root):
    try:
        Path(path).resolve().relative_to(root)
        return True
    except ValueError:
        return False


def load_function(version_root, file_path, func_name, tag):
    """Return the callable `func_name` from `file_path` inside `version_root`.

    `func_name` may be dotted (e.g. "Calculator.add") to reach a class's
    static method or class method.
    """
    root = Path(version_root).resolve()
    full = (root / file_path).resolve()
    if not full.is_file():
        raise LoadError(f"{file_path} does not exist in {tag}")

    module_name = f"_refactorcompare_{tag}_{full.stem}"
    extra_paths = [str(full.parent), str(root)]
    modules_before = set(sys.modules)
    sys.path[:0] = extra_paths
    try:
        spec = importlib.util.spec_from_file_location(module_name, full)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise LoadError(f"importing {file_path} from {tag} failed: {exc!r}") from exc
    finally:
        for p in extra_paths:
            sys.path.remove(p)
        # Forget this version's own modules so the other version imports its own copies.
        for name in set(sys.modules) - modules_before:
            if name == module_name:
                continue
            mod_file = getattr(sys.modules[name], "__file__", None)
            if mod_file and _is_inside(mod_file, root):
                del sys.modules[name]

    obj = module
    for part in func_name.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            raise LoadError(f"{func_name} not found in {file_path} ({tag})") from None
    if not callable(obj):
        raise LoadError(f"{func_name} in {file_path} ({tag}) is not callable")
    return obj
