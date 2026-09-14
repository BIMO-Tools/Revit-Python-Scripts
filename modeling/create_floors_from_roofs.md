# Create Floors from shape-edited roofs

Creates one native architectural `Floor` for each explicitly selected Basic Roof,
with its layers, elevation, shape points, split lines, sketch holes and hosted
vertical openings. Source roofs and their annotations are retained.

## Compatibility and scope

- BIMO engine: **IronPython**; minimum Revit API version: **2024**.
- Active editable project required, with no transaction already open.
- Exact catalog-script Revit testing: pending; see the pull request for current results.
- Only `FootPrintRoof` elements with enabled slab-shape editing, straight sketch
  and opening boundaries, planar solid faces, and no variable-thickness layer.
- Requires at least one architectural `FloorType` in the project.

The script does not convert extruded/curtain roofs, sloped roof sketches without
shape editing, curved boundaries, variable-layer roofs, shaft openings, or other
hosted families. Later Revit versions are not validated.

## Inputs

BIMO passes optional positional inputs as strings.

| Index | Name | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `IN[0]` | `dry_run` | boolean-string | `true` | `true` creates and checks trial elements, then rolls everything back; `false` keeps the new Floors. |
| `IN[1]` | `roof_ids` | string | empty | Comma-separated positive roof IDs in the active document. Empty uses the current selection. |

Every selected or specified element must be a supported roof. Invalid IDs and
mixed selections fail before model changes. An explicit ID list overrides the
selection. Empty input does **not** collect every roof in the project.

## Run through BIMO

1. Select the roofs to convert, or provide their IDs in `IN[1]`.
2. Choose **IronPython**, leave the inline Script field empty and point Script
   file at `create_floors_from_roofs.py`.
3. Run with `IN[0] = "true"`. Check the returned geometry report and warnings.
4. Run with `IN[0] = "false"` to retain the new Floors.
5. Inspect the results before manually removing any source roofs. Deleting a
   roof can also delete dimensions, spot slopes, alignments and hosted elements.

The same source works through the approved BIMO MCP Python execution operation.
No local Python installation or third-party geometry package is required in Revit.

## Model changes and other side effects

- Creates one Floor per source roof and one new FloorType per distinct RoofType
  per run. Copies the compound structure, including layer materials and thicknesses.
- Derives the new type from the lowest-ID architectural FloorType. Uncopied type
  properties retain that template's values. Existing types are never modified;
  a numeric suffix resolves name collisions.
- Keeps the roof's base level. Sets the Floor offset to the roof base offset plus
  the compound-structure thickness, then transfers shape elevations.
- Copies instance comments, mark, creation phase and demolition phase when set
  and writable. Other instance/type/shared parameters, worksets, design options,
  joins, attachments, hosted families, constraints and view overrides are not copied.
- Recreates curve-based hosted openings as **vertical** Floor openings and
  preserves inner sketch loops. Perpendicular openings are not a supported input;
  geometric mismatch causes rollback.
- Preserves both user-drawn and automatic non-boundary creases as explicit Floor
  split lines, which may change the later editing behaviour of automatic folds.
- Never deletes or modifies source roofs or their dependent annotations, and does
  not rehost spot slopes. Source and converted geometry overlap until the user
  removes or otherwise manages the sources.
- Does not save, synchronize or close the project, change selection or views,
  read/write files, access the network or show its own modal prompts.
- Warnings are collected in `OUT`; errors roll back the entire batch and propagate
  to BIMO. A committed run is grouped into one Revit Undo operation.
- Repeating a committed run creates additional Floors and types. It is not an
  update or duplicate-detection command.

## Geometry validation

The script compares bidirectional surface samples, solid volumes and total face
areas, including opening surfaces. It checks again after transaction commit and
before accepting the transaction group. Surface sampling is a practical check,
not a proof of exact solid equivalence.

- Maximum sampled surface distance: **0.01 mm**.
- Maximum volume difference: the greater of `1e-6 ft3` or `1e-6` of source volume.
- Maximum area difference: the greater of `1e-6 ft2` or `1e-6` of source surface area.
- Shape-point matching tolerance: `1e-6 ft`.

For a single planar top face, stored shape points may differ slightly from the
actual Revit surface. The script projects their heights onto that plane, reports
the adjustment, and rejects adjustments over **0.1 mm**. It preserves the existing
surface geometry rather than insisting on those inconsistent stored heights.

See [the algorithm decision record](../docs/decisions/0002-roof-to-floor-conversion.md)
for the reason for these checks and prototype measurements.

## Output

`OUT` is an object with `dry_run`, `floor_count`, `created_ids_are_persistent`,
`source_roofs_retained`, `warnings` and a per-roof `report` containing:

- source roof and new Floor IDs, plus source/target opening IDs;
- shape-vertex and explicit split-line counts;
- sampled surface distance and sample count;
- source/result volumes in cubic feet and their difference;
- source/result surface areas in square feet;
- vertex matching error and stored-point adjustment in millimetres.

In a dry run, `floor_count` means successfully validated trial Floors. Their IDs
and opening IDs are **not persistent** after rollback. Failures are execution
errors, never successful results containing `ok: false`.

## Manual Revit test scenario

Use a separate test copy containing several shape-edited polygonal roofs, an inner
sketch hole, vertical Opening Cuts crossing the outer boundary, edge points and
split lines. Include a nearly coplanar quadrilateral and spot-slope annotations.

1. Record counts of Floors, FloorTypes, roofs, openings and spot dimensions.
2. Run dry mode and confirm every count is unchanged.
3. Run commit mode and confirm one Floor per roof, one type per RoofType, and the
   expected new opening count; original roofs and annotations must remain.
4. Inspect top/bottom geometry, slope direction, thickness, materials and openings.
5. Test empty/mixed selection and missing IDs; expect an error with no new elements.
6. Exercise multiple RoofTypes and a deliberately unsupported input. Additional
   layers, phase transfer and failure-processor error rollback require separate cases.
