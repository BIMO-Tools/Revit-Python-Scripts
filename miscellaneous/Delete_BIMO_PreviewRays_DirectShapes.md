# Delete BIMO_PreviewRays DirectShapes

This script deletes all **DirectShape** elements in a Revit document whose `ApplicationId` equals `"BIMO_PreviewRays"`.

## File Name

`Delete_BIMO_PreviewRays_DirectShapes.py`

## How It Works

1. **Collect** all `DirectShape` elements in the active Revit document.
2. **Filter** them by `ApplicationId` (`"BIMO_PreviewRays"`).
3. **Delete** any matching elements within a Revit `Transaction`.
4. Print out a message indicating the number of elements deleted (or a message if none were found).

## Usage

1. **Load this script** into your Python execution environment that has access to Revit (e.g., pyRevit, RevitPythonShell, or your custom Revit command).
2. **Run** the script.
3. **Check** the output (e.g., in the console, TaskDialog, or custom logging mechanism) for a success or “not found” message.

## Notes

- The script relies on the Revit API, so it must be executed **within** a Revit session.  
- Make sure that you have permissions to modify the Revit document (i.e., that the document is not read-only).  
- Always **save or create a backup** of your Revit file before running scripts that delete elements.

## License

Use and distribute this script as needed. Modify it to suit your internal workflows.  
No warranties or guarantees are provided; use at your own risk.
