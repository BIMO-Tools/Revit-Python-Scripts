from Autodesk.Revit.DB import *

# Получаем текущий документ
uidoc = __uidoc__
doc = __doc__

def get_element_volume(element):
    """ Возвращает суммарный объем валидных Solid у элемента. """
    if not isinstance(element, FamilyInstance):
        raise Exception("Element is not a FamilyInstance.")
    
    # Параметры для получения геометрии
    options = Options()
    options.ComputeReferences = True
    options.IncludeNonVisibleObjects = True

    # Получаем геометрию элемента
    geom_elem = element.get_Geometry(options)
    if not geom_elem:
        raise Exception("GeometryElement is null.")
    
    total_volume = 0  # Суммарный объем

    for geom_obj in geom_elem:
        # Если это экземпляр геометрии (GeometryInstance)
        if isinstance(geom_obj, GeometryInstance):
            symbol_geom = geom_obj.GetSymbolGeometry()
            if symbol_geom:
                for symbol_obj in symbol_geom:
                    if isinstance(symbol_obj, Solid) and symbol_obj.Volume > 0:
                        total_volume += symbol_obj.Volume  # Добавляем объем
        # Если это непосредственно Solid
        elif isinstance(geom_obj, Solid) and geom_obj.Volume > 0:
            total_volume += geom_obj.Volume  # Добавляем объем

    return total_volume


# Входные данные
selected_ids = [elId for elId in uidoc.Selection.GetElementIds()]
elements = [doc.GetElement(id) for id in selected_ids]  # Список элементов
results = []


for elem in elements:
    try:
        volume = get_element_volume(elem)
        # Конвертируем в кубометры
        results.append(volume * 0.0283168)  # Перевод из футов³ в м³
    except Exception as e:
        esults.append(str(e))  # Возвращаем ошибку для проблемных элементов


# Возвращаем результат
print(results)
