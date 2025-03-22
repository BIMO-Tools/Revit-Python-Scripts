from System.Collections.Generic import List
from Autodesk.Revit.DB import (
    ElementId,
    FilteredElementCollector,
    DirectShape,
    Transaction
)

# Get the document object passed from C# through __doc__
doc = __doc__

applicationId = "BIMO_PreviewRays"

# Filter DirectShape and select only those with the specified ApplicationId
shapes_to_delete_ids = [
    ds.Id for ds in FilteredElementCollector(doc).OfClass(DirectShape)
    if ds.ApplicationId == applicationId
]

# If there are any shapes to delete
if shapes_to_delete_ids:
    # Convert the Python list to a .NET List[ElementId]
    shapes_to_delete_net_list = List[ElementId](shapes_to_delete_ids)

    # Create a transaction
    t = Transaction(doc, "Delete DirectShape with BIMO_PreviewRays")
    t.Start()

    # Delete all found elements
    doc.Delete(shapes_to_delete_net_list)

    # Commit the transaction
    t.Commit()

    # Print the result to IronPython's console (shown in the TaskDialog)
    print("Deleted DirectShape elements:", len(shapes_to_delete_ids))
else:
    # If none found
    print("No DirectShape elements found with ApplicationId 'BIMO_PreviewRays'.")
