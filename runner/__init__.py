from .cpp import CppRunner
from .python import PythonRunner


def get_runner(language, source, binary):
    lang = str(language or "").strip().lower()
    if lang in ("py", "python", "python3"):
        return PythonRunner(source)
    return CppRunner(source, binary)
