"""Create validated Floors from selected shape-edited Basic Roofs.

BIMO IronPython: IN[0] = dry_run (default "true"), IN[1] = optional
comma-separated roof IDs. Sources and annotations are always retained.
"""

import clr

clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import (
    BooleanOperationsType, BooleanOperationsUtils, BuiltInParameter,
    CurveArray, CurveLoop, Element, ElementClassFilter, ElementId,
    FailureProcessingResult, FailureSeverity, FilteredElementCollector,
    Floor, FloorType, FootPrintRoof, IFailuresPreprocessor, Level, Line,
    Opening, Options, PlanarFace, Sketch, Solid, StorageType,
    Transaction, TransactionGroup, TransactionStatus, ViewDetailLevel, XYZ,
)
from System.Collections.Generic import List


MM_PER_FOOT = 304.8
VERTEX_TOLERANCE = 1e-6
SURFACE_TOLERANCE = 0.01 / MM_PER_FOOT
PLANAR_CORRECTION_LIMIT = 0.1 / MM_PER_FOOT
RELATIVE_QUANTITY_TOLERANCE = 1e-6


def element_id(element):
    return element.Id.Value


def element_name(element):
    return Element.Name.GetValue(element)


def input_text(index, default=""):
    if index >= len(IN) or IN[index] is None:
        return default
    value = str(IN[index]).strip()
    return value if value else default


def read_inputs(doc):
    if len(IN) > 2:
        raise ValueError("Expected at most IN[0] and IN[1].")
    flag = input_text(0, "true").lower()
    if flag not in ("true", "false"):
        raise ValueError("IN[0] must be true or false.")
    explicit_ids = input_text(1)
    if explicit_ids:
        numbers = [int(value.strip()) for value in explicit_ids.split(",")]
        if any(value <= 0 for value in numbers):
            raise ValueError("IN[1] must contain positive element IDs.")
        ids = [ElementId(value) for value in sorted(set(numbers))]
    else:
        ids = list(__uidoc__.Selection.GetElementIds())
    if not ids:
        raise ValueError("Select Basic Roofs or provide their IDs in IN[1].")
    roofs = [doc.GetElement(value) for value in ids]
    if any(roof is None or not isinstance(roof, FootPrintRoof) for roof in roofs):
        raise ValueError("Every selected/provided element must be a Basic FootPrintRoof.")
    return flag == "true", sorted(roofs, key=element_id)


def get_sketch(doc, element):
    ids = element.GetDependentElements(ElementClassFilter(clr.GetClrType(Sketch)))
    sketches = [doc.GetElement(value) for value in ids]
    if len(sketches) != 1:
        raise ValueError("Expected one sketch for roof {0}.".format(element_id(element)))
    return sketches[0]


def solids(element):
    options = Options()
    options.DetailLevel = ViewDetailLevel.Fine
    result = [geometry for geometry in element.get_Geometry(options)
              if isinstance(geometry, Solid) and geometry.Volume > 1e-9]
    if not result:
        raise ValueError("No solid for element {0}.".format(element_id(element)))
    return result


def merged_solid(element):
    geometry = solids(element)
    result = geometry[0]
    for solid in geometry[1:]:
        result = BooleanOperationsUtils.ExecuteBooleanOperation(
            result, solid, BooleanOperationsType.Union)
    return result


def surface_samples(solid):
    # Revit mesh vertices lose precision far from the origin. Use exact edges
    # and project triangle interior samples onto their source analytical planes.
    points = {}

    def add(point):
        key = (round(point.X, 9), round(point.Y, 9), round(point.Z, 9))
        points[key] = point

    for edge in solid.Edges:
        curve = edge.AsCurve()
        for parameter in (0.0, 0.25, 0.5, 0.75, 1.0):
            add(curve.Evaluate(parameter, True))
    for face in solid.Faces:
        if not isinstance(face, PlanarFace):
            raise ValueError("Only planar solid faces are supported.")
        mesh = face.Triangulate()
        for index in range(mesh.NumTriangles):
            triangle = mesh.get_Triangle(index)
            center = sum([triangle.get_Vertex(i) for i in range(3)], XYZ.Zero) / 3.0
            projection = face.Project(center)
            if projection is not None:
                add(projection.XYZPoint)
    if not points:
        raise ValueError("No surface samples available.")
    return list(points.values())


