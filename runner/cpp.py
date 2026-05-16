import subprocess


class CppRunner:
    def __init__(self, source, binary):
        self.source = source
        self.binary = binary

    def compile(self):
        return subprocess.run(
            ["g++", "-std=c++17", "-O2", self.source, "-o", self.binary],
            capture_output=True,
            text=True
        )

    def command(self):
        return [f"./{self.binary}"]
