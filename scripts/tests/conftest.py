import importlib.util
import sys
from pathlib import Path

PROCESS = Path(__file__).parents[1] / "process"


def load_process_module(name: str):
    spec = importlib.util.spec_from_file_location(name, PROCESS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
