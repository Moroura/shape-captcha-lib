# shape_captcha_lib/shapes/base_model/trapezoid.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

class TrapezoidShape(AbstractShape):
    """
    Представление фигуры "Равнобедренная Трапеция" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "trapezoid"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Будет использовано для высоты (height)
        max_primary_size_upscaled: int,   # Будет использовано для высоты (height)
        min_secondary_size_upscaled: Optional[int] = None, # Для нижнего основания (bottom_width)
        max_secondary_size_upscaled: Optional[int] = None, # Для нижнего основания (bottom_width)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует высоту, нижнее и верхнее основания для трапеции.
        """
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            height = max(3, min_primary_size_upscaled)
        else:
            height = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        # Нижнее основание (bottom_width) как secondary_size
        min_bw = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(int(height * 0.6), 5)
        max_bw = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_bw + 1, int(height * 1.2))
        
        if max_bw <= min_bw:
            bottom_width = max(3, min_bw)
        else:
            bottom_width = random.randint(min_bw, max_bw)

        # Верхнее основание (top_width) меньше нижнего, но больше 0
        min_tw = max(1, int(bottom_width * 0.2))
        max_tw = max(min_tw + 1, int(bottom_width * 0.9))
        
        if max_tw <= min_tw:
            top_width = max(1, min_tw)
        else:
            top_width = random.randint(min_tw, max_tw)
        
        # Убедимся, что top_width < bottom_width
        if top_width >= bottom_width:
            top_width = max(1, int(bottom_width * 0.8))
            if top_width >= bottom_width and bottom_width > 1 : # Если все еще не так
                 top_width = bottom_width -1


        return {"height": height, "bottom_width": bottom_width, "top_width": top_width}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        height: Optional[int] = None,
        bottom_width: Optional[int] = None,
        top_width: Optional[int] = None,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if height is None or bottom_width is None or top_width is None:
            raise ValueError("Height, bottom_width, and top_width must be provided for TrapezoidShape.")
        if not (isinstance(height, int) and height > 0 and \
                isinstance(bottom_width, int) and bottom_width > 0 and \
                isinstance(top_width, int) and top_width > 0):
            raise ValueError(f"Dimensions must be positive integers, got h={height}, bw={bottom_width}, tw={top_width}.")
        if top_width >= bottom_width:
             raise ValueError(f"Top width ({top_width}) must be less than bottom width ({bottom_width}).")
            
        self.height_upscaled: int = height
        self.bottom_width_upscaled: int = bottom_width
        self.top_width_upscaled: int = top_width
        
        half_h = self.height_upscaled / 2.0
        half_bw = self.bottom_width_upscaled / 2.0
        half_tw = self.top_width_upscaled / 2.0
        
        self.vertices_orig_centered: List[Tuple[float, float]] = [
            (-half_tw, -half_h), (half_tw, -half_h),  # Верхнее основание
            (half_bw, half_h),   (-half_bw, half_h)   # Нижнее основание
        ]
        
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
            "height": self.height_upscaled,
            "bottom_width": self.bottom_width_upscaled,
            "top_width": self.top_width_upscaled,
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