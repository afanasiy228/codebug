import subprocess


class PythonRunner:
    def __init__(self, source):
        self.source = source

    def compile(self):
        return subprocess.run(
            ["python3", "-m", "py_compile", self.source],
            capture_output=True,
            text=True
        )

    def command(self):
        return ["python3", self.source]
