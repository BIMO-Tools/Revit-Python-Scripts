"""Create a model-line exterior contour from a horizontal linked-STL slice.

BIMO Run Python contract:
- Engine: IronPython
- Selection: exactly one linked ImportInstance containing mesh geometry
- IN[0]: exact level name (optional, default: L3)
- IN[1]: slice offset above the level in millimetres (optional, default: 1500)
- IN[2]: XY endpoint snap in millimetres (optional, default: 25)
- IN[3]: polygon gap-healing distance in millimetres (optional, default: 250)
- IN[4]: contour simplification tolerance in millimetres (optional, default: 50)
- IN[5]: minimum accepted contour area in square metres (optional, default: 10)
- IN[6]: semicolon-separated .NET assembly paths (optional if NTS is loaded)
- IN[7]: model-line style name (optional, default: BIMO_STL_Contour)
- OUT: result dictionary
"""

import clr

from Autodesk.Revit.DB import (
    BuiltInCategory,
    Color,
    FilteredElementCollector,
    GeometryInstance,
    GraphicsStyleType,
    ImportInstance,
    Level,
    Line,
    Mesh,
    Options,
    Plane,
    SketchPlane,
    Transaction,
    XYZ,
)
from System import Array
from System.IO import File


MILLIMETRES_PER_FOOT = 304.8
SQUARE_METRES_PER_SQUARE_FOOT = 0.09290304
MAXIMUM_RAW_SLICE_SEGMENTS = 2000000


def _input(index, default_value=None):
    if index >= len(IN):
        return default_value

    value = IN[index]
    if value is None or str(value).strip() == "":
        return default_value

    return value


def _number(value, input_name, minimum=None, minimum_inclusive=False):
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("{0} must be a number.".format(input_name))

    if minimum is not None:
        invalid = number < minimum if minimum_inclusive else number <= minimum
        if invalid:
            comparison = "at least" if minimum_inclusive else "greater than"
            raise ValueError(
                "{0} must be {1} {2}.".format(input_name, comparison, minimum)
            )

    return number


def _import_nettopologysuite_types():
    from NetTopologySuite.Geometries import (
        Coordinate,
        Geometry,
        GeometryFactory,
        LineString,
    )
    from NetTopologySuite.Operation.Polygonize import Polygonizer
    from NetTopologySuite.Simplify import TopologyPreservingSimplifier

    return (
        Coordinate,
        Geometry,
        GeometryFactory,
        LineString,
        Polygonizer,
        TopologyPreservingSimplifier,
    )


def _load_nettopologysuite(assembly_paths_value):
    try:
        return _import_nettopologysuite_types()
    except Exception:
        pass

    assembly_paths = [
        item.strip().strip('"')
        for item in str(assembly_paths_value or "").split(";")
        if item.strip()
    ]
    if not assembly_paths:
        raise ValueError(
            "NetTopologySuite is not loaded. Provide IN[6] with semicolon-separated "
            "full paths to its .NET assemblies; see the paired documentation."
        )

    for assembly_path in assembly_paths:
        if not File.Exists(assembly_path):
            raise ValueError(
                "The assembly supplied in IN[6] does not exist: {0}".format(
                    assembly_path
                )
            )
        clr.AddReferenceToFileAndPath(assembly_path)

    try:
        return _import_nettopologysuite_types()
    except Exception as exception:
        raise ValueError(
            "NetTopologySuite could not be loaded from IN[6]. Supply prerequisite "
            "assemblies first and NetTopologySuite.dll last. Details: {0}".format(
                exception
            )
        )


def _resolve_level(doc, requested_name):
    levels = list(FilteredElementCollector(doc).OfClass(Level))
    matches = [
        level
        for level in levels
        if str(level.Name).lower() == requested_name.lower()
    ]

    if not matches:
        raise ValueError("Level named '{0}' was not found.".format(requested_name))
    if len(matches) > 1:
        raise ValueError(
            "More than one Level is named '{0}'. Rename the duplicate levels first.".format(
                requested_name
            )
        )

    return matches[0]


