# Revit Python Scripts Agent Instructions

This repository is a reviewed catalog of reusable Revit scripts for BIMO Run Python and BIMO MCP. Agents may propose focused, generally useful scripts, but must preserve predictable discovery, approval, and execution contracts.

## Before changing files

1. Read [`README.md`](README.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md) completely.
2. Inspect [`catalog.json`](catalog.json), the paired documentation for similar scripts, and [`schemas/catalog.schema.json`](schemas/catalog.schema.json).
3. Read applicable long-lived context under [`docs/decisions`](docs/decisions/README.md) before changing a non-obvious algorithm or its defaults.
4. Keep one focused user outcome per pull request. Do not add speculative frameworks or unrelated cleanup.
5. Work on a branch and open a draft pull request. Do not push script changes directly to `main`.

## Adding a script

- Choose an existing focused lowercase category or create one when no category fits.
- Add a descriptively named `lower_snake_case.py` file and a Markdown file with the same stem.
- Register the script in `catalog.json` and add it to the human-readable table in `README.md`.
- Follow the BIMO globals, `IN`, `OUT`, validation, transaction, rollback, and exception rules in [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Document every model, file-system, network, selection, and input side effect. Avoid network access, credentials, machine-specific paths, and modal prompts unless the user explicitly requires them and the repository contract supports them.
- Keep existing script paths stable because saved BIMO presets may reference them.
- Never claim a Revit version is tested unless the exact repository script was run successfully in that version. Record partial or manual validation honestly in the pull request.

## Recording decisions

- Store durable algorithm and architecture context under [`docs/decisions`](docs/decisions/README.md).
- Record the problem, invariants, evaluated alternatives, measured evidence, accepted decision, limitations, and remaining work. Do not store chat transcripts or unfiltered reasoning.
- Link decision records to the related issue, pull request, implementation, and user guide. Update or supersede the relevant record when later evidence changes the decision.
- Keep user-facing execution instructions in the paired script documentation and keep this file as a concise routing entry point.

## Required validation

Run:

```shell
python tools/validate_catalog.py
```

Also review the final diff for uncatalogued scripts, missing paired documentation, unrelated files, unsafe defaults, and model-changing behavior that is not represented by the catalog risk and documentation.

The validator checks repository structure and CPython-parsable syntax; it does not prove Revit API compatibility. Model-changing scripts still require explicit BIMO approval and a manual test in an appropriate Revit model.
