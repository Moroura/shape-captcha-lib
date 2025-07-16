# shape_captcha_lib/shapes/base_model/rhombus.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails # Убедитесь, что путь к abc.py правильный
from ...utils import geometry_utils # Убедитесь, что путь к utils/ правильный
from ...utils import color_utils

class RhombusShape(AbstractShape):
    """
    Представление фигуры "Ромб" для CAPTCHA.
    Определяется двумя диагоналями.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "rhombus"

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
            d1 = max(2, min_primary_size_upscaled)
        else:
            d1 = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        min_d2 = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(2, int(d1 * 0.5))
        max_d2 = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_d2 + 1, int(d1 * 1.2))
        
        if max_d2 <= min_d2:
            d2 = max(2, min_d2)
        else:
            d2 = random.randint(min_d2, max_d2)
            
        return {"d1": d1, "d2": d2}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        d1: Optional[int] = None, 
        d2: Optional[int] = None, 
        **kwargs: Any # Добавил **kwargs для гибкости, если передаются лишние параметры
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if d1 is None or d2 is None:
            raise ValueError("Diagonals d1 and d2 must be provided for RhombusShape.")
        if not (isinstance(d1, int) and d1 > 0 and isinstance(d2, int) and d2 > 0):
            raise ValueError(f"Diagonals d1 and d2 must be positive integers, got d1={d1}, d2={d2}.")
            
        self.d1_upscaled: int = d1
        self.d2_upscaled: int = d2
        
        half_d1 = self.d1_upscaled / 2.0
        half_d2 = self.d2_upscaled / 2.0
        
        self.vertices_orig_centered: List[Tuple[float, float]] = [
            (0, -half_d2), (half_d1, 0),
            (0, half_d2),  (-half_d1, 0)
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
            "d1": self.d1_upscaled,
            "d2": self.d2_upscaled,
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

    # --- УБЕДИТЕСЬ, ЧТО ЭТОТ МЕТОД РЕАЛИЗОВАН ИМЕННО ТАК ---
    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        print(f"DEBUG [RhombusShape@{id(self)}]: Checking point ({point_x_upscaled}, {point_y_upscaled}) for rhombus.")
        print(f"DEBUG [RhombusShape@{id(self)}]: Vertices: {self.final_vertices_upscaled}")
        result = geometry_utils.is_point_in_polygon(
            px=point_x_upscaled,
            py=point_y_upscaled,
            vertices=self.final_vertices_upscaled
        )
        print(f"DEBUG [RhombusShape@{id(self)}]: is_point_in_polygon returned: {result} for point ({point_x_upscaled}, {point_y_upscaled})")
        return result
    # --- КОНЕЦ ПРОВЕРКИ МЕТОДА is_point_inside ---