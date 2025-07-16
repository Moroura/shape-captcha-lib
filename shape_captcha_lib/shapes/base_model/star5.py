# shape_captcha_lib/shapes/base_model/star5.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

class Star5Shape(AbstractShape):
    """
    Представление фигуры "Пятиконечная Звезда" для CAPTCHA.
    """
    NUM_POINTS = 5

    @staticmethod
    def get_shape_type() -> str:
        return "star5"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Будет использовано для внешнего радиуса (outer_radius)
        max_primary_size_upscaled: int,   # Будет использовано для внешнего радиуса (outer_radius)
        min_secondary_size_upscaled: Optional[int] = None, # Для мин. внутреннего радиуса (относительно внешнего)
        max_secondary_size_upscaled: Optional[int] = None, # Для макс. внутреннего радиуса (относительно внешнего)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует внешний и внутренний радиусы для звезды.
        """
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            outer_radius = max(int(Star5Shape.NUM_POINTS * 3), min_primary_size_upscaled) # Достаточный размер для звезды
        else:
            outer_radius = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        # Внутренний радиус как доля от внешнего (например, от 0.35 до 0.6 внешнего)
        # min_secondary/max_secondary могут определять эти факторы или абсолютные значения, если переданы
        min_inner_ratio = 0.35
        max_inner_ratio = 0.60

        # Если min_secondary_size_upscaled/max_secondary_size_upscaled это факторы (0-1)
        if min_secondary_size_upscaled is not None and isinstance(min_secondary_size_upscaled, float):
            min_inner_ratio = min_secondary_size_upscaled
        if max_secondary_size_upscaled is not None and isinstance(max_secondary_size_upscaled, float):
            max_inner_ratio = max_secondary_size_upscaled

        inner_radius = int(outer_radius * random.uniform(min_inner_ratio, max_inner_ratio))
        inner_radius = max(1, inner_radius) # Внутренний радиус должен быть > 0

        # Убедимся, что внутренний радиус значительно меньше внешнего
        if inner_radius >= outer_radius * 0.9:
            inner_radius = int(outer_radius * 0.5)
        inner_radius = max(1, inner_radius)


        return {"outer_radius": outer_radius, "inner_radius": inner_radius}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        outer_radius: Optional[int] = None,
        inner_radius: Optional[int] = None,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if outer_radius is None or inner_radius is None:
            raise ValueError("Outer and inner radius must be provided for Star5Shape.")
        if not (isinstance(outer_radius, int) and outer_radius > 0 and \
                isinstance(inner_radius, int) and inner_radius > 0):
            raise ValueError(f"Radii must be positive integers, got outer={outer_radius}, inner={inner_radius}.")
        if inner_radius >= outer_radius:
            # Эта проверка также может быть в generate_size_params
            raise ValueError(f"Inner radius ({inner_radius}) must be smaller than outer radius ({outer_radius}).")

        self.outer_radius_upscaled: int = outer_radius
        self.inner_radius_upscaled: int = inner_radius

        self.vertices_orig_centered: List[Tuple[float, float]] = \
            geometry_utils.calculate_star_centered_vertices(
                outer_radius=float(self.outer_radius_upscaled),
                inner_radius=float(self.inner_radius_upscaled),
                num_points=self.NUM_POINTS,
                start_angle_offset_rad=0 # Луч вверх
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
            "outer_radius": self.outer_radius_upscaled,
            "inner_radius": self.inner_radius_upscaled,
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