def distance_to_solid(point, solid):
    best = float("inf")
    for face in solid.Faces:
        projection = face.Project(point)
        if projection is not None:
            best = min(best, projection.Distance)
        if best < 1e-9:
            return best
    for edge in solid.Edges:
        curve = edge.AsCurve()
        best = min(best, point.DistanceTo(curve.GetEndPoint(0)),
                   point.DistanceTo(curve.GetEndPoint(1)))
        projection = curve.Project(point)
        low, high = sorted([curve.GetEndParameter(0), curve.GetEndParameter(1)])
        if projection is not None and low - 1e-9 <= projection.Parameter <= high + 1e-9:
            best = min(best, projection.Distance)
    return best


def vertex_at(editor, point):
    for vertex in editor.SlabShapeVertices:
        location = vertex.Position
        if (abs(location.X - point.X) < VERTEX_TOLERANCE
                and abs(location.Y - point.Y) < VERTEX_TOLERANCE):
            return vertex
    raise ValueError("Cannot find a matching slab-shape vertex.")


def copy_parameter(source, target, parameter_id):
    original = source.get_Parameter(parameter_id)
    replacement = target.get_Parameter(parameter_id)
    if not original or not replacement or not original.HasValue or replacement.IsReadOnly:
        return
    if original.StorageType == StorageType.String:
        replacement.Set(original.AsString() or "")
    elif original.StorageType == StorageType.ElementId:
        replacement.Set(original.AsElementId())
    elif original.StorageType == StorageType.Integer:
        replacement.Set(original.AsInteger())
    elif original.StorageType == StorageType.Double:
        replacement.Set(original.AsDouble())


def prepare_roof(doc, roof, openings):
    roof_type = doc.GetElement(roof.GetTypeId())
    structure = roof_type.GetCompoundStructure()
    editor = roof.SlabShapeEditor
    if structure is None or structure.VariableLayerIndex != -1 or structure.IsVerticallyCompound:
        raise ValueError("Only homogeneous roofs without variable layers are supported.")
    if structure.GetWidth() <= 0 or editor is None or not editor.IsEnabled:
        raise ValueError("Each roof must have thickness and enabled shape editing.")
    if not isinstance(doc.GetElement(roof.LevelId), Level):
        raise ValueError("Roof has no valid base level.")
    points = [vertex.Position for vertex in editor.SlabShapeVertices]
    if not points:
        raise ValueError("Roof has no slab-shape vertices.")
    sketch = get_sketch(doc, roof)
    profiles = List[CurveLoop]()
    for curves in sketch.Profile:
        loop = CurveLoop()
        for curve in curves:
            if not isinstance(curve, Line):
                raise ValueError("Only straight sketch boundaries are supported.")
            loop.Append(curve.Clone())
        profiles.Add(loop)
    hosted_openings = [opening for opening in openings
                       if opening.Host is not None and opening.Host.Id == roof.Id]
    for opening in hosted_openings:
        if opening.IsRectBoundary or any(not isinstance(c, Line) for c in opening.BoundaryCurves):
            raise ValueError("Only curve-based openings with straight edges are supported.")
    source = merged_solid(roof)
    samples = surface_samples(source)
    top_faces = [face for face in source.Faces if face.FaceNormal.Z > 0.1]
    adjustment = 0.0
    if len(top_faces) == 1:
        # Near-coplanar shape points may differ from the face Revit actually built.
        # Match that face, with a bounded and reported correction, never a roof ID.
        face = top_faces[0]
        normal, origin = face.FaceNormal, face.Origin
        adjusted = [XYZ(p.X, p.Y, origin.Z - (
            normal.X * (p.X - origin.X) + normal.Y * (p.Y - origin.Y)) / normal.Z)
            for p in points]
        adjustment = max(abs(a.Z - b.Z) for a, b in zip(points, adjusted))
        if adjustment > PLANAR_CORRECTION_LIMIT:
            raise ValueError("Stored shape points differ from the actual plane by over 0.1 mm.")
        points = adjusted
    edges = [(crease.EndPoints[0].Position, crease.EndPoints[1].Position)
             for crease in editor.SlabShapeCreases if str(crease.CreaseType) != "Boundary"]
    return {"roof": roof, "type": roof_type, "structure": structure,
            "points": points, "profiles": profiles, "edges": edges,
            "openings": hosted_openings, "solid": source, "samples": samples,
            "adjustment": adjustment}


