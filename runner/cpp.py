import os

from sandbox import run_in_sandbox


class CppRunner:
    def __init__(self, source, binary):
        self.source = source
        self.binary = binary

    def compile(self):
        return run_in_sandbox(
            ["g++", "-std=c++17", "-O2", self.source, "-o", self.binary],
            workdir=os.getcwd(),
            language="cpp",
            timeout=30,
        )

    def command(self):
        return [f"./{self.binary}"]