def _selected_linked_import_instance(doc):
    selected_ids = list(__uidoc__.Selection.GetElementIds())
    if len(selected_ids) != 1:
        raise ValueError(
            "Select exactly one linked STL ImportInstance before running the script."
        )

    element = doc.GetElement(selected_ids[0])
    if not isinstance(element, ImportInstance) or not element.IsLinked:
        raise ValueError(
            "The selected element must be a linked ImportInstance containing mesh "
            "geometry."
        )

    return element


def _meshes_from_geometry(geometry):
    meshes = []
    for geometry_object in geometry:
        if isinstance(geometry_object, Mesh):
            meshes.append(geometry_object)
        elif isinstance(geometry_object, GeometryInstance):
            instance_geometry = geometry_object.GetInstanceGeometry()
            if instance_geometry is not None:
                meshes.extend(_meshes_from_geometry(instance_geometry))
    return meshes


def _append_unique_point(points, point, tolerance_feet):
    for existing in points:
        if (
            abs(existing[0] - point[0]) <= tolerance_feet
            and abs(existing[1] - point[1]) <= tolerance_feet
        ):
            return
    points.append(point)


def _triangle_slice_segment(triangle, slice_z, tolerance_feet):
    vertices = [triangle.get_Vertex(index) for index in range(3)]
    distances = [vertex.Z - slice_z for vertex in vertices]

    if all(abs(distance) <= tolerance_feet for distance in distances):
        return None
    if all(distance > tolerance_feet for distance in distances):
        return None
    if all(distance < -tolerance_feet for distance in distances):
        return None

    intersections = []
    for start_index, end_index in ((0, 1), (1, 2), (2, 0)):
        start = vertices[start_index]
        end = vertices[end_index]
        start_distance = distances[start_index]
        end_distance = distances[end_index]

        if abs(start_distance) <= tolerance_feet and abs(end_distance) <= tolerance_feet:
            continue
        if abs(start_distance) <= tolerance_feet:
            _append_unique_point(intersections, (start.X, start.Y), tolerance_feet)
            continue
        if abs(end_distance) <= tolerance_feet:
            _append_unique_point(intersections, (end.X, end.Y), tolerance_feet)
            continue
        if (start_distance < 0 < end_distance) or (
            end_distance < 0 < start_distance
        ):
            parameter = start_distance / (start_distance - end_distance)
            point = (
                start.X + (end.X - start.X) * parameter,
                start.Y + (end.Y - start.Y) * parameter,
            )
            _append_unique_point(intersections, point, tolerance_feet)

    if len(intersections) < 2:
        return None
    if len(intersections) == 2:
        return intersections[0], intersections[1]

    longest_pair = None
    longest_distance_squared = -1.0
    for first_index in range(len(intersections)):
        for second_index in range(first_index + 1, len(intersections)):
            first = intersections[first_index]
            second = intersections[second_index]
            distance_squared = (first[0] - second[0]) ** 2 + (
                first[1] - second[1]
            ) ** 2
            if distance_squared > longest_distance_squared:
                longest_distance_squared = distance_squared
                longest_pair = first, second

    return longest_pair


def _slice_meshes(meshes, slice_z, tolerance_feet):
    segments = []
    triangle_count = 0

    for mesh in meshes:
        triangle_count += mesh.NumTriangles
        for triangle_index in range(mesh.NumTriangles):
            segment = _triangle_slice_segment(
                mesh.get_Triangle(triangle_index), slice_z, tolerance_feet
            )
            if segment is None:
                continue

            segments.append(segment)
            if len(segments) > MAXIMUM_RAW_SLICE_SEGMENTS:
                raise ValueError(
                    "The slice exceeded the {0}-segment safety limit.".format(
                        MAXIMUM_RAW_SLICE_SEGMENTS
                    )
                )

    if not segments:
        raise ValueError(
            "The selected mesh does not intersect the requested horizontal plane."
        )

    return segments, triangle_count


