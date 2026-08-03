"""Create a Revit Toposolid from points sampled along selected model curves.

BIMO Run Python contract:
- Engine: IronPython
- IN[0]: sampling step in millimetres (optional, default: 1000)
- IN[1]: XY duplicate tolerance in millimetres (optional, default: 1)
- IN[2]: exact Toposolid type name (optional)
- IN[3]: exact level name (optional)
- OUT: human-readable result
"""

import math

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    Level,
    ModelCurve,
    Toposolid,
    ToposolidType,
    Transaction,
    XYZ,
)
from System.Collections.Generic import List


MILLIMETRES_PER_FOOT = 304.8
MAXIMUM_SAMPLED_POINTS = 50000


def _input(index, default_value=None):
    if index >= len(IN):
        return default_value

    value = IN[index]
    if value is None or str(value).strip() == "":
        return default_value

    return value


def _positive_float(value, input_name):
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("{0} must be a number.".format(input_name))

    if number <= 0:
        raise ValueError("{0} must be greater than zero.".format(input_name))

    return number


def _sample_curve(curve, step_feet, maximum_points):
    try:
        segment_count = max(1, int(math.ceil(curve.Length / step_feet)))
        if segment_count + 1 > maximum_points:
            raise ValueError(
                "Sampling would exceed the {0}-point safety limit. Increase IN[0].".format(
                    MAXIMUM_SAMPLED_POINTS
                )
            )
        return [
            curve.Evaluate(float(index) / float(segment_count), True)
            for index in range(segment_count + 1)
        ]
    except ValueError:
        raise
    except Exception:
        points = list(curve.Tessellate())
        if len(points) > maximum_points:
            raise ValueError(
                "Tessellation would exceed the {0}-point safety limit.".format(
                    MAXIMUM_SAMPLED_POINTS
                )
            )
        return points


def _deduplicate_xy(points, tolerance_feet):
    buckets = {}

    for point in points:
        key = (
            int(round(point.X / tolerance_feet)),
            int(round(point.Y / tolerance_feet)),
        )

        if key not in buckets:
            buckets[key] = [point.X, point.Y, point.Z, 1]
            continue

        bucket = buckets[key]
        bucket[0] += point.X
        bucket[1] += point.Y
        bucket[2] += point.Z
        bucket[3] += 1

    unique_points = []
    for key in sorted(buckets.keys()):
        x_sum, y_sum, z_sum, count = buckets[key]
        unique_points.append(XYZ(x_sum / count, y_sum / count, z_sum / count))

    return unique_points


def _element_by_name(elements, requested_name, element_kind):
    if requested_name:
        normalized_name = requested_name.lower()
        for element in elements:
            if str(element.Name).lower() == normalized_name:
                return element

        raise ValueError(
            "{0} named '{1}' was not found.".format(element_kind, requested_name)
        )

    if not elements:
        raise ValueError("No {0} is available in the active project.".format(element_kind))

    return sorted(elements, key=lambda element: str(element.Name).lower())[0]


def _resolve_level(doc, requested_name, minimum_z):
    levels = list(FilteredElementCollector(doc).OfClass(Level))

    if requested_name:
        return _element_by_name(levels, requested_name, "Level")

    active_view = doc.ActiveView
    if active_view is not None and active_view.GenLevel is not None:
        return active_view.GenLevel

    if not levels:
        raise ValueError("No Level is available in the active project.")

    return min(levels, key=lambda level: abs(level.Elevation - minimum_z))


def _create_toposolid():
    step_mm = _positive_float(_input(0, 1000.0), "IN[0] sampling step")
    tolerance_mm = _positive_float(_input(1, 1.0), "IN[1] XY tolerance")
    requested_type_name = str(_input(2, "")).strip()
    requested_level_name = str(_input(3, "")).strip()

    selected_ids = list(__selection__.GetElementIds())
    if not selected_ids:
        raise ValueError(
            "Select model lines with real Z elevations before running this script."
        )

    curves = []
    ignored_count = 0
    for element_id in selected_ids:
        element = __doc__.GetElement(element_id)
        if isinstance(element, ModelCurve) and element.GeometryCurve is not None:
            curves.append(element.GeometryCurve)
        else:
            ignored_count += 1

    if not curves:
        raise ValueError(
            "The selection contains no model curves. Detail lines and imported CAD "
            "geometry are not supported."
        )

    step_feet = step_mm / MILLIMETRES_PER_FOOT
    tolerance_feet = tolerance_mm / MILLIMETRES_PER_FOOT

    sampled_points = []
    for curve in curves:
        remaining_capacity = MAXIMUM_SAMPLED_POINTS - len(sampled_points)
        if remaining_capacity < 2:
            raise ValueError(
                "Sampling would exceed the {0}-point safety limit. Increase IN[0].".format(
                    MAXIMUM_SAMPLED_POINTS
                )
            )
        sampled_points.extend(_sample_curve(curve, step_feet, remaining_capacity))

    points = _deduplicate_xy(sampled_points, tolerance_feet)
    if len(points) < 3:
        raise ValueError("At least three unique XY points are required.")

    min_x = min(point.X for point in points)
    max_x = max(point.X for point in points)
    min_y = min(point.Y for point in points)
    max_y = max(point.Y for point in points)
    min_z = min(point.Z for point in points)
    max_z = max(point.Z for point in points)

    if max_x - min_x < tolerance_feet or max_y - min_y < tolerance_feet:
        raise ValueError(
            "The sampled points are collinear in XY. A Toposolid requires an area."
        )

    toposolid_types = list(FilteredElementCollector(__doc__).OfClass(ToposolidType))
    toposolid_type = _element_by_name(
        toposolid_types, requested_type_name, "Toposolid type"
    )
    level = _resolve_level(__doc__, requested_level_name, min_z)

    net_points = List[XYZ]()
    for point in points:
        net_points.Add(point)

    transaction = Transaction(__doc__, "Create Toposolid from selected model lines")
    started = False
    try:
        transaction.Start()
        started = True
        toposolid = Toposolid.Create(
            __doc__, net_points, toposolid_type.Id, level.Id
        )
        transaction.Commit()
        started = False
    except Exception:
        if started:
            try:
                transaction.RollBack()
            except Exception:
                pass
        raise

    return (
        "Toposolid created. Id: {0}; curves: {1}; points: {2}; ignored "
        "elements: {3}; type: {4}; level: {5}; Z range: {6:.3f}-{7:.3f} m."
    ).format(
        toposolid.Id,
        len(curves),
        len(points),
        ignored_count,
        toposolid_type.Name,
        level.Name,
        min_z * 0.3048,
        max_z * 0.3048,
    )


OUT = _create_toposolid()
