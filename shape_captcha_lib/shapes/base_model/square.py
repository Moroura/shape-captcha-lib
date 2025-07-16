# shape_captcha_lib/shapes/base_model/square.py
import random
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils # Для calculate_rotated_polygon_vertices, is_point_in_polygon, calculate_polygon_bounding_box
from ...utils import color_utils

class SquareShape(AbstractShape):
    """
    Представление фигуры "Квадрат" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "square"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int, # Для квадрата это будет min_side
        max_primary_size_upscaled: int, # Для квадрата это будет max_side
        min_secondary_size_upscaled: Optional[int] = None, # Не используется квадратом
        max_secondary_size_upscaled: Optional[int] = None, # Не используется квадратом
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует длину стороны для квадрата.
        """
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            side = max(1, min_primary_size_upscaled)
        else:
            side = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)
        return {"side": side}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        side: Optional[int] = None, # Ожидается из generate_size_params
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if side is None:
            raise ValueError("Side length ('side') must be provided for SquareShape.")
        if not isinstance(side, int) or side <= 0:
            raise ValueError(f"Side length must be a positive integer, got {side}.")
            
        self.side_upscaled: int = side
        
        # Рассчитываем вершины квадрата, центрированные относительно (0,0)
        half_side = self.side_upscaled / 2.0
        self.vertices_orig_centered: List[Tuple[float, float]] = [
            (-half_side, -half_side),
            ( half_side, -half_side),
            ( half_side,  half_side),
            (-half_side,  half_side)
        ]
        
        # Поворачиваем и смещаем вершины
        self.final_vertices_upscaled: List[Tuple[int, int]] = \
            geometry_utils.calculate_rotated_polygon_vertices(
                self.cx_upscaled,
                self.cy_upscaled,
                self.vertices_orig_centered,
                self.rotation_angle_rad
            )
        
        # Рассчитываем bounding box
        self.bbox_upscaled_coords: List[float] = \
            geometry_utils.calculate_polygon_bounding_box(self.final_vertices_upscaled)

    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,
            "cy_upscaled": self.cy_upscaled,
            "side": self.side_upscaled,
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
            self.final_vertices_upscaled, # Передаем список кортежей [(x1,y1), (x2,y2), ...]
            fill=fill_color_rgb_actual,
            outline=derived_outline_color_rgb,
            width=outline_width_upscaled
        )

    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        return geometry_utils.is_point_in_polygon(
            px=point_x_upscaled,
            py=point_y_upscaled,
            vertices=self.final_vertices_upscaled
        )