# shape_captcha_lib/shapes/base_model/equilateral_triangle.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

class EquilateralTriangleShape(AbstractShape):
    """
    Представление фигуры "Равносторонний Треугольник" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "equilateral_triangle"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Будет использовано для длины стороны (side_length)
        max_primary_size_upscaled: int,   # Будет использовано для длины стороны (side_length)
        min_secondary_size_upscaled: Optional[int] = None, # Не используется
        max_secondary_size_upscaled: Optional[int] = None, # Не используется
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует длину стороны для равностороннего треугольника.
        """
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            side_length = max(3, min_primary_size_upscaled) # Мин. сторона 3 для норм. полигона
        else:
            side_length = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)
        return {"side_length": side_length}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        side_length: Optional[int] = None,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if side_length is None:
            raise ValueError("Side length ('side_length') must be provided for EquilateralTriangleShape.")
        if not (isinstance(side_length, int) and side_length > 0): # Минимальная сторона для полигона
            raise ValueError(f"Side length must be a positive integer, got {side_length}.")
            
        self.side_length_upscaled: int = side_length
        
        # Рассчитываем радиус описанной окружности R = side_length / sqrt(3)
        # R = self.side_length_upscaled / math.sqrt(3)
        # Альтернативный расчет из старого кода:
        # h_triangle = (self.side_length_upscaled * math.sqrt(3)) / 2.0
        # r_circumscribed = (2.0 / 3.0) * h_triangle
        # Используем geometry_utils.calculate_regular_polygon_centered_vertices
        # Для равностороннего треугольника num_vertices = 3.
        # start_angle_offset_rad=0 для вершины "сверху".
        
        # Радиус описанной окружности (R) для равностороннего треугольника: R = a / √3
        # Где 'a' - это side_length.
        radius_circumscribed = self.side_length_upscaled / math.sqrt(3)

        self.vertices_orig_centered: List[Tuple[float, float]] = \
            geometry_utils.calculate_regular_polygon_centered_vertices(
                radius=radius_circumscribed,
                num_vertices=3,
                start_angle_offset_rad=0 # Вершина сверху
            )
        
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
            "side_length": self.side_length_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad  # Ключ унифицирован
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