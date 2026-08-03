# Create Toposolid from model lines

Creates a point-based Revit `Toposolid` by sampling the elevations of selected model curves.

## Compatibility

- BIMO engine: `IronPython`
- Minimum Revit version: 2024
- Active project document required
- Model-changing operation: yes
- Tested Revit versions: not yet recorded

`Toposolid` was introduced in Revit 2024. This script does not provide a `TopographySurface` fallback for older Revit versions.

## Before running

1. Create model lines at the real Z elevations of the site contours.
2. Select the model lines. Detail lines and imported CAD elements are ignored.
3. Open a plan or 3D view associated with the intended level, or provide a level name in `IN[3]`.
4. Run the script through BIMO Run Python with the inline **Script** field empty.

The selected curves do not have to form a closed boundary. The script samples points along them and lets Revit triangulate the resulting point cloud.

## Inputs

BIMO passes `IN` values as strings. All inputs are optional and positional.

| Index | Meaning | Default |
| --- | --- | --- |
| `IN[0]` | Sampling step in millimetres | `1000` |
| `IN[1]` | XY tolerance for merging duplicate points, in millimetres | `1` |
| `IN[2]` | Exact `ToposolidType` name | First type alphabetically |
| `IN[3]` | Exact `Level` name | Active view level, otherwise nearest level |

A smaller sampling step creates more points and may produce a more detailed but heavier Toposolid.

## Processing

The script:

1. accepts selected `ModelCurve` elements;
2. samples every curve at approximately the configured interval;
3. merges points whose XY coordinates fall within the configured tolerance;
4. averages XYZ coordinates within each duplicate bucket;
5. rejects point sets with fewer than three unique XY locations or a collinear XY extent;
6. stops before creation when sampling would exceed the 50,000-point safety limit;
7. creates the Toposolid in a dedicated Revit transaction;
8. rolls the transaction back if creation fails.

## Output

On success, `OUT` contains the created element ID, curve and point counts, ignored selection count, chosen type and level, and elevation range in metres. Validation and Revit API failures are returned by BIMO as execution errors.

## Limitations and safety

- This creates a point-based Toposolid, not a user-defined closed sketch boundary.
- Coincident XY points are averaged, including their Z values.
- The result depends on Revit's triangulation of the sampled points.
- Very small sampling steps can create excessive geometry and slow down the model.
- Run model-changing scripts on a test copy before using them in production.
