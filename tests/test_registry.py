# tests/test_registry.py
import pytest
from typing import List
from shape_captcha_lib import registry
from shape_captcha_lib.shapes.abc import AbstractShape
from shape_captcha_lib.shapes.base_model.circle import CircleShape
from shape_captcha_lib.shapes.base_model.square import SquareShape # <--- НОВЫЙ ИМПОРТ
from shape_captcha_lib.shapes.base_model.rectangle import RectangleShape 
from shape_captcha_lib.shapes.base_model.equilateral_triangle import EquilateralTriangleShape
from shape_captcha_lib.shapes.base_model.pentagon import PentagonShape # <--- НОВЫЙ ИМПОРТ
from shape_captcha_lib.shapes.base_model.hexagon import HexagonShape   # <--- НОВЫЙ ИМПОРТ
from shape_captcha_lib.shapes.base_model.star5 import Star5Shape
from shape_captcha_lib.shapes.base_model.rhombus import RhombusShape
from shape_captcha_lib.shapes.base_model.trapezoid import TrapezoidShape
from shape_captcha_lib.shapes.base_model.cross import CrossShape
#==== 3D ====
from shape_captcha_lib.shapes.td_model.sphere import SphereShape
from shape_captcha_lib.shapes.td_model.cube import CubeShape
from shape_captcha_lib.shapes.td_model.cylinder import CylinderShape
from shape_captcha_lib.shapes.td_model.cone import ConeShape
from shape_captcha_lib.shapes.td_model.pyramid import PyramidShape
from shape_captcha_lib.shapes.td_model.cuboid import CuboidShape
from shape_captcha_lib.shapes.td_model.octahedron import OctahedronShape
from shape_captcha_lib.shapes.td_model.torus import TorusShape
from shape_captcha_lib.shapes.td_model.cross_3d import Cross3DShape
from shape_captcha_lib.shapes.td_model.star5_3d import Star5_3DShape

# Функция test_shape_discovery_and_registration (или test_circle_shape_registration)
# остается такой же, как была. Мы добавим новую для квадрата.

def test_circle_shape_is_registered(): # Переименуем для ясности, если нужно
    """Проверяет регистрацию CircleShape."""
    # discover_shapes() вызывается в shape_captcha_lib/__init__.py
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models

    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "circle" in base_model_shapes

    circle_class = registry.get_shape_class("base_model", "circle")
    assert circle_class is not None
    assert circle_class == CircleShape
    assert issubclass(circle_class, AbstractShape)
    assert circle_class.get_shape_type() == "circle"

def test_square_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию SquareShape."""
    # discover_shapes() вызывается в shape_captcha_lib/__init__.py
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models, \
        f"Модель 'base_model' должна быть зарегистрирована. Найдено: {registered_models}"

    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "square" in base_model_shapes, \
        f"Тип фигуры 'square' должен быть зарегистрирован в 'base_model'. Найдено: {base_model_shapes}"

    square_class = registry.get_shape_class("base_model", "square")
    
    assert square_class is not None, \
        "Класс SquareShape не был найден в реестре для 'base_model' и 'square'."
    
    assert square_class == SquareShape, \
        (f"Зарегистрированный класс для 'square' в 'base_model' ({square_class.__name__}) "
         f"не совпадает с импортированным SquareShape ({SquareShape.__name__}).")

    assert issubclass(square_class, AbstractShape), \
        f"Зарегистрированный класс {square_class.__name__} должен быть подклассом AbstractShape."
    
    assert hasattr(square_class, 'get_shape_type'), \
        f"Класс {square_class.__name__} должен иметь статический метод get_shape_type."
    
    try:
        shape_type_name = square_class.get_shape_type()
        assert shape_type_name == "square", \
            (f"Метод get_shape_type для {square_class.__name__} должен возвращать 'square', "
             f"а вернул '{shape_type_name}'.")
    except Exception as e:
        pytest.fail(f"Ошибка при вызове get_shape_type для {square_class.__name__}: {e}")

def test_rectangle_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию RectangleShape."""
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models

    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "rectangle" in base_model_shapes, \
        f"Тип фигуры 'rectangle' должен быть зарегистрирован. Найдено: {base_model_shapes}"

    rectangle_class = registry.get_shape_class("base_model", "rectangle")
    assert rectangle_class is not None
    assert rectangle_class == RectangleShape
    assert issubclass(rectangle_class, AbstractShape)
    assert rectangle_class.get_shape_type() == "rectangle"

def test_equilateral_triangle_shape_is_registered():
    """Проверяет регистрацию EquilateralTriangleShape."""
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models

    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "equilateral_triangle" in base_model_shapes, \
        f"Тип фигуры 'equilateral_triangle' должен быть зарегистрирован. Найдено: {base_model_shapes}"

    triangle_class = registry.get_shape_class("base_model", "equilateral_triangle")
    assert triangle_class is not None
    assert triangle_class == EquilateralTriangleShape
    assert issubclass(triangle_class, AbstractShape)
    assert triangle_class.get_shape_type() == "equilateral_triangle"

