# Create model-line contour from linked STL slice

Creates one closed exterior contour as Revit model lines by intersecting a selected linked STL mesh with a horizontal plane and calculating a NetTopologySuite concave hull from the intersection points.

The initial defaults preserve the prototype scenario: level `L3`, a slice `1500` mm above the level, `25` mm point snapping, a `2500` mm maximum hull edge, and `50` mm contour simplification.

## Compatibility

- BIMO engine: `IronPython`
- Minimum Revit version: 2024
- Active project document required
- Model-changing operation: yes
- File-system reads: optional local .NET assembly paths supplied through `IN[6]`
- Tested Revit versions: not yet recorded for this exact catalog script

The prototype from which this draft was generalized ran successfully in Revit 2024. The generalized repository file still requires a separate manual test before Revit 2024 can be listed as tested.

## Before running

1. Link the STL into the active Revit project.
2. Select exactly one linked `ImportInstance` containing the STL mesh.
3. Ensure that the requested Revit `Level` exists.
4. Make NetTopologySuite 2.6.0 and its prerequisites available as described below.
5. Run the script through BIMO Run Python with the inline **Script** field empty.

The script reads all mesh geometry exposed by the selected linked import. It does not modify the link or the source STL file.

## NetTopologySuite dependency

The concave hull is calculated with `NetTopologySuite` 2.6.0. If the assemblies are already loaded in the Revit process, leave `IN[6]` empty. Otherwise pass a semicolon-separated list of full local DLL paths in dependency order, with `NetTopologySuite.dll` last.

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
| `IN[2]` | XY grid used to merge nearby intersection points, in millimetres | `25` |
| `IN[3]` | Maximum edge length used by the concave-hull algorithm, in millimetres | `2500` |
| `IN[4]` | Topology-preserving contour simplification tolerance, in millimetres | `50` |
| `IN[5]` | Minimum accepted contour area, in square metres | `10` |
| `IN[6]` | Semicolon-separated full paths to required .NET assemblies, in load order | Empty when already loaded |
| `IN[7]` | Model-line style name | `BIMO_STL_Contour` |

When a slice produces more than 100,000 raw points, the script raises the effective point snap to at least `50` mm. It stops if the slice exceeds 2,000,000 raw points.

## Processing

The script:

1. resolves the exact named `Level` and places the section plane at `Level.ProjectElevation + IN[1]`;
2. recursively reads mesh geometry from the selected linked `ImportInstance` in project coordinates;
3. intersects each mesh triangle with the horizontal plane;
4. snaps and deduplicates the resulting XY points;
5. calculates a NetTopologySuite concave hull with holes disabled;
6. applies topology-preserving simplification;
7. keeps the largest polygon whose area meets `IN[5]`;
8. validates the contour before opening a Revit transaction;
9. creates a line subcategory when needed, one horizontal `SketchPlane`, and the closed model-line contour;
10. rolls the transaction back if any model creation step fails.

## Output

On success, `OUT` is a dictionary containing the source element ID, level and slice elevation, mesh and triangle counts, raw and snapped point counts, effective parameters, contour area, created model-line IDs, sketch-plane ID, and line-style information.

Validation, dependency-loading, geometry, and Revit API failures reach BIMO as execution errors.

## Model changes and safety

The script creates:

- a model-line subcategory named by `IN[7]` when it does not already exist; a new subcategory is colored magenta;
- one `SketchPlane` at the section elevation;
- one closed chain of model curves assigned to that line style.

No existing model elements are intentionally edited or deleted. Undo the single transaction to remove all model changes from one run. Test the draft on a copy of the model before production use.

## Limitations

- Only the largest exterior polygon is created. Courtyards, holes, and smaller detached contours are omitted.
- The concave hull is inferred from points, not reconstructed from connected triangle-intersection segments. Its shape depends strongly on point snap, maximum edge length, and simplification tolerance.
- Coplanar mesh triangles are ignored to avoid filling horizontal mesh faces.
- The source must be a selected linked `ImportInstance`; unloaded links and other element types are not supported.
- Very large STL meshes can take tens of seconds or longer to process because every triangle is inspected.
- NetTopologySuite and all required assemblies must be compatible with the selected IronPython host.

## Manual Revit test

1. Open a disposable Revit 2024 or newer project containing level `L3` and a linked building STL.
2. Select the linked STL `ImportInstance`.
3. Supply the local NetTopologySuite assembly paths in `IN[6]` when they are not already loaded.
4. Run with the defaults and verify that model lines are created at `L3 + 1500 mm`.
5. Inspect the contour against the mesh in plan and 3D, confirm it is closed, and review omitted courtyards or detached portions.
6. Undo the transaction and confirm that the created lines, sketch plane, and newly created style are removed together.
