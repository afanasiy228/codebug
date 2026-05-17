import os

from sandbox import run_in_sandbox


class PythonRunner:
    def __init__(self, source):
        self.source = source

    def compile(self):
        return run_in_sandbox(
            ["python3", "-m", "py_compile", self.source],
            workdir=os.getcwd(),
            language="python",
            timeout=30,
        )

    def command(self):
        return ["python3", self.source]
