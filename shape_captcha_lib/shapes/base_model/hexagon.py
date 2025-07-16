# shape_captcha_lib/shapes/base_model/hexagon.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

class HexagonShape(AbstractShape):
    """
    Представление фигуры "Правильный Шестиугольник" для CAPTCHA.
    """
    NUM_VERTICES = 6 # Отличие от Пентагона

    @staticmethod
    def get_shape_type() -> str:
        return "hexagon" # Отличие от Пентагона

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,
        max_primary_size_upscaled: int,
        min_secondary_size_upscaled: Optional[int] = None,
        max_secondary_size_upscaled: Optional[int] = None,
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            radius = max(int(HexagonShape.NUM_VERTICES * 1.5), min_primary_size_upscaled)
        else:
            radius = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)
        return {"radius": radius}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        radius: Optional[int] = None,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if radius is None:
            raise ValueError("Radius must be provided for HexagonShape.")
        if not (isinstance(radius, int) and radius > 0):
            raise ValueError(f"Radius must be a positive integer, got {radius}.")
            
        self.radius_upscaled: int = radius
        
        self.vertices_orig_centered: List[Tuple[float, float]] = \
            geometry_utils.calculate_regular_polygon_centered_vertices(
                radius=float(self.radius_upscaled),
                num_vertices=self.NUM_VERTICES, # Используем NUM_VERTICES класса
                start_angle_offset_rad=0
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
            "radius": self.radius_upscaled,
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