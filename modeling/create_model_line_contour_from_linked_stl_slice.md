# Create model-line contour from linked STL slice

Creates one closed exterior contour as Revit model lines by intersecting a selected linked STL mesh with a horizontal plane. The script preserves the triangle-section segments, polygonizes the resulting linework, heals small gaps between separate STL solids, and keeps the largest exterior shell.

The defaults preserve the validated prototype scenario: level `L3`, a slice `1500` mm above the level, `25` mm endpoint snapping, `250` mm polygon gap healing, and `50` mm topology-preserving simplification.

The alternatives, parameter sweep, measured evidence, implementation traps, and remaining experiments are maintained in [decision record 0001](../docs/decisions/0001-linked-stl-slice-contour.md).

## Compatibility

- BIMO engine: `IronPython`
- Minimum Revit version: 2024
- Active project document required
- Model-changing operation: yes
- File-system reads: optional local .NET assembly paths supplied through `IN[6]`
- Tested Revit versions: not yet recorded for this exact catalog script

The polygonization and gap-healing prototype from which this draft was generalized ran successfully in Revit 2024. The generalized repository file still requires a separate manual test before Revit 2024 can be listed as tested.

## Before running

1. Link the STL into the active Revit project.
2. Select exactly one linked `ImportInstance` containing the STL mesh.
3. Ensure that the requested Revit `Level` exists.
4. Make NetTopologySuite 2.6.0 and its prerequisites available as described below.
5. Run the script through BIMO Run Python with the inline **Script** field empty.

The script reads all mesh geometry exposed by the selected linked import. It does not modify the link or the source STL file.

## NetTopologySuite dependency

Segment noding, polygonization, buffering, and simplification use `NetTopologySuite` 2.6.0. If the assemblies are already loaded in the Revit process, leave `IN[6]` empty. Otherwise pass a semicolon-separated list of full local DLL paths in dependency order, with `NetTopologySuite.dll` last.

The prototype used these assemblies:

1. `System.Numerics.Vectors.dll`
2. `System.Runtime.CompilerServices.Unsafe.dll`
3. `System.Buffers.dll`
4. `System.Memory.dll`
5. `NetTopologySuite.dll`

The paths are intentionally not embedded in the script because NuGet caches and installation locations are machine-specific. The script only reads the explicitly supplied files and performs no downloads or network access.

## Inputs

BIMO passes `IN` values as strings. All inputs are positional.

| Index | Meaning | Default |
| --- | --- | --- |
| `IN[0]` | Exact Revit level name | `L3` |
| `IN[1]` | Slice offset above the level, in millimetres | `1500` |
| `IN[2]` | XY grid used to snap segment endpoints, in millimetres; must be greater than zero | `25` |
| `IN[3]` | Buffer distance used to close gaps between polygonized STL fragments, in millimetres; `0` disables healing | `250` |
| `IN[4]` | Topology-preserving contour simplification tolerance, in millimetres; `0` disables simplification | `50` |
| `IN[5]` | Minimum accepted exterior-shell area, in square metres | `10` |
| `IN[6]` | Semicolon-separated full paths to required .NET assemblies, in load order | Empty when already loaded |
| `IN[7]` | Model-line style name | `BIMO_STL_Contour` |

The script stops if the slice exceeds 2,000,000 raw segments.

## Processing

The script:

1. resolves the exact named `Level` and places the section plane at `Level.ProjectElevation + IN[1]`;
2. recursively reads mesh geometry from the selected linked `ImportInstance` in project coordinates;
3. intersects every mesh triangle with the horizontal plane and keeps the real section segments;
4. snaps segment endpoints to the `IN[2]` grid, discards collapsed segments, and removes duplicates;
5. uses NetTopologySuite to node and dissolve the linework, then polygonizes every closed ring;
6. combines nearby polygon fragments by buffering outward and inward by `IN[3]`;
7. keeps the polygon with the largest exterior shell and applies topology-preserving simplification using `IN[4]`;
8. checks the final exterior-shell area against `IN[5]` before opening a Revit transaction;
9. creates a line subcategory when needed, one horizontal `SketchPlane`, and the closed model-line contour;
10. rolls the transaction back if any model creation step fails.

## Tuning contour accuracy

`IN[3]` and `IN[4]` affect different parts of the result:

- Reduce `IN[4]` to `25`, `10`, or `0` to retain more of the healed shell and determine whether a local discrepancy comes from simplification.
- Reduce `IN[3]` when the contour bridges intended recesses or rounds exterior corners too strongly. Increase it only when the polygonized STL remains split into separate building fragments.
- Keep `IN[2]` small enough to preserve wall location. Increasing endpoint snap can close noisy linework but also moves every sliced endpoint to a coarser grid.

The gap-healing operation uses the default NetTopologySuite buffer joins. Consequently, some corner rounding can be introduced by `IN[3]` even when simplification is disabled. Tune simplification first, then gap healing, so the source of a discrepancy remains clear.

## Output

On success, `OUT` is a dictionary containing:

- source, level, and slice elevation;
- mesh, triangle, raw-segment, collapsed-segment, duplicate-segment, and unique-segment counts;
- noded line component and polygonizer diagnostics (`polygon_count`, `dangle_count`, `cut_edge_count`, and `invalid_ring_count`);
- gap-healing and simplification parameters plus healed and final exterior-shell areas;
- created model-line IDs, sketch-plane ID, and line-style information.

Validation, dependency-loading, geometry, and Revit API failures reach BIMO as execution errors.

## Model changes and safety

The script creates:

- a model-line subcategory named by `IN[7]` when it does not already exist; a new subcategory is colored cyan;
- one `SketchPlane` at the section elevation;
- one closed chain of model curves assigned to that line style.

No existing model elements are intentionally edited or deleted. Undo the single transaction to remove all model changes from one run. Test the draft on a copy of the model before production use.

## Limitations

- Only the largest exterior shell is created. Courtyards, holes, and smaller detached contours are omitted.
- Gap healing can join close but intentionally separate geometry, fill narrow recesses, and round corners. Its default is model-dependent, not a universal building tolerance.
- Coplanar mesh triangles are ignored to avoid filling horizontal mesh faces.
- The source must be a selected linked `ImportInstance`; unloaded links and other element types are not supported.
- Very large STL meshes can take tens of seconds or longer to process because every triangle is inspected.
- NetTopologySuite and all required assemblies must be compatible with the selected IronPython host.

## Prototype validation

The current approach was exercised in Revit 2024 on the development building model at `L3 + 1500 mm`. The complete measurements, comparison with the earlier concave hull, gap-healing sweep, confidence boundary, and calibration order are recorded in [decision record 0001](../docs/decisions/0001-linked-stl-slice-contour.md).

Those measurements document the prototype run, not a successful run of the exact generalized repository file.

## Manual Revit test

1. Open a disposable Revit 2024 or newer project containing level `L3` and a linked building STL.
2. Select the linked STL `ImportInstance`.
3. Supply the local NetTopologySuite assembly paths in `IN[6]` when they are not already loaded.
4. Run with the defaults and verify that model lines are created at `L3 + 1500 mm`.
5. Inspect the contour against the mesh in plan and 3D, confirm it is closed, and review omitted courtyards or detached portions.
6. Repeat with `IN[4] = 0` and compare the suspect locations to isolate simplification effects.
7. Undo each transaction and confirm that the created lines, sketch plane, and newly created style are removed together.
