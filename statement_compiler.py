import os
import subprocess
from dataclasses import dataclass


@dataclass
class StatementCompileResult:
    ok: bool
    stderr: str = ""
    stdout: str = ""


def compile_latex_statement(tex_path, html_path):
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    try:
        result = subprocess.run(
            [
                "pandoc",
                "--from=latex",
                "--to=html5",
                "--mathjax",
                tex_path,
                "-o",
                html_path,
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return StatementCompileResult(ok=False, stderr="pandoc not found")
    if result.returncode != 0:
        return StatementCompileResult(
            ok=False,
            stderr=result.stderr.strip() or "pandoc failed",
            stdout=result.stdout,
        )
    return StatementCompileResult(ok=True, stderr=result.stderr, stdout=result.stdout)
