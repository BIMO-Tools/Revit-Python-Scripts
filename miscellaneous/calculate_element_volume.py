from Autodesk.Revit.DB import *

# Get the current document and UI document objects
uidoc = __uidoc__
doc = __doc__

def get_element_volume(element):
    """Returns the total volume of valid Solids in a FamilyInstance."""
    if not isinstance(element, FamilyInstance):
        raise Exception("Element is not a FamilyInstance.")
    
    # Options for retrieving geometry
    options = Options()
    options.ComputeReferences = True
    options.IncludeNonVisibleObjects = True

    # Get the element's geometry
    geom_elem = element.get_Geometry(options)
    if not geom_elem:
        raise Exception("GeometryElement is null.")
    
    total_volume = 0  # Accumulate total volume here

    for geom_obj in geom_elem:
        # If this is a GeometryInstance
        if isinstance(geom_obj, GeometryInstance):
            symbol_geom = geom_obj.GetSymbolGeometry()
            if symbol_geom:
                for symbol_obj in symbol_geom:
                    if isinstance(symbol_obj, Solid) and symbol_obj.Volume > 0:
                        total_volume += symbol_obj.Volume  # Add volume
        # If it is directly a Solid
        elif isinstance(geom_obj, Solid) and geom_obj.Volume > 0:
            total_volume += geom_obj.Volume  # Add volume

    return total_volume


# Input data
selected_ids = [elId for elId in uidoc.Selection.GetElementIds()]
elements = [doc.GetElement(id) for id in selected_ids]  # List of selected elements
results = []

for elem in elements:
    try:
        volume_in_cubic_feet = get_element_volume(elem)
        # Convert from cubic feet to cubic meters
        volume_in_cubic_meters = volume_in_cubic_feet * 0.0283168
        results.append(volume_in_cubic_meters)
    except Exception as e:
        # Return the error message for problematic elements
        results.append(str(e))

# Print the result (visible in TaskDialog)
print(results)
