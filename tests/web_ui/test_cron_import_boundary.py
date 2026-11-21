"""Check cron imports against the source and dependencies copied into its image."""

import ast
from pathlib import Path, PurePosixPath
import shlex
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[2]
CRON_ROOT = REPO_ROOT / "katrain" / "cron"
IMAGE_THIRD_PARTY = {
    "apscheduler": "apscheduler",
    "bs4": "beautifulsoup4",
    "chardet": "chardet",
    "httpx": "httpx",
    "sqlalchemy": "sqlalchemy",
    "lxml": "lxml",
    "psycopg2": "psycopg2-binary",
    "pydantic": "pydantic",
    "pypinyin": "pypinyin",
}


def _cron_imports():
    for path in sorted(CRON_ROOT.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                yield from ((alias.name, (), path) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                yield node.module, tuple(alias.name for alias in node.names), path


def _image_modules():
    modules = {"katrain"}  # Dockerfile.cron creates katrain/__init__.py.
    for line in (REPO_ROOT / "Dockerfile.cron").read_text().splitlines():
        if not line.startswith("COPY "):
            continue
        _, *sources, destination = shlex.split(line)
        for source in sources:
            path = REPO_ROOT / source
            target = PurePosixPath(destination)
            if path.is_dir():
                files = (target / child.relative_to(path) for child in path.rglob("*.py"))
            elif path.suffix == ".py":
                files = (target / path.name if destination.endswith("/") else target,)
            else:
                continue
            for file in files:
                parts = file.parent.parts if file.name == "__init__.py" else file.with_suffix("").parts
                modules.add(".".join(parts))
                modules.update(".".join(parts[:i]) for i in range(1, len(parts)))
    return modules


def _local_imports(module, names):
    yield module
    # A from-import can name a child module rather than a value on the package.
    package = REPO_ROOT.joinpath(*module.split("."))
    if package.is_dir():
        for name in names:
            child = package / name
            if child.is_dir() or child.with_suffix(".py").is_file():
                yield f"{module}.{name}"


def test_local_cron_imports_are_copied_into_image():
    available = _image_modules()
    offenders = {
        (name, str(path.relative_to(REPO_ROOT)))
        for module, names, path in _cron_imports()
        if module.split(".")[0] == "katrain"
        for name in _local_imports(module, names)
        if name not in available
    }
    assert not offenders, f"Local cron imports missing from Dockerfile.cron COPY: {sorted(offenders)}"


def test_third_party_cron_imports_are_installed_in_image():
    offenders = {
        (module, str(path.relative_to(REPO_ROOT)))
        for module, _, path in _cron_imports()
        if (root := module.split(".")[0]) != "katrain"
        and root not in sys.stdlib_module_names
        and root not in IMAGE_THIRD_PARTY
    }
    assert not offenders, f"Third-party cron imports missing from requirements-cron.txt: {sorted(offenders)}"


def _requirements():
    return [
        Requirement(line)
        for raw in (REPO_ROOT / "requirements-cron.txt").read_text().splitlines()
        if (line := raw.partition("#")[0].strip())
    ]


def test_cron_module_mapping_matches_requirements():
    declared = {canonicalize_name(requirement.name) for requirement in _requirements()}
    mapped = set(IMAGE_THIRD_PARTY.values())
    assert mapped == declared, f"Missing in mapping: {declared - mapped}; missing in requirements: {mapped - declared}"


def test_cron_sqlalchemy_keeps_psycopg2_as_default_postgresql_driver():
    """The cron image installs psycopg2, alongside SQLAlchemy 2.0."""
    sqlalchemy = next(requirement for requirement in _requirements() if requirement.name == "sqlalchemy")
    assert "2.0.0" in sqlalchemy.specifier
    assert "2.1.0" not in sqlalchemy.specifier