def new_floor_type(doc, template, source_type, structure, used_names):
    base_name = "BIMO - Roof to Floor - {0}".format(element_name(source_type))
    candidate, suffix = base_name, 2
    while candidate in used_names:
        candidate = "{0} ({1})".format(base_name, suffix)
        suffix += 1
    result = template.Duplicate(candidate)
    result.SetCompoundStructure(structure)
    used_names.add(candidate)
    return result


class CaptureFailures(IFailuresPreprocessor):
    def __init__(self):
        self.messages = []

    def PreprocessFailures(self, accessor):
        has_error = False
        for failure in accessor.GetFailureMessages():
            self.messages.append(failure.GetDescriptionText())
            if failure.GetSeverity() == FailureSeverity.Warning:
                accessor.DeleteWarning(failure)
            else:
                has_error = True
        if has_error:
            return FailureProcessingResult.ProceedWithRollBack
        return FailureProcessingResult.Continue


def create_floor(doc, source, floor_type):
    roof, points = source["roof"], source["points"]
    floor = Floor.Create(doc, source["profiles"], floor_type.Id, roof.LevelId)
    offset = (roof.get_Parameter(BuiltInParameter.ROOF_LEVEL_OFFSET_PARAM).AsDouble()
              + source["structure"].GetWidth())
    floor.get_Parameter(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM).Set(offset)
    for parameter in (BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS,
                      BuiltInParameter.ALL_MODEL_MARK,
                      BuiltInParameter.PHASE_CREATED, BuiltInParameter.PHASE_DEMOLISHED):
        copy_parameter(roof, floor, parameter)
    doc.Regenerate()
    editor = floor.SlabShapeEditor
    editor.Enable()
    doc.Regenerate()
    base_z = list(editor.SlabShapeVertices)[0].Position.Z
    for point in points:
        found = any(abs(v.Position.X - point.X) < VERTEX_TOLERANCE
                    and abs(v.Position.Y - point.Y) < VERTEX_TOLERANCE
                    for v in editor.SlabShapeVertices)
        if not found and editor.DrawPoint(XYZ(point.X, point.Y, base_z)) is None:
            raise ValueError("Cannot add a roof vertex to the Floor.")
    for start, end in source["edges"]:
        editor.DrawSplitLine(vertex_at(editor, start), vertex_at(editor, end))
    for point in points:
        editor.ModifySubElement(vertex_at(editor, point), point.Z - base_z)
    doc.Regenerate()
    vertex_error = max(abs(vertex_at(editor, p).Position.Z - p.Z) for p in points)
    if vertex_error > VERTEX_TOLERANCE:
        raise ValueError("Slab-shape vertex elevations do not match.")
    opening_map = []
    for opening in source["openings"]:
        curves = CurveArray()
        for curve in opening.BoundaryCurves:
            curves.Append(curve.Clone())
        # False means vertical, not perpendicular to the sloping face.
        created = doc.Create.NewOpening(floor, curves, False)
        opening_map.append({"source": element_id(opening), "target": element_id(created)})
    doc.Regenerate()
    return floor, opening_map, vertex_error


