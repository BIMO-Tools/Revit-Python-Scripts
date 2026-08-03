# Contributing scripts

Contributions should remain easy to run manually through BIMO Run Python and predictable enough for future AI-agent discovery through BIMO MCP.

## Add a script

1. Choose an existing category or create a focused lowercase category folder.
2. Add a descriptively named `lower_snake_case.py` file.
3. Add a Markdown file with the same stem.
4. Register the script in `catalog.json`.
5. Run `python tools/validate_catalog.py`.
6. Describe any Revit testing performed in the pull request. Do not mark an untested version as tested.

Existing files with historical naming are allowed to keep their paths so saved BIMO presets continue to work.

## BIMO script contract

New scripts should:

- declare either `ironpython` or `dynamo-cpython3` in the catalog;
- use BIMO-provided Revit globals only when the selected engine supports them;
- read optional positional values from `IN` and document every index;
- assign a concise value to `OUT` for predictable manual and MCP results;
- validate required selection and inputs before changing the model;
- avoid modal prompts and hidden dependencies when preselection or `IN` can be used;
- open their own Revit transaction for model changes;
- roll back a started transaction when an operation fails;
- allow exceptions to reach BIMO so failed executions are not reported as successful;
- avoid secrets, credentials, machine-specific paths, and unrequested network access.

IronPython scripts intended for BIMO may use these globals:

| Global | Value |
| --- | --- |
| `__doc__` | Active Revit `Document` |
| `__uidoc__` | Active Revit `UIDocument` |
| `__revit__`, `__uiapp__` | Active `UIApplication` |
| `__selection__` | Active Revit selection object |
| `IN` | Positional input list |
| `OUT` | Script result assigned by the script |

## Documentation contract

The paired Markdown file must state:

- purpose and expected user outcome;
- engine and minimum Revit version;
- whether the script reads, writes, or deletes model data;
- active-document and selection requirements;
- every `IN` value, type, order, and default;
- `OUT` format;
- important limitations and a manual Revit test scenario.

## Catalog risk levels

- `read`: inspects model state without intentionally changing it;
- `write`: creates or modifies model state;
- `destructive`: deletes elements or performs changes that are difficult to reverse.

Risk metadata is guidance for users and agents. It does not replace BIMO authorization, code review, backups, or Revit transaction safety.

## Validation

Run:

```shell
python tools/validate_catalog.py
```

The validator checks JSON syntax, required metadata, unique IDs and paths, paired documentation, catalog coverage for every script, and CPython-parsable syntax. It does not execute Revit API code or prove runtime compatibility.
