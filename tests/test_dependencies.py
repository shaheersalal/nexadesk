"""
Every third-party module app/ imports must be declared in requirements.txt.

This bug class has bitten twice. `twilio` was imported in four places and never
declared, so the first real phone call would have died on ImportError. Then
thirteen more — pdfplumber, python-docx, openpyxl, beautifulsoup4 and the Google
Calendar libraries among them — meant document upload and appointment booking
were broken in production while the app booted perfectly.

Both slipped through for the same reason: the imports are function-local, so
nothing fails at import time, no test touches the path, and the only symptom is
a feature that quietly does not work for real users.

Modules whose import is genuinely optional are listed in OPTIONAL below, and
each one has to actually be guarded — the test checks that too, so a module
cannot be exempted just by adding its name here.
"""
import ast
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "app"

# import name -> distribution name on PyPI
DISTRIBUTION = {
    "jose": "python-jose",
    "pptx": "python-pptx",
    "multipart": "python-multipart",
    "deep_translator": "deep-translator",
    "qdrant_client": "qdrant-client",
    "pydantic_settings": "pydantic-settings",
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
    "docx": "python-docx",
    "magic": "python-magic",
    "googleapiclient": "google-api-python-client",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "google": "google-auth",
    "dotenv": "python-dotenv",
    "jwt": "pyjwt",
    "yaml": "pyyaml",
}

# Optional by design. Each needs a system binary or is far too large to ship,
# and each import site must degrade rather than raise ImportError at the user.
OPTIONAL = {
    "pytesseract",   # needs the tesseract binary
    "pdf2image",     # needs poppler
    "unstructured",  # hundreds of MB of dependency
    "magic",         # needs libmagic; already guarded with a try/except
    "PIL",           # only reachable through image OCR, which needs tesseract
}


def _declared() -> set[str]:
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    names = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[<>=!\[;]", line, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def _imported() -> dict[str, set[pathlib.Path]]:
    found: dict[str, set[pathlib.Path]] = {}
    for path in APP.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in sys.stdlib_module_names or n == "app":
                    continue
                found.setdefault(n, set()).add(path)
    return found


def test_every_imported_package_is_declared():
    declared = _declared()
    missing = {}
    for module, paths in _imported().items():
        if module in OPTIONAL:
            continue
        dist = DISTRIBUTION.get(module, module).lower()
        if dist not in declared:
            missing[dist] = sorted(str(p.relative_to(ROOT)) for p in paths)
    assert not missing, (
        "Imported but not in requirements.txt — these fail at runtime in "
        f"production while the app boots fine:\n{missing}"
    )


@pytest.mark.parametrize("module", sorted(OPTIONAL - {"magic"}))
def test_optional_imports_degrade_instead_of_raising(module):
    """
    An optional dependency must be caught at its import site.

    Otherwise "optional" means the user sees `No module named pdf2image` as the
    error on their upload, which tells an estate agent nothing about what to do.
    """
    for path in APP.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        if f"import {module}" not in src:
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            names = (
                [a.name.split(".")[0] for a in node.names]
                if isinstance(node, ast.Import)
                else [(node.module or "").split(".")[0]]
            )
            if module not in names:
                continue
            guarded = any(
                isinstance(anc, ast.Try)
                and any(
                    isinstance(h.type, ast.Name) and h.type.id in {"ImportError", "Exception"}
                    or isinstance(h.type, ast.Tuple)
                    for h in anc.handlers
                )
                for anc in ast.walk(tree)
                if isinstance(anc, ast.Try) and node in ast.walk(anc)
            )
            assert guarded, (
                f"{path.relative_to(ROOT)}:{node.lineno} imports optional "
                f"'{module}' without catching ImportError — the raw error "
                "reaches the user as their upload's failure message."
            )


def test_magic_is_guarded():
    """python-magic needs libmagic; detector.py falls back to file extensions."""
    src = (APP / "rag" / "detector.py").read_text(encoding="utf-8")
    assert "except ImportError" in src and "_HAS_MAGIC" in src