def _snap_and_deduplicate_segments(segments, snap_feet):
    unique_segments = {}
    collapsed_segment_count = 0
    duplicate_segment_count = 0

    for start, end in segments:
        start_key = (
            int(round(start[0] / snap_feet)),
            int(round(start[1] / snap_feet)),
        )
        end_key = (
            int(round(end[0] / snap_feet)),
            int(round(end[1] / snap_feet)),
        )
        if start_key == end_key:
            collapsed_segment_count += 1
            continue

        if end_key < start_key:
            start_key, end_key = end_key, start_key
        segment_key = start_key, end_key
        if segment_key in unique_segments:
            duplicate_segment_count += 1
            continue

        unique_segments[segment_key] = (
            (start_key[0] * snap_feet, start_key[1] * snap_feet),
            (end_key[0] * snap_feet, end_key[1] * snap_feet),
        )

    if not unique_segments:
        raise ValueError("Endpoint snapping left no usable slice segments.")

    return (
        [unique_segments[key] for key in sorted(unique_segments.keys())],
        collapsed_segment_count,
        duplicate_segment_count,
    )


def _polygon_members(geometry):
    if geometry is None or geometry.IsEmpty:
        return []
    geometry_type = str(geometry.GeometryType)
    if geometry_type == "Polygon":
        return [geometry]
    if geometry_type not in ("MultiPolygon", "GeometryCollection"):
        return []

    polygons = []
    for geometry_index in range(geometry.NumGeometries):
        polygons.extend(_polygon_members(geometry.GetGeometryN(geometry_index)))
    return polygons


def _ring_area_square_feet(ring):
    coordinates = ring.Coordinates
    origin = coordinates[0]
    twice_signed_area = 0.0
    for index in range(len(coordinates) - 1):
        start = coordinates[index]
        end = coordinates[index + 1]
        start_x = start.X - origin.X
        start_y = start.Y - origin.Y
        end_x = end.X - origin.X
        end_y = end.Y - origin.Y
        twice_signed_area += start_x * end_y - end_x * start_y
    return abs(twice_signed_area) * 0.5


def _largest_exterior_polygon(geometry, stage_name):
    polygons = _polygon_members(geometry)
    if not polygons:
        raise ValueError("{0} produced no polygon.".format(stage_name))

    return (
        max(polygons, key=lambda polygon: _ring_area_square_feet(polygon.ExteriorRing)),
        len(polygons),
    )


def _build_contour(
    segments,
    coordinate_type,
    geometry_type,
    geometry_factory_type,
    line_string_type,
    polygonizer_type,
    simplifier_type,
    gap_healing_feet,
    simplify_feet,
):
    geometry_factory = geometry_factory_type()
    line_strings = []
    for start, end in segments:
        coordinates = Array[coordinate_type](
            [
                coordinate_type(start[0], start[1]),
                coordinate_type(end[0], end[1]),
            ]
        )
        line_strings.append(geometry_factory.CreateLineString(coordinates))

    multi_line = geometry_factory.CreateMultiLineString(
        Array[line_string_type](line_strings)
    )
    noded_lines = multi_line.Union()

    polygonizer = polygonizer_type(False)
    polygonizer.Add(noded_lines)
    polygons = list(polygonizer.GetPolygons())
    dangle_count = len(list(polygonizer.GetDangles()))
    cut_edge_count = len(list(polygonizer.GetCutEdges()))
    invalid_ring_count = len(list(polygonizer.GetInvalidRingLines()))

    if not polygons:
        raise ValueError(
            "Polygonization produced no polygons (dangles: {0}, cut edges: {1}, "
            "invalid rings: {2}).".format(
                dangle_count, cut_edge_count, invalid_ring_count
            )
        )

    polygon_collection = geometry_factory.CreateGeometryCollection(
        Array[geometry_type](polygons)
    )
    healed_geometry = polygon_collection
    if gap_healing_feet > 0:
        healed_geometry = healed_geometry.Buffer(gap_healing_feet).Buffer(
            -gap_healing_feet
        )

    healed_polygon, healed_polygon_count = _largest_exterior_polygon(
        healed_geometry, "Gap healing"
    )
    healed_shell_area_square_feet = _ring_area_square_feet(
        healed_polygon.ExteriorRing
    )

    final_geometry = healed_polygon
    if simplify_feet > 0:
        final_geometry = simplifier_type.Simplify(healed_polygon, simplify_feet)
    final_polygon, final_polygon_count = _largest_exterior_polygon(
        final_geometry, "Simplification"
    )

    diagnostics = {
        "noded_component_count": noded_lines.NumGeometries,
        "polygon_count": len(polygons),
        "dangle_count": dangle_count,
        "cut_edge_count": cut_edge_count,
        "invalid_ring_count": invalid_ring_count,
        "healed_polygon_count": healed_polygon_count,
        "healed_shell_area_square_feet": healed_shell_area_square_feet,
        "final_polygon_count": final_polygon_count,
    }
    return final_polygon, diagnostics


