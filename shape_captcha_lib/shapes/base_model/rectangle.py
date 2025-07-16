# shape_captcha_lib/shapes/base_model/rectangle.py
import random
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

class RectangleShape(AbstractShape):
    """
    Представление фигуры "Прямоугольник" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "rectangle"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Будет использовано для ширины (width)
        max_primary_size_upscaled: int,   # Будет использовано для ширины (width)
        min_secondary_size_upscaled: Optional[int] = None, # Будет использовано для высоты (height)
        max_secondary_size_upscaled: Optional[int] = None, # Будет использовано для высоты (height)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует ширину и высоту для прямоугольника.
        """
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            width = max(1, min_primary_size_upscaled)
        else:
            width = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        # Если вторичные размеры не предоставлены, делаем высоту пропорциональной ширине
        # (например, от 40% до 70% ширины, как было в старом image_generator)
        min_h = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(1, int(width * 0.4))
        max_h = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_h + 1, int(width * 0.7))
        
        if max_h <= min_h:
            height = max(1, min_h)
        else:
            height = random.randint(min_h, max_h)
            
        # Опционально: убедимся, что это не квадрат (если это важно для "прямоугольника")
        # Например, если abs(width - height) < порог, изменить один из размеров.
        # Пока оставляем возможность генерации квадрата через этот класс.

        return {"width": width, "height": height}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if width is None or height is None:
            raise ValueError("Width and height must be provided for RectangleShape.")
        if not (isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0):
            raise ValueError(f"Width and height must be positive integers, got w={width}, h={height}.")
            
        self.width_upscaled: int = width
        self.height_upscaled: int = height
        
        half_w = self.width_upscaled / 2.0
        half_h = self.height_upscaled / 2.0
        self.vertices_orig_centered: List[Tuple[float, float]] = [
            (-half_w, -half_h), (half_w, -half_h),
            (half_w, half_h),  (-half_w, half_h)
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
            "width": self.width_upscaled,
            "height": self.height_upscaled,
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