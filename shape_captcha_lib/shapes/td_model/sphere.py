# shape_captcha_lib/shapes/td_model/sphere.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List

from PIL import ImageDraw

# Относительные импорты для AbstractShape и утилит
from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils # Для is_point_in_circle
from ...utils import color_utils   # Наш обновленный модуль

class SphereShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Сфера" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "sphere"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int, # Для сферы это будет min_radius
        max_primary_size_upscaled: int, # Для сферы это будет max_radius
        min_secondary_size_upscaled: Optional[int] = None, # Не используется
        max_secondary_size_upscaled: Optional[int] = None, # Не используется
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            radius = max(5, min_primary_size_upscaled) # Минимальный радиус для видимости
        else:
            radius = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)
        return {"radius": radius}

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0, # Не используется сферой
        radius: Optional[int] = None,
        # Параметры для отрисовки сферы, можно сделать их частью model_specific_constraints
        # или передавать при вызове draw, или задать как атрибуты класса
        center_brightness_factor: float = 1.7, 
        edge_brightness_factor: float = 0.5,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad # Игнорируется, но есть в интерфейсе
        )
        if radius is None:
            raise ValueError("Radius must be provided for SphereShape.")
        if not (isinstance(radius, int) and radius > 0):
            raise ValueError(f"Radius must be a positive integer, got {radius}.")
            
        self.radius_upscaled: int = radius
        self.center_brightness_factor = center_brightness_factor
        self.edge_brightness_factor = edge_brightness_factor
        
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
            "rotation_angle_rad": self.rotation_angle_rad, # Хотя не используется, для консистентности
            "center_brightness_factor": self.center_brightness_factor,
            "edge_brightness_factor": self.edge_brightness_factor
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
        fill_color_rgb_actual: Tuple[int, int, int], # Это уже RGB цвет заливки
        outline_width_upscaled: int,
        # brightness_factor_for_outline не используется напрямую, т.к. есть свои факторы
        # background_color_rgb_actual не используется сферой
        brightness_factor_for_outline: Optional[float] = None, # Игнорируется, используем свои
        background_color_rgb_actual: Optional[Tuple[int, int, int]] = None
    ):
        # Логика из draw_pseudo_3d_sphere из drawing_3d.py
        # base_rgb_fill уже передан как fill_color_rgb_actual

        # Контурный цвет для внешней обводки
        derived_outline_color_rgb = color_utils.get_contrasting_line_color(fill_color_rgb_actual)
        
        num_steps = max(10, self.radius_upscaled // 2)
        if self.radius_upscaled <= 0:
            logger.warning(f"Sphere radius {self.radius_upscaled}. Skip drawing.")
            return

        for i in range(num_steps, 0, -1):
            current_radius = int(self.radius_upscaled * (i / float(num_steps)))
            if current_radius <= 0:
                continue
            
            # Фактор яркости для текущего "слоя" сферы
            ratio_to_center = (num_steps - i + 1.0) / num_steps # От 0 (край) до 1 (центр)
            current_brightness_factor = self.edge_brightness_factor + \
                                      (self.center_brightness_factor - self.edge_brightness_factor) * ratio_to_center
            
            current_fill_layer_color = color_utils.adjust_brightness(
                fill_color_rgb_actual, 
                current_brightness_factor
            )
            
            layer_bbox = [
                self.cx_upscaled - current_radius, self.cy_upscaled - current_radius,
                self.cx_upscaled + current_radius, self.cy_upscaled + current_radius
            ]
            draw_context.ellipse(layer_bbox, fill=current_fill_layer_color, outline=None)
        
        # Внешний контур
        outer_pil_bbox = [int(round(c)) for c in self.bbox_upscaled_coords]
        draw_context.ellipse(outer_pil_bbox, fill=None, outline=derived_outline_color_rgb, width=outline_width_upscaled)

    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # Для сферы проверка попадания аналогична кругу
        return geometry_utils.is_point_in_circle(
            px=point_x_upscaled,
            py=point_y_upscaled,
            cx=self.cx_upscaled,
            cy=self.cy_upscaled,
            r=self.radius_upscaled
        )