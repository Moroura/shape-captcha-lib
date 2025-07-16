# shape_captcha_lib/shapes/base_model/cross.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils


class CrossShape(AbstractShape):
    """
    Представление фигуры "Крест" (симметричный) для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "cross"

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
        """
        Генерирует общий размер и толщину для креста.
        """
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            size = max(10, min_primary_size_upscaled)
        else:
            size = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        min_thick = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(1, int(size * 0.2))
        max_thick = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_thick + 1, int(size * 0.4))

        if max_thick <= min_thick:
            thickness = max(1, min_thick)
        else:
            thickness = random.randint(min_thick, max_thick)

        if thickness * 2 >= size:
            thickness = max(1, int(size / 3))

        return {"size": size, "thickness": thickness}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        size: Optional[int] = None,
        thickness: Optional[int] = None,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if size is None or thickness is None:
            raise ValueError("Size and thickness must be provided for CrossShape.")
        if not (isinstance(size, int) and size > 0 and isinstance(thickness, int) and thickness > 0):
            raise ValueError(f"Size and thickness must be positive integers, got size={size}, thickness={thickness}.")
        if thickness * 2 >= size:
            raise ValueError(f"Thickness ({thickness}) is too large for size ({size}). Must be less than size/2.")

        self.size_upscaled: int = size
        self.thickness_upscaled: int = thickness

        hs = self.size_upscaled / 2.0
        ht = self.thickness_upscaled / 2.0

        self.vertices_orig_centered: List[Tuple[float, float]] = [
            (-ht, -hs), (ht, -hs),
            (ht, -ht), (hs, -ht),
            (hs, ht), (ht, ht),
            (ht, hs), (-ht, hs),
            (-ht, ht), (-hs, ht),
            (-hs, -ht), (-ht, -ht)
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
            "size": self.size_upscaled,
            "thickness": self.thickness_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad
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