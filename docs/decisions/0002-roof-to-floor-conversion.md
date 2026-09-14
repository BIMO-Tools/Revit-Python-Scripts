# 0002 — Roof-to-Floor geometry conversion

- Status: Accepted for the current draft
- Date: 2026-09-14
- Related issue: [#6](https://github.com/BIMO-Tools/Revit-Python-Scripts/issues/6)
- Implementation: [create_floors_from_roofs.py](../../modeling/create_floors_from_roofs.py)
- User guide: [Create Floors from roofs](../../modeling/create_floors_from_roofs.md)

## Goal and invariants

Reuse a conversion developed through BIMO MCP to create native editable Floors
from shape-edited Basic Roofs. Preserve the existing surface, compound layers,
levels, inner sketch contours and vertical hosted openings. Require explicit
selection or IDs, retain originals and annotations, and roll back the entire
batch if an API operation or geometry check fails.

## Evidence from the original Revit 2024 prototype

The prototype created 16 Floors from 16 Basic FootPrintRoofs of one RoofType with
a 152.4 mm constant structural layer. Six hosted Opening Cuts were recreated;
one additional opening was an inner sketch loop. The largest Opening Cut had
75 straight boundary curves. The source included boundary/edge vertices and
both user-drawn and automatic creases.

A removal trial revealed 45 dependent Spot Slopes, 186 automatic sketch
dimensions and one alignment constraint. That trial was rolled back. Final
creation kept every source and annotation; the user subsequently removed the
sources manually. The reusable script deliberately has no deletion mode.

## Evaluated approaches and decisions

| Approach | Evidence | Decision |
| --- | --- | --- |
| Recreate sketch, shape points, non-boundary creases and hosted openings | Reproduced the prototype geometry as native Floors | Retained; copy automatic creases as explicit split lines to constrain triangulation |
| Boolean symmetric difference of source and result | Revit failed on the complex trimmed main roof | Not the acceptance check; do not infer equivalence from boolean failure |
| Raw mesh vertices and triangle points | Apparent deviations around 0.009 mm despite matching volumes and areas; coordinates far from origin lose mesh precision | Use exact edge samples and project triangle interior points onto analytical source faces |
| Preserve all stored subelement heights literally | A nearly coplanar quadrilateral differed by about 0.02 mm after reconstruction; its stored points did not lie on the source's actual planar face | Match the actual single top-face plane with a bounded, reported correction |
| Implicitly delete original hosts after successful conversion | Would also delete 45 user annotations and an alignment | Retain all sources; deletion is a separate user decision |

The single-plane correction adjusted one prototype's stored height by at most
0.0312993 mm. After correction and precise sampling, maximum sampled surface
distance across all 16 pairs was approximately `5.2e-11 mm`. The affected roof's
relative volume difference was `2.1026e-7`; the other pairs were around floating
point precision. The volume and area acceptance tolerance is `1e-6` relative
with an absolute `1e-6` native-unit floor. Surface tolerance remains 0.01 mm.
These checks are measured practical acceptance criteria, not a mathematical
proof of identical solids.

## API details and retained behaviour

- For the exercised shape-edited roofs, the sketch/base is below the original
  flat top by the compound thickness. Floor level offset includes that thickness.
- Get the FootPrintRoof sketch through its dependent `Sketch`; the Revit 2024
  FootPrintRoof does not expose the Floor-style `SketchId` property.
- Create missing shape points on the initially flat Floor top. Draw split lines,
  then set vertex offsets relative to the initial top elevation.
- `Document.NewOpening(host, curves, False)` cuts vertically. `True` means
  perpendicular to the host face, not vertical.
- The BIMO IronPython execution used here did not provide the `traceback` standard
  library module. The catalog script uses ordinary re-raising after rollback so
  BIMO captures the real exception and reports failure.
- The generalized script derives floor types per source RoofType and uses
  explicit selection/IN, replacing all prototype-specific document names and IDs.

## Validation boundary and remaining cases

The measurements above describe the original live prototype. The exact generalized
catalog file needs its own runtime validation; record those results separately
in the PR and only then list a tested Revit version in the catalog.

The script excludes curved faces/boundaries, variable layers, extruded and curtain
roofs, non-shape-edited slopes, shaft openings and hosted-family conversion.
Multiple RoofTypes, additional constant layers, phases, and other Revit versions
need dedicated fixtures. Samples do not exhaust every point on a face, and merged
multi-solid geometry can still encounter Revit boolean-union failures; such a
failure aborts instead of bypassing validation.