def _clean_ring_coordinates(coordinates, minimum_segment_length):
    points = []
    for coordinate in coordinates:
        point = (coordinate.X, coordinate.Y)
        if not points:
            points.append(point)
            continue

        previous = points[-1]
        distance_squared = (point[0] - previous[0]) ** 2 + (
            point[1] - previous[1]
        ) ** 2
        if distance_squared >= minimum_segment_length ** 2:
            points.append(point)

    while len(points) > 1:
        first = points[0]
        last = points[-1]
        closing_distance_squared = (first[0] - last[0]) ** 2 + (
            first[1] - last[1]
        ) ** 2
        if closing_distance_squared >= minimum_segment_length ** 2:
            break
        points.pop()

    if len(points) < 3:
        raise ValueError("The final contour contains fewer than three vertices.")

    return points


def _line_subcategory(doc, style_name):
    lines_category = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Lines)
    for subcategory in lines_category.SubCategories:
        if str(subcategory.Name).lower() == style_name.lower():
            return subcategory, False

    subcategory = doc.Settings.Categories.NewSubcategory(lines_category, style_name)
    subcategory.LineColor = Color(0, 200, 255)
    return subcategory, True


def _create_model_lines(doc, contour_points, slice_z, style_name):
    transaction = Transaction(doc, "Create linked STL polygonized slice contour")
    started = False
    try:
        transaction.Start()
        started = True

        line_subcategory, style_created = _line_subcategory(doc, style_name)
        graphics_style = line_subcategory.GetGraphicsStyle(
            GraphicsStyleType.Projection
        )
        plane = Plane.CreateByNormalAndOrigin(XYZ.BasisZ, XYZ(0.0, 0.0, slice_z))
        sketch_plane = SketchPlane.Create(doc, plane)

        model_line_ids = []
        for point_index in range(len(contour_points)):
            start_xy = contour_points[point_index]
            end_xy = contour_points[(point_index + 1) % len(contour_points)]
            start = XYZ(start_xy[0], start_xy[1], slice_z)
            end = XYZ(end_xy[0], end_xy[1], slice_z)
            model_curve = doc.Create.NewModelCurve(
                Line.CreateBound(start, end), sketch_plane
            )
            model_curve.LineStyle = graphics_style
            model_line_ids.append(model_curve.Id.IntegerValue)

        transaction.Commit()
        started = False
        return model_line_ids, sketch_plane.Id.IntegerValue, style_created
    except Exception:
        if started:
            try:
                transaction.RollBack()
            except Exception:
                pass
        raise


