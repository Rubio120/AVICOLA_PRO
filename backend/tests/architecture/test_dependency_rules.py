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
LAYER_DEPENDENCIES = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "infrastructure": {"domain", "application", "infrastructure"},
    "api": {"domain", "application", "api"},
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            imports.update(f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*")
    return imports


def violations(path: Path) -> list[str]:
    raw_imports = imported_modules(path)
    imports = {name for name in raw_imports if not any(name.startswith(other + ".") for other in raw_imports)}
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
                imported_layer = parts[3] if len(parts) > 3 and parts[3] in EXPECTED_LAYERS else None
                invalid_same_module = (
                    imported_module == current_module and imported_layer not in LAYER_DEPENDENCIES.get(layer, set())
                )
                invalid_cross_module = imported_module != current_module and (
                    layer in {"domain", "api"} or imported_layer in {"infrastructure", "api"}
                )
                if invalid_same_module or invalid_cross_module:
                    violations_found.append(name)
    return violations_found


def module_name(path: Path, source_root: Path = SOURCE_ROOT) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(("avicola_pro", *parts))


def import_cycles(paths: list[Path], source_root: Path = SOURCE_ROOT) -> list[list[str]]:
    names = {module_name(path, source_root): path for path in paths}
    graph = {
        name: {
            candidate
            for imported in imported_modules(path)
            for candidate in names
            if imported == candidate or imported.startswith(candidate + ".")
        }
        for name, path in names.items()
    }
    cycles: list[list[str]] = []
    active: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in active:
            cycle = active[active.index(name) :] + [name]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        if name in visited:
            return
        active.append(name)
        for dependency in sorted(graph[name]):
            visit(dependency)
        active.pop()
        visited.add(name)

    for name in sorted(graph):
        visit(name)
    return cycles


def test_illegal_domain_import_fixture_is_detected(tmp_path: Path) -> None:
    layer = tmp_path / "domain"
    layer.mkdir()
    source = layer / "illegal.py"
    source.write_text("from fastapi import Request\n", encoding="utf-8")

    assert violations(source) == ["fastapi"]


def test_same_module_reverse_layer_imports_are_detected(tmp_path: Path) -> None:
    source = tmp_path / "modules" / "inventory" / "domain" / "illegal.py"
    source.parent.mkdir(parents=True)
    source.write_text("from avicola_pro.modules.inventory.infrastructure import repository\n", encoding="utf-8")

    assert violations(source) == ["avicola_pro.modules.inventory.infrastructure"]


def test_internal_import_cycle_fixture_is_detected(tmp_path: Path) -> None:
    package = tmp_path / "sample"
    package.mkdir()
    first = package / "first.py"
    second = package / "second.py"
    first.write_text("from avicola_pro.sample import second\n", encoding="utf-8")
    second.write_text("from avicola_pro.sample import first\n", encoding="utf-8")

    assert import_cycles([first, second], tmp_path) == [
        ["avicola_pro.sample.first", "avicola_pro.sample.second", "avicola_pro.sample.first"]
    ]


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


def test_project_source_has_no_internal_import_cycles() -> None:
    assert import_cycles(list(SOURCE_ROOT.rglob("*.py"))) == []
