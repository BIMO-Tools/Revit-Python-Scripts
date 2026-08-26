"""Import a raster image into the active Revit view.

BIMO Run Python contract:
- Engine: IronPython
- IN[0]: image file path (required)
- IN[1]: target width as a fraction of the visible view width (optional, default: 0.4)
- IN[2]: copy the image beside the active Revit document (optional, default: true)
- OUT: structured details about the imported image
"""

from Autodesk.Revit.DB import (
    BoxPlacement,
    ImageInstance,
    ImagePlacementOptions,
    ImageType,
    ImageTypeOptions,
    ImageTypeSource,
    Transaction,
)
from System.IO import File, Path


MINIMUM_WIDTH_FRACTION = 0.01
MAXIMUM_WIDTH_FRACTION = 1.0
MAXIMUM_COLLISION_ATTEMPTS = 1000


def _input(index, default_value=None):
    if index >= len(IN):
        return default_value

    value = IN[index]
    if value is None or str(value).strip() == "":
        return default_value

    return value


def _width_fraction(value):
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("IN[1] width fraction must be a number.")

    if number < MINIMUM_WIDTH_FRACTION or number > MAXIMUM_WIDTH_FRACTION:
        raise ValueError(
            "IN[1] width fraction must be between {0} and {1}.".format(
                MINIMUM_WIDTH_FRACTION, MAXIMUM_WIDTH_FRACTION
            )
        )

    return number


def _boolean(value, input_name):
    normalized = str(value).strip().lower()
    if normalized in ("true", "1", "yes", "y", "on"):
        return True
    if normalized in ("false", "0", "no", "n", "off"):
        return False

    raise ValueError("{0} must be true or false.".format(input_name))


def _available_target_path(directory, file_name):
    candidate = Path.Combine(directory, file_name)
    if not File.Exists(candidate):
        return candidate

    stem = Path.GetFileNameWithoutExtension(file_name)
    extension = Path.GetExtension(file_name)
    for index in range(1, MAXIMUM_COLLISION_ATTEMPTS + 1):
        candidate = Path.Combine(
            directory, "{0}_{1}{2}".format(stem, index, extension)
        )
        if not File.Exists(candidate):
            return candidate

    raise ValueError(
        "Could not choose a free file name beside the Revit document after {0} attempts.".format(
            MAXIMUM_COLLISION_ATTEMPTS
        )
    )


def _prepare_image_path(source_path, copy_to_document_folder):
    absolute_source = Path.GetFullPath(source_path)
    if not File.Exists(absolute_source):
        raise ValueError("Image file does not exist: {0}".format(absolute_source))

    if not copy_to_document_folder:
        return absolute_source, False

    document_path = str(__doc__.PathName or "").strip()
    if not document_path:
        raise ValueError(
            "The active Revit document must be saved before the image can be copied beside it."
        )

    document_directory = Path.GetDirectoryName(Path.GetFullPath(document_path))
    source_directory = Path.GetDirectoryName(absolute_source)
    if source_directory.lower() == document_directory.lower():
        return absolute_source, False

    target_path = _available_target_path(
        document_directory, Path.GetFileName(absolute_source)
    )
    File.Copy(absolute_source, target_path, False)
    return target_path, True


def _active_view_placement(width_fraction):
    view = __doc__.ActiveView
    if view is None or not ImageInstance.IsValidView(view):
        raise ValueError("The active view cannot contain raster images.")

    ui_views = [
        ui_view
        for ui_view in __uidoc__.GetOpenUIViews()
        if ui_view.ViewId == view.Id
    ]
    if not ui_views:
        raise ValueError("The active UI view is not available for image placement.")

    corners = ui_views[0].GetZoomCorners()
    first = corners[0]
    second = corners[1]
    center = (first + second) * 0.5
    visible_width = abs((second - first).DotProduct(view.RightDirection))
    if visible_width <= 0:
        raise ValueError("The visible view width could not be determined.")

    return view, center, visible_width * width_fraction


def _import_image():
    source_path = str(_input(0, "")).strip()
    if not source_path:
        raise ValueError("IN[0] image file path is required.")

    width_fraction = _width_fraction(_input(1, 0.4))
    copy_to_document_folder = _boolean(
        _input(2, True), "IN[2] copy-to-document-folder"
    )

    view, center, target_width = _active_view_placement(width_fraction)
    image_path, copied = _prepare_image_path(
        source_path, copy_to_document_folder
    )

    transaction = Transaction(__doc__, "Import image into active view")
    started = False
    try:
        transaction.Start()
        started = True

        type_options = ImageTypeOptions(
            image_path, False, ImageTypeSource.Import
        )
        image_type = ImageType.Create(__doc__, type_options)
        placement = ImagePlacementOptions(center, BoxPlacement.Center)
        image = ImageInstance.Create(
            __doc__, view, image_type.Id, placement
        )
        image.LockProportions = True
        image.Width = target_width

        transaction.Commit()
        started = False
    except Exception:
        if started:
            try:
                transaction.RollBack()
            except Exception:
                pass
        raise

    return {
        "imageInstanceId": image.Id.IntegerValue,
        "imageTypeId": image_type.Id.IntegerValue,
        "viewName": view.Name,
        "storedPath": image_type.Path,
        "copiedBesideDocument": copied,
        "widthFeet": image.Width,
        "heightFeet": image.Height,
    }


OUT = _import_image()