def test_pentagon_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию PentagonShape."""
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models
    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "pentagon" in base_model_shapes
    shape_class = registry.get_shape_class("base_model", "pentagon")
    assert shape_class is not None and shape_class == PentagonShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "pentagon"

def test_hexagon_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию HexagonShape."""
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models
    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "hexagon" in base_model_shapes
    shape_class = registry.get_shape_class("base_model", "hexagon")
    assert shape_class is not None and shape_class == HexagonShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "hexagon"

def test_star5_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию Star5Shape."""
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models
    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "star5" in base_model_shapes
    shape_class = registry.get_shape_class("base_model", "star5")
    assert shape_class is not None and shape_class == Star5Shape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "star5"

def test_rhombus_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию RhombusShape."""
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models
    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "rhombus" in base_model_shapes
    shape_class = registry.get_shape_class("base_model", "rhombus")
    assert shape_class is not None and shape_class == RhombusShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "rhombus"

def test_trapezoid_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию TrapezoidShape."""
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models
    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "trapezoid" in base_model_shapes
    shape_class = registry.get_shape_class("base_model", "trapezoid")
    assert shape_class is not None and shape_class == TrapezoidShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "trapezoid"

def test_cross_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию CrossShape."""
    registered_models = registry.get_all_registered_models()
    assert "base_model" in registered_models
    base_model_shapes = registry.get_model_shape_types("base_model")
    assert "cross" in base_model_shapes
    shape_class = registry.get_shape_class("base_model", "cross")
    assert shape_class is not None and shape_class == CrossShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "cross"

# ==== 3D ====

def test_sphere_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию SphereShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models, \
        f"Модель 'td_model' должна быть зарегистрирована. Найдено: {registered_models}"

    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "sphere" in td_model_shapes, \
        f"Тип фигуры 'sphere' должен быть зарегистрирован в 'td_model'. Найдено: {td_model_shapes}"
        
    shape_class = registry.get_shape_class("td_model", "sphere")
    assert shape_class is not None and shape_class == SphereShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "sphere"

def test_cube_shape_is_registered():
    """Проверяет регистрацию CubeShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "cube" in td_model_shapes
    shape_class = registry.get_shape_class("td_model", "cube")
    assert shape_class is not None and shape_class == CubeShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "cube"

def test_cylinder_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию CylinderShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "cylinder" in td_model_shapes
    shape_class = registry.get_shape_class("td_model", "cylinder")
    assert shape_class is not None and shape_class == CylinderShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "cylinder"

def test_cone_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию ConeShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "cone" in td_model_shapes
    shape_class = registry.get_shape_class("td_model", "cone")
    assert shape_class is not None and shape_class == ConeShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "cone"

def test_pyramid_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию PyramidShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "pyramid" in td_model_shapes
    shape_class = registry.get_shape_class("td_model", "pyramid")
    assert shape_class is not None and shape_class == PyramidShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "pyramid"

def test_cuboid_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию CuboidShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "cuboid" in td_model_shapes
    shape_class = registry.get_shape_class("td_model", "cuboid")
    assert shape_class is not None and shape_class == CuboidShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "cuboid"

def test_octahedron_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию OctahedronShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "octahedron" in td_model_shapes
    shape_class = registry.get_shape_class("td_model", "octahedron")
    assert shape_class is not None and shape_class == OctahedronShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "octahedron"

def test_torus_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию TorusShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "torus" in td_model_shapes
    shape_class = registry.get_shape_class("td_model", "torus")
    assert shape_class is not None and shape_class == TorusShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "torus"

def test_cross_3d_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию Cross3DShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "cross_3d" in td_model_shapes # Имя типа фигуры
    shape_class = registry.get_shape_class("td_model", "cross_3d")
    assert shape_class is not None and shape_class == Cross3DShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "cross_3d"

def test_star5_3d_shape_is_registered(): # <--- НОВАЯ ТЕСТОВАЯ ФУНКЦИЯ
    """Проверяет регистрацию Star5_3DShape."""
    registered_models = registry.get_all_registered_models()
    assert "td_model" in registered_models
    td_model_shapes = registry.get_model_shape_types("td_model")
    assert "star5_3d" in td_model_shapes
    shape_class = registry.get_shape_class("td_model", "star5_3d")
    assert shape_class is not None and shape_class == Star5_3DShape
    assert issubclass(shape_class, AbstractShape)
    assert shape_class.get_shape_type() == "star5_3d"