def _create_contour():
    requested_level_name = str(_input(0, "L3")).strip()
    if not requested_level_name:
        raise ValueError("IN[0] level name must not be empty.")

    slice_offset_mm = _number(_input(1, 1500.0), "IN[1] slice offset")
    endpoint_snap_mm = _number(_input(2, 25.0), "IN[2] XY endpoint snap", 0.0)
    gap_healing_mm = _number(
        _input(3, 250.0), "IN[3] polygon gap healing", 0.0, True
    )
    simplify_mm = _number(
        _input(4, 50.0), "IN[4] simplification tolerance", 0.0, True
    )
    minimum_area_m2 = _number(
        _input(5, 10.0), "IN[5] minimum contour area", 0.0, True
    )
    assembly_paths = str(_input(6, "")).strip()
    style_name = str(_input(7, "BIMO_STL_Contour")).strip()
    if not style_name:
        raise ValueError("IN[7] model-line style name must not be empty.")

    (
        coordinate_type,
        geometry_type,
        geometry_factory_type,
        line_string_type,
        polygonizer_type,
        simplifier_type,
    ) = _load_nettopologysuite(assembly_paths)

    doc = __uidoc__.Document
    level = _resolve_level(doc, requested_level_name)
    linked_import = _selected_linked_import_instance(doc)
    slice_z = level.ProjectElevation + slice_offset_mm / MILLIMETRES_PER_FOOT

    options = Options()
    options.ComputeReferences = False
    options.IncludeNonVisibleObjects = True
    source_geometry = linked_import.get_Geometry(options)
    if source_geometry is None:
        raise ValueError("The selected linked import has no readable geometry.")

    meshes = _meshes_from_geometry(source_geometry)
    if not meshes:
        raise ValueError("The selected linked import contains no mesh geometry.")

    intersection_tolerance_feet = 0.01 / MILLIMETRES_PER_FOOT
    raw_segments, triangle_count = _slice_meshes(
        meshes, slice_z, intersection_tolerance_feet
    )

    endpoint_snap_feet = endpoint_snap_mm / MILLIMETRES_PER_FOOT
    (
        unique_segments,
        collapsed_segment_count,
        duplicate_segment_count,
    ) = _snap_and_deduplicate_segments(raw_segments, endpoint_snap_feet)

    gap_healing_feet = gap_healing_mm / MILLIMETRES_PER_FOOT
    simplify_feet = simplify_mm / MILLIMETRES_PER_FOOT
    contour_polygon, diagnostics = _build_contour(
        unique_segments,
        coordinate_type,
        geometry_type,
        geometry_factory_type,
        line_string_type,
        polygonizer_type,
        simplifier_type,
        gap_healing_feet,
        simplify_feet,
    )

    final_shell_area_square_feet = _ring_area_square_feet(
        contour_polygon.ExteriorRing
    )
    minimum_area_square_feet = minimum_area_m2 / SQUARE_METRES_PER_SQUARE_FOOT
    if final_shell_area_square_feet < minimum_area_square_feet:
        raise ValueError(
            "The largest exterior contour is {0:.3f} m2, below the IN[5] "
            "minimum of {1:.3f} m2.".format(
                final_shell_area_square_feet * SQUARE_METRES_PER_SQUARE_FOOT,
                minimum_area_m2,
            )
        )

    minimum_segment_length = max(
        doc.Application.ShortCurveTolerance, 0.1 / MILLIMETRES_PER_FOOT
    )
    contour_points = _clean_ring_coordinates(
        contour_polygon.ExteriorRing.Coordinates, minimum_segment_length
    )
    model_line_ids, sketch_plane_id, style_created = _create_model_lines(
        doc, contour_points, slice_z, style_name
    )

    return {
        "source_element_id": linked_import.Id.IntegerValue,
        "level": level.Name,
        "slice_offset_mm": slice_offset_mm,
        "slice_elevation_mm": slice_z * MILLIMETRES_PER_FOOT,
        "mesh_count": len(meshes),
        "triangle_count": triangle_count,
        "raw_segment_count": len(raw_segments),
        "collapsed_segment_count": collapsed_segment_count,
        "duplicate_segment_count": duplicate_segment_count,
        "unique_segment_count": len(unique_segments),
        "endpoint_snap_mm": endpoint_snap_mm,
        "noded_component_count": diagnostics["noded_component_count"],
        "polygon_count": diagnostics["polygon_count"],
        "dangle_count": diagnostics["dangle_count"],
        "cut_edge_count": diagnostics["cut_edge_count"],
        "invalid_ring_count": diagnostics["invalid_ring_count"],
        "gap_healing_mm": gap_healing_mm,
        "healed_polygon_count": diagnostics["healed_polygon_count"],
        "healed_shell_area_m2": diagnostics["healed_shell_area_square_feet"]
        * SQUARE_METRES_PER_SQUARE_FOOT,
        "simplify_mm": simplify_mm,
        "final_polygon_count": diagnostics["final_polygon_count"],
        "final_shell_area_m2": final_shell_area_square_feet
        * SQUARE_METRES_PER_SQUARE_FOOT,
        "model_line_count": len(model_line_ids),
        "model_line_ids": model_line_ids,
        "sketch_plane_id": sketch_plane_id,
        "line_style": style_name,
        "line_style_created": style_created,
    }


OUT = _create_contour()
