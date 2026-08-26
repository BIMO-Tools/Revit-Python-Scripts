# Import image to active view

Imports a raster image into the active Revit view, centers it in the currently visible area, and scales it proportionally to the visible view width.

By default, the source image is first copied beside the saved Revit document. Revit then imports that persistent copy into the project.

## Compatibility

- BIMO engine: `IronPython`
- Minimum Revit version: 2024
- Active project document required
- Model-changing operation: yes
- External file-system write: yes, when `IN[2]` is enabled
- Tested Revit versions: not yet recorded for this exact repository script

## Before running

1. Save the active Revit project if the image should be copied beside it.
2. Open the target plan, elevation, section, drafting, or other view that supports raster images.
3. Make sure the visible area and zoom level represent the desired initial image placement.
4. Provide the source image path in `IN[0]`.
5. Run the script through BIMO Run Python with the inline **Script** field empty.

No element selection is required.

## Inputs

BIMO passes preset `IN` values as strings. Inputs are positional.

| Index | Meaning | Required | Default |
| --- | --- | --- | --- |
| `IN[0]` | Existing local raster-image path | Yes | None |
| `IN[1]` | Target image width as a fraction of the visible view width, from `0.01` to `1.0` | No | `0.4` |
| `IN[2]` | Copy the image beside the active Revit document before import | No | `true` |

Accepted true values for `IN[2]` are `true`, `1`, `yes`, `y`, and `on`; accepted false values are `false`, `0`, `no`, `n`, and `off`.

## Processing

The script:

1. validates the input path, width fraction, active view, and visible view extent;
2. when requested, copies the image beside the saved Revit document;
3. avoids overwriting an existing file by adding a numeric suffix;
4. creates an imported `ImageType` from the persistent path;
5. places an `ImageInstance` at the center of the visible area;
6. locks its proportions and scales it to the configured width fraction;
7. commits all Revit changes in one transaction and rolls that transaction back on failure.

## Output

`OUT` is an object with:

- `imageInstanceId` and `imageTypeId`;
- `viewName`;
- `storedPath` used by the imported image type;
- `copiedBesideDocument`;
- final `widthFeet` and `heightFeet` in Revit internal units.

Validation and Revit API failures are returned by BIMO as execution errors.

## Limitations and safety

- The image is imported into the RVT rather than linked, even though its source path is retained.
- Copying the source file is an external file-system effect and is not part of the Revit transaction. If Revit import later fails, the copied file may remain beside the document.
- The script never overwrites an existing image file; it chooses a suffixed name instead.
- Placement uses the current on-screen view extent. Change `IN[1]` or move and resize the image manually when exact real-world scaling is required.
- Unsupported image formats and views are rejected by Revit.

## Manual Revit test

1. Open and save a test project in Revit 2024 or newer.
2. Open a plan view and set a recognizable zoom extent.
3. Run with a JPG or PNG path in `IN[0]`, `0.4` in `IN[1]`, and `true` in `IN[2]`.
4. Confirm the image appears centered, preserves its proportions, and is approximately 40% of the visible view width.
5. Confirm a non-overwriting copy exists beside the RVT and `OUT.storedPath` points to it.
6. Undo the Revit transaction and remove the copied test file manually if it is no longer needed.
