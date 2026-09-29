import os
import re
import subprocess  # nosec B404
import sys
from pathlib import Path
from urllib.parse import urlparse

"""Sanitize uv.lock so it matches what would be produced without a custom UV_DEFAULT_INDEX.

Current goals:
- Ensure registry lines read: source = { registry = "https://pypi.org/simple" }
- Ensure distribution (sdist / wheel) URLs point to https://files.pythonhosted.org/packages/...
- Convert any URLs that still reference the custom index host (optionally with /simple) to the
  canonical PyPI hosts, without introducing path duplication like /packages/packages/.
- Remove [[tool.uv.index]] blocks from pyproject.toml.

We purposefully avoid a blanket host replacement to prevent corrupting the structure of
wheel/sdist paths and to keep the two canonical hosts distinct: pypi.org (index) and
files.pythonhosted.org (distributions).
"""

PROJECT_PATH = Path(__file__).parent.parent
LOCK_PATH = PROJECT_PATH / "uv.lock"
PYPROJECT_PATH = PROJECT_PATH / "pyproject.toml"

changed = False

uv_default_index = os.environ.get("UV_DEFAULT_INDEX")
custom_host_pattern = None
if uv_default_index:
    parsed = urlparse(uv_default_index)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or ""
    if path.endswith("/simple"):
        path = path[: -len("/simple")]
    if path != "/":
        path = path.rstrip("/")
    custom_host_pattern = f"{parsed.scheme}://{host}{port}{path}".rstrip("/")


def sanitize_lock(content: str) -> str:
    original = content

    def _fix_registry(match: re.Match) -> str:
        url = match.group(1)
        if url != "https://pypi.org/simple":
            return 'source = { registry = "https://pypi.org/simple" }'
        return match.group(0)

    content = re.sub(
        r'source = { registry = "(https?://[^" ]+/simple)" }', _fix_registry, content
    )

    if custom_host_pattern:
        escaped = re.escape(custom_host_pattern)
        dist_pattern = re.compile(
            r'(url\s*=\s*")' + escaped + r"(?:/simple)?" r'(/packages/[^"\s]+)"'
        )
        content = dist_pattern.sub(r'\1https://files.pythonhosted.org\2"', content)

    content = re.sub(
        r"https://files\.pythonhosted\.org//+(packages/)",
        r"https://files.pythonhosted.org/\1",
        content,
    )
    while "https://files.pythonhosted.org/packages/packages/" in content:
        content = content.replace(
            "https://files.pythonhosted.org/packages/packages/",
            "https://files.pythonhosted.org/packages/",
        )

    content = content.replace(
        'source = { registry = "https://files.pythonhosted.org/simple" }',
        'source = { registry = "https://pypi.org/simple" }',
    )

    return content if content != original else original


def main() -> int:  # pragma: no cover - thin wrapper
    """Sanitize lock/index metadata and return 1 when files were changed."""
    global changed
    if LOCK_PATH.exists():
        lock_content = LOCK_PATH.read_text(encoding="utf-8")
        sanitized_lock = sanitize_lock(lock_content)

        if sanitized_lock != lock_content:
            LOCK_PATH.write_text(sanitized_lock, encoding="utf-8")
            subprocess.run(["git", "add", str(LOCK_PATH)], check=True)  # nosec
            print(
                "Sanitized uv.lock to canonical PyPI registry and distribution URLs; re-staged."
            )
            changed = True

    if PYPROJECT_PATH.exists():
        pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
        sanitized_pyproject = re.sub(
            r"(?sm)^\[\[tool\.uv\.index]](?:\n.*?)*(?=^\[|\Z)", "", pyproject
        )
        if sanitized_pyproject != pyproject:
            PYPROJECT_PATH.write_text(sanitized_pyproject, encoding="utf-8")
            subprocess.run(["git", "add", str(PYPROJECT_PATH)], check=True)  # nosec
            print(
                "Removed [[tool.uv.index]] section(s) from pyproject.toml and re-staged."
            )
            changed = True

    return 1 if changed else 0


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    sys.exit(main())
