# shape_captcha_lib/shapes/community_plugins/arrow.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

# Относительные импорты должны работать, если 'community_plugins' на одном уровне с 'base_model'
from ..abc import AbstractShape, ShapeDrawingDetails 
from ...utils import geometry_utils
from ...utils import color_utils

class ArrowShape(AbstractShape):
    """
    Представление фигуры "Стрелка" как плагина для CAPTCHA.
    Направлена вверх по умолчанию (до поворота).
    Центр фигуры (cx, cy) - это точка на древке, примерно на 1/3 длины от хвоста.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "arrow"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Будет использовано для общей длины (length)
        max_primary_size_upscaled: int,   # Будет использовано для общей длины (length)
        min_secondary_size_upscaled: Optional[int] = None, # Для ширины наконечника (head_width)
        max_secondary_size_upscaled: Optional[int] = None, # Для ширины наконечника (head_width)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            length = max(20, min_primary_size_upscaled) # Стрелка должна быть достаточно длинной
        else:
            length = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        # Ширина наконечника, например, от 30% до 60% длины
        min_hw = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(int(length * 0.3), 10)
        max_hw = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_hw + 1, int(length * 0.6))
        if max_hw <= min_hw:
            head_width = max(5, min_hw)
        else:
            head_width = random.randint(min_hw, max_hw)

        # Длина наконечника как доля от общей длины
        head_length_ratio = random.uniform(0.25, 0.40)
        
        # Ширина древка как доля от ширины наконечника
        shaft_width_ratio = random.uniform(0.3, 0.6)
        
        return {
            "length": length,
            "head_width": head_width,
            "head_length_ratio": head_length_ratio,
            "shaft_width_ratio": shaft_width_ratio
        }

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        length: Optional[int] = None,
        head_width: Optional[int] = None,
        head_length_ratio: Optional[float] = None,
        shaft_width_ratio: Optional[float] = None,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if None in [length, head_width, head_length_ratio, shaft_width_ratio]:
            raise ValueError("All dimensions (length, head_width, head_length_ratio, shaft_width_ratio) must be provided for ArrowShape.")
        
        self.length: int = length
        self.head_width: int = head_width
        self.head_length_ratio: float = head_length_ratio
        self.shaft_width_ratio: float = shaft_width_ratio

        # Рассчитываем геометрию стрелки, центрированную относительно (0,0)
        # Стрелка направлена вверх (вдоль отрицательной оси Y)
        # Центр (0,0) будет примерно на 1/3 длины от хвоста на древке

        total_len = float(self.length)
        head_len = total_len * self.head_length_ratio
        shaft_len = total_len - head_len

        half_head_w = self.head_width / 2.0
        shaft_w = self.head_width * self.shaft_width_ratio
        half_shaft_w = shaft_w / 2.0

        # Задаем y-координаты точек относительно желаемого центра (0,0)
        # Пусть (0,0) - это точка на оси симметрии древка,
        # смещенная от хвоста на (1/3)*shaft_len для лучшего визуального центрирования
        y_center_offset = -shaft_len / 2.0 + shaft_len / 3.0 # Смещение "центра масс" от геометрического центра древка

        # Вершины (против часовой стрелки, начиная с острия):
        # 1. Острие наконечника
        v1_y = - (total_len / 2.0) + y_center_offset
        v1 = (0.0, v1_y)
        
        # 2. Правый внешний угол наконечника
        v2_y = v1_y + head_len
        v2 = (half_head_w, v2_y)
        
        # 3. Правый внутренний угол наконечника (переход к древку)
        v3 = (half_shaft_w, v2_y)
        
        # 4. Правый нижний угол древка (хвост)
        v4_y = v2_y + shaft_len
        v4 = (half_shaft_w, v4_y)
        
        # 5. Левый нижний угол древка (хвост)
        v5 = (-half_shaft_w, v4_y)
        
        # 6. Левый внутренний угол наконечника (переход к древку)
        v6 = (-half_shaft_w, v2_y)
        
        # 7. Левый внешний угол наконечника
        v7 = (-half_head_w, v2_y)

        self.vertices_orig_centered: List[Tuple[float, float]] = [v1, v2, v3, v4, v5, v6, v7]
        
        self.final_vertices_upscaled: List[Tuple[int, int]] = \
            geometry_utils.calculate_rotated_polygon_vertices(
                self.cx_upscaled, self.cy_upscaled,
                self.vertices_orig_centered, self.rotation_angle_rad
            )
        
        self.bbox_upscaled_coords: List[float] = \
            geometry_utils.calculate_polygon_bounding_box(self.final_vertices_upscaled)

    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,
            "cy_upscaled": self.cy_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad,
            "length": self.length,
            "head_width": self.head_width,
            "head_length_ratio": self.head_length_ratio,
            "shaft_width_ratio": self.shaft_width_ratio
        }
        return ShapeDrawingDetails(
            shape_type=self.get_shape_type(),
            color_name_or_rgb=self.color_name_or_rgb,
            params_for_storage=params_for_storage,
            bbox_upscaled=self.bbox_upscaled_coords
        )

    def draw(
        self,
        draw_context: ImageDraw.ImageDraw,
        fill_color_rgb_actual: Tuple[int, int, int],
        outline_width_upscaled: int,
        brightness_factor_for_outline: Optional[float] = 0.4,
        background_color_rgb_actual: Optional[Tuple[int, int, int]] = None
    ):
        derived_outline_color_rgb = color_utils.get_contrasting_outline_color(
            fill_color_val=fill_color_rgb_actual,
            dark_factor=brightness_factor_for_outline if brightness_factor_for_outline is not None else 0.4
        )
        draw_context.polygon(
            self.final_vertices_upscaled,
            fill=fill_color_rgb_actual,
            outline=derived_outline_color_rgb,
            width=outline_width_upscaled
        )

    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        return geometry_utils.is_point_in_polygon(
            px=point_x_upscaled, py=point_y_upscaled,
            vertices=self.final_vertices_upscaled
        )