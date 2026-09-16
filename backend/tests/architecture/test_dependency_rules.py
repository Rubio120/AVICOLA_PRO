from __future__ import annotations

import ast
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "avicola_pro"
MODULE_ROOT = SOURCE_ROOT / "modules"
EXPECTED_MODULES = {
    "audit",
    "catalog",
    "costing",
    "identity",
    "inventory",
    "parties",
    "production",
    "purchasing",
    "reporting",
    "sales",
    "settings",
    "treasury",
}
EXPECTED_LAYERS = {"domain", "application", "infrastructure", "api"}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def violations(path: Path) -> list[str]:
    imports = imported_modules(path)
    layer = path.parent.name
    violations_found: list[str] = []
    if layer == "domain":
        domain_forbidden = (
            "fastapi",
            "pydantic",
            "sqlalchemy",
            "avicola_pro.shared.infrastructure",
            "avicola_pro.shared.api",
        )
        violations_found.extend(name for name in imports if name.startswith(domain_forbidden))
    if layer == "application":
        application_forbidden = ("fastapi", "sqlalchemy", ".infrastructure", ".api")
        violations_found.extend(
            name
            for name in imports
            if name.startswith(application_forbidden) or any(part in name for part in application_forbidden[2:])
        )
    if "modules" in path.parts:
        current_module = path.parts[path.parts.index("modules") + 1]
        for name in imports:
            prefix = "avicola_pro.modules."
            if name.startswith(prefix):
                parts = name.split(".")
                imported_module = parts[2]
                if imported_module != current_module and "infrastructure" in parts:
                    violations_found.append(name)
    return violations_found


def test_illegal_domain_import_fixture_is_detected(tmp_path: Path) -> None:
    layer = tmp_path / "domain"
    layer.mkdir()
    source = layer / "illegal.py"
    source.write_text("from fastapi import Request\n", encoding="utf-8")

    assert violations(source) == ["fastapi"]


def test_all_approved_modules_have_hexagonal_layers() -> None:
    actual_modules = {path.name for path in MODULE_ROOT.iterdir() if path.is_dir()}

    assert actual_modules == EXPECTED_MODULES
    for module_name in EXPECTED_MODULES:
        actual_layers = {path.name for path in (MODULE_ROOT / module_name).iterdir() if path.is_dir()}
        assert actual_layers == EXPECTED_LAYERS


def test_project_source_has_no_forbidden_layer_imports() -> None:
    found = {
        str(path.relative_to(SOURCE_ROOT)): violations(path) for path in SOURCE_ROOT.rglob("*.py") if violations(path)
    }

    assert found == {}
