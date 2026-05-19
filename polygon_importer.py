import os
import re
import shutil
import xml.etree.ElementTree as ET


class PolygonImportError(Exception):
    pass


def _read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _copy_text_if_exists(root, candidates):
    for rel in candidates:
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            return _read_text(path)
    return ""


def _copy_file_if_exists(root, candidates, dest_path):
    for rel in candidates:
        src = os.path.join(root, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copyfile(src, dest_path)
            return True
    return False


def _natural_key(value):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def _normalize_statement_tex(raw_text):
    text = str(raw_text or "")
    if not text.strip():
        return text

    # Часто в Polygon-пакете в plain-тексте лимиты склеиваются в одну строку.
    glued_tokens = [
        "стандартный вводстандартный вывод1 секунда256 мегабайт",
        "standard inputstandard output1 second256 megabytes",
    ]
    for token in glued_tokens:
        text = text.replace(token, "")

    # Если в statement почти нет TeX-команд, приводим к аккуратному plain-LaTeX блоку.
    has_tex = bool(re.search(r"\\(section|subsection|begin|end|item|textbf|emph|frac|sum|cdot|le|ge)", text))
    if not has_tex:
        lines = [line.rstrip() for line in text.splitlines()]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n\n".join(line for line in lines if line.strip())
    return text


def _find_problem_xml(root):
    direct = os.path.join(root, "problem.xml")
    if os.path.isfile(direct):
        return direct
    for current, _, files in os.walk(root):
        if "problem.xml" in files:
            return os.path.join(current, "problem.xml")
    return None


def _xml_title(xml_root):
    for node in xml_root.findall(".//name"):
        lang = (node.get("language") or node.get("lang") or "").lower()
        value = node.get("value") or node.get("title") or (node.text or "").strip()
        if value and lang in ("russian", "ru", ""):
            return value
    return xml_root.get("name") or xml_root.get("short-name") or "Imported Polygon task"


def _test_visibility(xml_root, idx):
    tests = xml_root.findall(".//test")
    if idx - 1 >= len(tests):
        return "open" if idx <= 2 else "private"
    sample = (tests[idx - 1].get("sample") or tests[idx - 1].get("visibility") or "").lower()
    return "open" if sample in ("true", "open", "sample", "yes", "1") else "private"


def _discover_tests(root, xml_root):
    tests_dir = os.path.join(root, "tests")
    if not os.path.isdir(tests_dir):
        raise PolygonImportError("tests directory not found")

    pairs = []
    files = [name for name in os.listdir(tests_dir) if os.path.isfile(os.path.join(tests_dir, name))]
    used = set()

    for name in sorted(files, key=_natural_key):
        if name in used or name.endswith((".a", ".out")):
            continue
        base, ext = os.path.splitext(name)
        answer_names = []
        if ext == ".in":
            answer_names.append(base + ".out")
        answer_names.extend([name + ".a", base + ".a"])
        answer_name = next((candidate for candidate in answer_names if candidate in files), None)
        if not answer_name:
            continue
        used.add(name)
        used.add(answer_name)
        idx = len(pairs) + 1
        pairs.append({
            "input": _read_text(os.path.join(tests_dir, name)),
            "output": _read_text(os.path.join(tests_dir, answer_name)),
            "visibility": _test_visibility(xml_root, idx),
            "group": 1,
            "subtask": 1,
            "points": 0,
        })

    if not pairs:
        raise PolygonImportError("no tests with answers found")
    return pairs


def parse_polygon_package(extracted_dir, task_id):
    problem_xml = _find_problem_xml(extracted_dir)
    if not problem_xml:
        raise PolygonImportError("problem.xml not found")

    root_dir = os.path.dirname(problem_xml)
    try:
        xml_root = ET.parse(problem_xml).getroot()
    except ET.ParseError as e:
        raise PolygonImportError(f"problem.xml parse failed: {e}") from e

    statement_tex = _copy_text_if_exists(root_dir, [
        "statement/russian.tex",
        "statements/russian.tex",
        "statements/russian/problem.tex",
        "statements/ru/problem.tex",
        "statement/problem.tex",
    ])
    if not statement_tex.strip():
        raise PolygonImportError("russian statement tex not found")
    statement_tex = _normalize_statement_tex(statement_tex)

    tests = _discover_tests(root_dir, xml_root)

    meta = {
        "id": task_id,
        "title": _xml_title(xml_root),
        "difficulty": "",
        "language": "cpp",
        "type": "",
        "tags": [],
        "taskType": "standard",
        "groups": [{
            "id": 1,
            "name": "group 1",
            "points": 100,
            "dependencies": [],
            "tests": [],
        }],
    }

    files = {
        "statement": statement_tex,
        "code": "",
        "solution": _copy_text_if_exists(root_dir, [
            "solutions/main.cpp",
            "solutions/accepted.cpp",
            "solutions/solution.cpp",
            "main.cpp",
        ]),
        "generator": _copy_text_if_exists(root_dir, [
            "generator/gen.cpp",
            "generators/gen.cpp",
            "files/gen.cpp",
        ]),
        "validator": _copy_text_if_exists(root_dir, [
            "validator/validator.cpp",
            "validators/validator.cpp",
            "files/validator.cpp",
        ]),
        "checker": _copy_text_if_exists(root_dir, [
            "checker/checker.cpp",
            "checkers/checker.cpp",
            "files/checker.cpp",
        ]),
    }

    return {
        "meta": meta,
        "files": files,
        "tests": tests,
    }
