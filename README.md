![BIMO Run Python](https://github.com/user-attachments/assets/bfba335f-8ee6-4665-8fc6-f75f4372acd3)

# BIMO Run Python Scripts

Community-maintained Revit automation scripts for [BIMO Run Python](https://bimo.tools/docs/library/run-python). The repository is designed for both direct use by Revit users and machine discovery by AI agents that execute approved scripts through BIMO MCP.

## Quick start

1. Download or clone this repository.
2. In Revit, open **BIMO > Run Python** and create a preset.
3. Select the engine declared for the script in [`catalog.json`](catalog.json).
4. Leave the inline **Script** field empty and set **Script file** to the `.py` file.
5. Add the documented `IN` values, prepare the required selection, and run the preset.

BIMO hosts the Python engine inside Revit, so users do not need a separate local Python installation just to run these scripts. Scripts that modify a model manage their own Revit transactions.

## Script catalog

| Script | Category | Engine | Risk |
| --- | --- | --- | --- |
| [Import image to active view](documentation/import_image_to_active_view.md) | Documentation | IronPython | Writes model and optionally copies a file |
| [Create Toposolid from model lines](modeling/create_toposolid_from_model_lines.md) | Modeling | IronPython | Writes model |
| [Create model-line contour from linked STL slice](modeling/create_model_line_contour_from_linked_stl_slice.md) | Modeling | IronPython | Writes model and optionally reads local assemblies |
| [Calculate selected lines length](miscellaneous/calculate_selected_lines_length_mm.md) | Miscellaneous | IronPython | Read-only |
| [Calculate element volume](miscellaneous/calculate_element_volume.md) | Miscellaneous | IronPython | Read-only |
| [Delete BIMO preview rays](miscellaneous/Delete_BIMO_PreviewRays_DirectShapes.md) | Miscellaneous | IronPython | Deletes elements |

The authoritative machine-readable index is [`catalog.json`](catalog.json). Its contract is defined by [`schemas/catalog.schema.json`](schemas/catalog.schema.json).

## Repository structure

```text
catalog.json                  Machine-readable script index
schemas/catalog.schema.json  Catalog JSON Schema
docs/decisions/              Durable algorithm and architecture decisions
documentation/               View documentation and image scripts
modeling/                     Model-creation and editing scripts
miscellaneous/                General-purpose scripts
tools/validate_catalog.py     Dependency-free repository validator
.github/workflows/            Continuous validation
```

Every executable script has a paired Markdown file explaining selection requirements, inputs, output, supported Revit versions, and model-change risk. Existing script paths are kept stable so saved BIMO presets do not break.

## Using the catalog from an AI agent

An agent should:

1. Filter `catalog.json` by category, tags, engine, Revit version, and risk.
2. Read the script documentation before execution.
3. Confirm required selection and inputs.
4. Treat `write` and `destructive` scripts as model-changing operations requiring explicit approval.
5. Load the exact file referenced by `path` and execute it through the supported BIMO Run Python or MCP operation.
6. Return the script's `OUT` value or execution error without claiming success before Revit confirms it.

The catalog helps discovery; it is not an execution allowlist or a security boundary. Review scripts before running them and use a test model for model-changing operations.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the script contract and submission checklist. Validate changes locally with:

```shell
python tools/validate_catalog.py
```

The same check runs in GitHub Actions.

## License

Distributed under the [MIT License](LICENSE).
