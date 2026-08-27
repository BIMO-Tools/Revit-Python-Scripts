# 0001 — Linked STL slice contour extraction

- Status: Accepted for the current draft
- Date: 2026-08-28
- Related issue: [#4](https://github.com/BIMO-Tools/Revit-Python-Scripts/issues/4)
- Related pull request: [#5](https://github.com/BIMO-Tools/Revit-Python-Scripts/pull/5)
- Implementation: [`modeling/create_model_line_contour_from_linked_stl_slice.py`](../../modeling/create_model_line_contour_from_linked_stl_slice.py)
- User guide: [`modeling/create_model_line_contour_from_linked_stl_slice.md`](../../modeling/create_model_line_contour_from_linked_stl_slice.md)

## Context and goal

The source is an exported building model linked into Revit as an STL `ImportInstance`. For a requested Revit `Level`, the script must create a closed exterior contour as horizontal model lines at `Level.ProjectElevation + 1500 mm` by default.

The STL is not one watertight building solid. Walls, columns, facade components, and other parts can be represented by separate meshes or solids. A horizontal cut therefore contains both the building exterior and many disconnected interior rings.

## Invariants and current public contract

- The source is exactly one selected linked `ImportInstance` containing mesh geometry.
- Revit `Level` elements define storey elevations; the section offset is configurable and defaults to `1500 mm`.
- Mesh coordinates must be read in project coordinates.
- Existing model elements and the source link are not intentionally modified or deleted.
- Geometry processing completes before the Revit transaction starts.
- One transaction creates the line subcategory when absent, one `SketchPlane`, and the model-line chain; failures roll it back.
- The current output is only the largest exterior shell. Holes, courtyards, and detached contours are intentionally omitted.
- Existing script and documentation paths stay stable because saved BIMO presets may reference them.

## Approaches evaluated

| Approach | Observed behavior | Decision |
| --- | --- | --- |
| Convex hull | Cannot preserve facade recesses or a concave building footprint. | Rejected conceptually. |
| Point-based NetTopologySuite concave hull | Produced one compact contour, but inferred edges from points rather than preserving triangle-section segments. It bridged or simplified facade conditions too aggressively. | Rejected as the primary algorithm. |
| Segment polygonization without healing | Preserved real section connectivity, but separate STL solids remained separate. The prototype produced 997 polygons; the largest direct shell was only about `27.953 m²`. | Accepted as the geometric basis, insufficient alone. |
| Segment polygonization plus morphological closing | Preserved section segments, then joined nearby polygon fragments into a building-scale exterior shell. | Accepted for the current draft. |

## Accepted pipeline

1. Resolve the exact named Revit `Level`.
2. Place a horizontal plane at the level project elevation plus the requested offset.
3. Recursively read every `Mesh` from the selected linked import using instance geometry.
4. Intersect every mesh triangle with the horizontal plane and retain the resulting XY segment.
5. Snap both segment endpoints to a configurable grid.
6. Remove collapsed and direction-independent duplicate segments.
7. Build NetTopologySuite `LineString` objects and call the geometry instance `Union()` to node and dissolve the network.
8. Run `Polygonizer(False)` and collect its polygons and diagnostics.
9. Build a polygon collection and apply `Buffer(+gap).Buffer(-gap)` to close bounded gaps between separate STL components.
10. Select the polygon with the largest exterior-ring area.
11. Apply `TopologyPreservingSimplifier` when its tolerance is greater than zero.
12. Validate area and Revit short-curve constraints, then create the closed model-line chain.

This is a hybrid contour-extraction approach. Polygonization provides topology from the actual section segments; morphological closing compensates for the source STL being split into nearby solids.

## Prototype evidence

The accepted approach was exercised through BIMO MCP in Revit 2024 on the development building model at `L3 + 1500 mm`.

### Section and polygonization

| Measurement | Result |
| --- | ---: |
| Meshes | 49 |
| Triangles inspected | 7,264,272 |
| Raw section segments | 12,275 |
| Segments collapsed by `25 mm` snapping | 1,976 |
| Duplicate segments removed | 438 |
| Unique snapped segments | 9,861 |
| Noded line components | 9,925 |
| Valid polygons | 997 |
| Dangles | 13 |
| Cut edges | 0 |
| Invalid rings | 0 |
| Largest polygon before healing | approximately `27.953 m²` |

### Gap-healing sweep

The same polygon collection was buffered outward and inward by each distance.

| Healing distance | Largest exterior-shell area | Exterior vertices |
| ---: | ---: | ---: |
| `250 mm` | `572.873 m²` | 1,229 |
| `500 mm` | `574.097 m²` | 959 |
| `750 mm` | `575.454 m²` | 750 |
| `1000 mm` | `576.870 m²` | 618 |
| `1500 mm` | `580.061 m²` | 462 |

`250 mm` was selected because it was the smallest tested distance that produced one building-scale shell. Larger distances changed the area more and progressively removed detail.

With `50 mm` topology-preserving simplification, the `250 mm` healed shell changed from approximately `572.873 m²` to `573.418 m²` and was created as 179 model lines. The complete prototype run took approximately 58.9 seconds.

For comparison, the earlier point-based concave-hull prototype created 46 model lines with an area of approximately `590.55 m²` in 25.8 seconds. Its lower complexity and larger area were signs that it was generalizing across facade detail rather than reconstructing the section network.

The exact generalized repository script has not yet been run as-is. These measurements validate the underlying algorithm and parameter choice, not the complete catalog file or every supported input path. Keep `revit.tested` empty until the repository file itself passes the documented manual test.

## Parameter interpretation and calibration order

| Input | Current default | Effect |
| --- | ---: | --- |
| `endpoint_snap_mm` | `25` | Moves endpoints to an XY grid before noding. A larger value can close noisy connections but also shifts wall locations. |
| `gap_healing_mm` | `250` | Joins nearby polygon fragments. A larger value can bridge intended recesses and close narrow passages. `0` disables the operation. |
| `simplification_tolerance_mm` | `50` | Reduces vertices after healing while preserving topology. A larger value removes more facade detail. `0` disables the operation. |

When investigating a local mismatch:

1. Keep endpoint snapping and gap healing unchanged.
2. Compare simplification values `50`, `25`, `10`, and `0 mm`.
3. If the mismatch remains at `0`, reduce gap healing and verify whether the result still forms one building-scale shell.
4. Change endpoint snapping last, because it changes the input network rather than only the final shell.

This order separates three different error sources instead of tuning several parameters simultaneously.

## Known geometric effects and limitations

- Default NetTopologySuite buffer joins can round exterior corners even when simplification is disabled.
- Morphological closing can fill real narrow recesses or join intentionally separate objects.
- The largest shell is selected by exterior-ring area; polygon holes are not emitted as model lines.
- Coplanar triangles are ignored to avoid filling horizontal mesh faces.
- Runtime is dominated by the full mesh-triangle scan.
- The chosen `250 mm` healing distance is evidence from one building model, not a universal architectural tolerance.
- The source STL is not stored in this repository, so the numeric prototype results are not yet an automated regression fixture.

## IronPython and API implementation notes

- Use `__uidoc__.Document` for the active document. A module docstring occupies Python's `__doc__` name and can hide a host-provided global with the same name.
- Call the parameterless geometry instance method `multi_line.Union()`. Calling static unary-union overloads from IronPython caused overload ambiguity during the prototype.
- NetTopologySuite coordinates and Revit geometry use Revit internal feet in the implementation. Convert millimetre inputs before geometry processing and square feet before reporting square metres.
- Construct typed .NET arrays for NetTopologySuite factory calls, including `Array[LineString]` and `Array[Geometry]`.
- Do not open a Revit transaction until slicing, polygonization, healing, simplification, area checks, and short-curve cleanup have succeeded.

## Remaining work

- Run the exact repository script in a disposable Revit 2024 model and record the result.
- Compare `simplification_tolerance_mm` values `0`, `10`, `25`, and `50` at the visually discrepant facade locations.
- Evaluate a mitre-join buffer or a graph-based gap-bridging strategy if corner rounding remains material.
- Decide whether courtyards, holes, and detached building parts should become explicit outputs.
- Add a distributable synthetic mesh fixture and automated geometry regression tests when the script moves beyond the current draft stage.
