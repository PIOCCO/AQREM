import re
from dataclasses import dataclass

LANGUAGE_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".tf": "hcl",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
}


@dataclass
class CodeSymbol:
    name: str
    kind: str
    line_start: int
    line_end: int


PY_FUNC = re.compile(r"^(\s*)def\s+([a-zA-Z_][\w]*)\s*\(", re.MULTILINE)
PY_CLASS = re.compile(r"^(\s*)class\s+([a-zA-Z_][\w]*)\s*[:\(]", re.MULTILINE)
TF_RESOURCE = re.compile(r"^resource\s+\"([^\"]+)\"\s+\"([^\"]+)\"\s*\{", re.MULTILINE)


def detect_language(file_path: str) -> str | None:
    for ext, lang in LANGUAGE_BY_EXT.items():
        if file_path.lower().endswith(ext):
            return lang
    return None


def extract_symbols(content: str, language: str | None) -> list[CodeSymbol]:
    symbols: list[CodeSymbol] = []
    if language == "python":
        for match in PY_CLASS.finditer(content):
            line = content.count("\n", 0, match.start()) + 1
            symbols.append(CodeSymbol(name=match.group(2), kind="class", line_start=line, line_end=line))
        for match in PY_FUNC.finditer(content):
            line = content.count("\n", 0, match.start()) + 1
            symbols.append(CodeSymbol(name=match.group(2), kind="function", line_start=line, line_end=line))
    elif language == "hcl":
        for match in TF_RESOURCE.finditer(content):
            line = content.count("\n", 0, match.start()) + 1
            name = f'{match.group(1)}.{match.group(2)}'
            symbols.append(CodeSymbol(name=name, kind="resource", line_start=line, line_end=line))
    return symbols
