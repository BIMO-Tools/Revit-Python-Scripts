"""Validate the BIMO Run Python script catalog without third-party packages."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog.json"

SCRIPT_FIELDS = {
    "id",
    "name",
    "summary",
    "category",
    "path",
    "documentation",
    "engine",
    "revit",
    "risk",
    "requiresActiveDocument",
    "selection",
    "inputs",
    "output",
    "tags",
}
ENGINES = {"ironpython", "dynamo-cpython3"}
RISKS = {"read", "write", "destructive"}
OUTPUT_FORMATS = {"text", "json", "object"}
INPUT_TYPES = {
    "string",
    "number-string",
    "integer-string",
    "boolean-string",
    "json-string",
}


def load_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exception:
        errors.append(f"{path.relative_to(ROOT)}: {exception}")
        return None


def repository_path(value: object, field: str, script_id: str, errors: list[str]):
    if not isinstance(value, str) or not value:
        errors.append(f"{script_id}: {field} must be a non-empty string")
        return None

    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        errors.append(f"{script_id}: {field} must be a repository-relative POSIX path")
        return None

    return ROOT / path


def validate_inputs(script_id: str, inputs: object, errors: list[str]) -> None:
    if not isinstance(inputs, list):
        errors.append(f"{script_id}: inputs must be an array")
        return

    indexes = []
    for input_value in inputs:
        if not isinstance(input_value, dict):
            errors.append(f"{script_id}: every input must be an object")
            continue

        required = {"index", "name", "type", "required", "description"}
        missing = required - input_value.keys()
        if missing:
            errors.append(f"{script_id}: input is missing {sorted(missing)}")

        index = input_value.get("index")
        if not isinstance(index, int) or index < 0:
            errors.append(f"{script_id}: input index must be a non-negative integer")
        else:
            indexes.append(index)

        if input_value.get("type") not in INPUT_TYPES:
            errors.append(f"{script_id}: unsupported input type {input_value.get('type')!r}")

        if not isinstance(input_value.get("required"), bool):
            errors.append(f"{script_id}: input required must be boolean")

    if indexes != list(range(len(indexes))):
        errors.append(f"{script_id}: input indexes must be contiguous and ordered from zero")


def validate_script(script: object, seen_ids: set[str], seen_paths: set[str], errors: list[str]):
    if not isinstance(script, dict):
        errors.append("Every scripts entry must be an object")
        return

    script_id = script.get("id", "<missing-id>")
    missing = SCRIPT_FIELDS - script.keys()
    extra = script.keys() - SCRIPT_FIELDS
    if missing:
        errors.append(f"{script_id}: missing fields {sorted(missing)}")
    if extra:
        errors.append(f"{script_id}: unknown fields {sorted(extra)}")

    if not isinstance(script_id, str) or not script_id:
        errors.append("Script id must be a non-empty string")
    elif script_id in seen_ids:
        errors.append(f"Duplicate script id: {script_id}")
    else:
        seen_ids.add(script_id)

    if script.get("engine") not in ENGINES:
        errors.append(f"{script_id}: unsupported engine {script.get('engine')!r}")
    if script.get("risk") not in RISKS:
        errors.append(f"{script_id}: unsupported risk {script.get('risk')!r}")
    if not isinstance(script.get("requiresActiveDocument"), bool):
        errors.append(f"{script_id}: requiresActiveDocument must be boolean")

    category = script.get("category")
    script_path = repository_path(script.get("path"), "path", script_id, errors)
    documentation_path = repository_path(
        script.get("documentation"), "documentation", script_id, errors
    )

    if script_path is not None:
        relative_path = script_path.relative_to(ROOT).as_posix()
        if relative_path in seen_paths:
            errors.append(f"Duplicate script path: {relative_path}")
        else:
            seen_paths.add(relative_path)

        if script_path.suffix != ".py":
            errors.append(f"{script_id}: path must end with .py")
        if not script_path.is_file():
            errors.append(f"{script_id}: script file does not exist: {relative_path}")
        if script_path.parts[-2] != category:
            errors.append(f"{script_id}: category must match the script directory")

    if documentation_path is not None:
        if documentation_path.suffix != ".md":
            errors.append(f"{script_id}: documentation must end with .md")
        if not documentation_path.is_file():
            errors.append(
                f"{script_id}: documentation file does not exist: "
                f"{documentation_path.relative_to(ROOT).as_posix()}"
            )
        if script_path is not None and documentation_path.stem != script_path.stem:
            errors.append(f"{script_id}: script and documentation stems must match")

    revit = script.get("revit")
    if not isinstance(revit, dict):
        errors.append(f"{script_id}: revit must be an object")
    else:
        minimum = revit.get("minimum")
        tested = revit.get("tested")
        if not isinstance(minimum, int) or minimum < 2024:
            errors.append(f"{script_id}: revit.minimum must be an integer >= 2024")
        if not isinstance(tested, list) or any(not isinstance(v, int) for v in tested):
            errors.append(f"{script_id}: revit.tested must be an integer array")
        elif isinstance(minimum, int) and any(v < minimum for v in tested):
            errors.append(f"{script_id}: tested versions cannot precede revit.minimum")

    selection = script.get("selection")
    if not isinstance(selection, dict):
        errors.append(f"{script_id}: selection must be an object")
    elif not isinstance(selection.get("required"), bool) or not selection.get("description"):
        errors.append(f"{script_id}: selection requires boolean required and description")

    validate_inputs(script_id, script.get("inputs"), errors)

    output = script.get("output")
    if not isinstance(output, dict):
        errors.append(f"{script_id}: output must be an object")
    elif output.get("format") not in OUTPUT_FORMATS or not output.get("description"):
        errors.append(f"{script_id}: output requires a supported format and description")

    tags = script.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        errors.append(f"{script_id}: tags must be a string array")
    elif len(tags) != len(set(tags)):
        errors.append(f"{script_id}: tags must be unique")


def validate_python(path: Path, errors: list[str]) -> None:
    try:
        source = path.read_text(encoding="utf-8-sig")
        compile(source, str(path), "exec")
    except (OSError, SyntaxError) as exception:
        errors.append(f"{path.relative_to(ROOT).as_posix()}: {exception}")


def main() -> int:
    errors: list[str] = []
    catalog = load_json(CATALOG_PATH, errors)
    load_json(ROOT / "schemas" / "catalog.schema.json", errors)

    if not isinstance(catalog, dict):
        scripts = []
    else:
        if catalog.get("version") != 1:
            errors.append("catalog.json: version must be 1")
        if catalog.get("$schema") != "schemas/catalog.schema.json":
            errors.append("catalog.json: $schema must reference schemas/catalog.schema.json")
        scripts = catalog.get("scripts")
        if not isinstance(scripts, list) or not scripts:
            errors.append("catalog.json: scripts must be a non-empty array")
            scripts = []

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for script in scripts:
        validate_script(script, seen_ids, seen_paths, errors)

    repository_scripts = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.py")
        if path.relative_to(ROOT).parts[0] != "tools"
    }

    uncatalogued = repository_scripts - seen_paths
    missing_from_disk = seen_paths - repository_scripts
    if uncatalogued:
        errors.append(f"Uncatalogued scripts: {sorted(uncatalogued)}")
    if missing_from_disk:
        errors.append(f"Catalog paths missing from disk: {sorted(missing_from_disk)}")

    for path in sorted(repository_scripts | {"tools/validate_catalog.py"}):
        validate_python(ROOT / path, errors)

    if errors:
        print("Catalog validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Catalog validation passed for {len(scripts)} scripts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
