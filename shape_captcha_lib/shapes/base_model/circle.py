# shape_captcha_lib/shapes/base_model/circle.py
import random
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils


class CircleShape(AbstractShape):
    @staticmethod
    def get_shape_type() -> str:
        return "circle"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,  # Для круга это будет min_radius
        max_primary_size_upscaled: int,  # Для круга это будет max_radius
        min_secondary_size_upscaled: Optional[int] = None,  # Не используется кругом
        max_secondary_size_upscaled: Optional[int] = None,  # Не используется кругом
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует радиус для круга.
        min_primary_size_upscaled и max_primary_size_upscaled интерпретируются как мин/макс радиус.
        """
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            # Гарантируем, что max больше min
            radius = max(1, min_primary_size_upscaled)
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
            raise ValueError("Radius must be provided for CircleShape.")
        if not isinstance(radius, int) or radius <= 0:
            raise ValueError(f"Radius must be a positive integer, got {radius}.")

        self.radius_upscaled: int = radius

        self.bbox_upscaled_coords: List[float] = [
            float(self.cx_upscaled - self.radius_upscaled),
            float(self.cy_upscaled - self.radius_upscaled),
            float(self.cx_upscaled + self.radius_upscaled),
            float(self.cy_upscaled + self.radius_upscaled)
        ]

    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,
            "cy_upscaled": self.cy_upscaled,
            "radius": self.radius_upscaled,
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
        pil_bbox = [
            int(round(self.bbox_upscaled_coords[0])),
            int(round(self.bbox_upscaled_coords[1])),
            int(round(self.bbox_upscaled_coords[2])),
            int(round(self.bbox_upscaled_coords[3]))
        ]
        draw_context.ellipse(
            pil_bbox,
            fill=fill_color_rgb_actual,
            outline=derived_outline_color_rgb,
            width=outline_width_upscaled
        )

    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        return geometry_utils.is_point_in_circle(
            px=point_x_upscaled,
            py=point_y_upscaled,
            cx=self.cx_upscaled,
            cy=self.cy_upscaled,
            r=self.radius_upscaled
        )