def verify_floor(source, floor, opening_map, vertex_error):
    original, result = source["solid"], merged_solid(floor)
    original_samples, result_samples = source["samples"], surface_samples(result)
    distance = max(max(distance_to_solid(p, result) for p in original_samples),
                   max(distance_to_solid(p, original) for p in result_samples))
    original_area = sum(face.Area for face in original.Faces)
    result_area = sum(face.Area for face in result.Faces)
    volume_difference = abs(original.Volume - result.Volume)
    area_difference = abs(original_area - result_area)
    if (distance > SURFACE_TOLERANCE
            or volume_difference > max(1e-6, original.Volume * RELATIVE_QUANTITY_TOLERANCE)
            or area_difference > max(1e-6, original_area * RELATIVE_QUANTITY_TOLERANCE)):
        raise ValueError("Geometry validation failed for roof {0}: surface {1} mm, "
                         "volume difference {2} ft3, area difference {3} ft2.".format(
                             element_id(source["roof"]), distance * MM_PER_FOOT,
                             volume_difference, area_difference))
    return {"roof_id": element_id(source["roof"]), "floor_id": element_id(floor),
            "openings": opening_map, "shape_vertices": len(source["points"]),
            "split_lines": len(source["edges"]), "surface_distance_mm": distance * MM_PER_FOOT,
            "surface_samples": len(original_samples) + len(result_samples),
            "source_volume_ft3": original.Volume, "floor_volume_ft3": result.Volume,
            "volume_difference_ft3": volume_difference,
            "source_surface_ft2": original_area, "floor_surface_ft2": result_area,
            "vertex_error_mm": vertex_error * MM_PER_FOOT,
            "stored_point_adjustment_mm": source["adjustment"] * MM_PER_FOOT}


def main():
    doc = __doc__
    if doc is None or doc.IsFamilyDocument or doc.IsReadOnly or doc.IsModifiable:
        raise ValueError("An editable project with no active transaction is required.")
    dry_run, roofs = read_inputs(doc)
    openings = list(FilteredElementCollector(doc).OfClass(Opening))
    sources = [prepare_roof(doc, roof, openings) for roof in roofs]
    floor_types = list(FilteredElementCollector(doc).OfClass(FloorType))
    templates = sorted([ft for ft in floor_types if not ft.IsFoundationSlab], key=element_id)
    if not templates:
        raise ValueError("The project must contain an architectural FloorType.")
    used_names = set(element_name(ft) for ft in floor_types)
    derived_types, report = {}, []
    failures = CaptureFailures()
    group = TransactionGroup(doc, "BIMO: Create Floors from roofs")
    group.Start()
    transaction = None
    try:
        transaction = Transaction(doc, "Create and validate Floors and openings")
        transaction.Start()
        options = transaction.GetFailureHandlingOptions()
        options.SetFailuresPreprocessor(failures)
        options.SetClearAfterRollback(True)
        transaction.SetFailureHandlingOptions(options)
        for source in sources:
            type_id = element_id(source["type"])
            if type_id not in derived_types:
                derived_types[type_id] = new_floor_type(
                    doc, templates[0], source["type"], source["structure"], used_names)
            floor, opening_map, vertex_error = create_floor(doc, source, derived_types[type_id])
            report.append(verify_floor(source, floor, opening_map, vertex_error))
        if transaction.Commit() != TransactionStatus.Committed:
            raise RuntimeError("Revit rolled back creation: {0}".format(failures.messages))
        transaction = None
        # Commit processing can change geometry: verify again before assimilating.
        for source, item in zip(sources, report):
            verify_floor(source, doc.GetElement(ElementId(item["floor_id"])),
                         item["openings"], item["vertex_error_mm"] / MM_PER_FOOT)
        if dry_run:
            group.RollBack()
        elif group.Assimilate() != TransactionStatus.Committed:
            raise RuntimeError("Could not commit the conversion transaction group.")
        return {"dry_run": dry_run, "floor_count": len(report),
                "created_ids_are_persistent": not dry_run,
                "source_roofs_retained": True, "report": report, "warnings": failures.messages}
    except:
        if transaction is not None and transaction.GetStatus() == TransactionStatus.Started:
            transaction.RollBack()
        if group.GetStatus() == TransactionStatus.Started:
            group.RollBack()
        raise


OUT = main()
