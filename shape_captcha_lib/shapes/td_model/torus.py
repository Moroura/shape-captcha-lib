# shape_captcha_lib/shapes/td_model/torus.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import logging

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

logger = logging.getLogger(__name__)

class TorusShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Тор" для CAPTCHA.
    Теперь всегда с круглой 2D-проекцией.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "torus"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Для внешнего радиуса (outer_radius)
        max_primary_size_upscaled: int,   # Для внешнего радиуса (outer_radius)
        min_secondary_size_upscaled: Optional[int] = None, # Для радиуса трубки (tube_radius)
        max_secondary_size_upscaled: Optional[int] = None, # Для радиуса трубки (tube_radius)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            outer_radius = max(10, min_primary_size_upscaled)
        else:
            outer_radius = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        min_tube_r_abs = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(2, int(outer_radius * 0.25))
        max_tube_r_abs = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_tube_r_abs + 1, int(outer_radius * 0.45))

        if max_tube_r_abs <= min_tube_r_abs:
            tube_radius = max(1, min_tube_r_abs)
        else:
            tube_radius = random.randint(min_tube_r_abs, max_tube_r_abs)
        
        if tube_radius >= outer_radius / 1.5: 
            tube_radius = int(outer_radius / 2.0)
        tube_radius = max(1, tube_radius)
        if outer_radius - tube_radius < 2 : 
            # Убедимся, что внешний радиус немного больше радиуса трубки для видимого отверстия
            # и что outer_radius не становится слишком маленьким.
            new_outer_radius = tube_radius + max(2, int(tube_radius*0.2)) # Гарантируем зазор
            if new_outer_radius < min_primary_size_upscaled and min_primary_size_upscaled > tube_radius + 1:
                outer_radius = min_primary_size_upscaled # Стараемся не делать меньше минимума
            else:
                outer_radius = new_outer_radius

            if tube_radius >= outer_radius / 1.5: # Перепроверка после корректировки outer_radius
                 tube_radius = int(outer_radius / 2.0)
            tube_radius = max(1, tube_radius)


        constraints = model_specific_constraints or {}
        highlight_factor = constraints.get("highlight_factor", 1.5)
        shadow_factor = constraints.get("shadow_factor", 0.6)
        # perspective_factor больше не нужен

        return {
            "outer_radius": outer_radius, 
            "tube_radius": tube_radius,
            # "perspective_factor": perspective_factor, # УДАЛЕНО
            "highlight_factor": highlight_factor,
            "shadow_factor": shadow_factor
        }

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0, # Тор обычно не вращаем
        outer_radius: Optional[int] = None,
        tube_radius: Optional[int] = None,
        # perspective_factor: float = 0.5, # УДАЛЕНО ИЗ ПАРАМЕТРОВ
        highlight_factor: float = 1.5,
        shadow_factor: float = 0.6,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad 
        )
        if outer_radius is None or tube_radius is None:
            raise ValueError("Outer_radius and tube_radius must be provided for TorusShape.")
        if not (isinstance(outer_radius, int) and outer_radius > 0 and \
                isinstance(tube_radius, int) and tube_radius > 0):
            raise ValueError(f"Radii must be positive integers, got R={outer_radius}, r={tube_radius}.")
        if tube_radius >= outer_radius: # Отверстие должно существовать
             # Можно скорректировать или выбросить ошибку, как сейчас
             # Для большей надежности, эта логика также должна быть в generate_size_params
             logger.warning(f"Correcting tube_radius ({tube_radius}) to be less than outer_radius ({outer_radius}) for Torus.")
             self.tube_radius_upscaled = max(1, outer_radius -1)
        else:
            self.tube_radius_upscaled: int = tube_radius

        self.outer_radius_upscaled: int = outer_radius
        # self.perspective_factor больше не нужен
        self.highlight_factor = highlight_factor
        self.shadow_factor = shadow_factor
        
        self._calculate_internal_geometry()

    def _calculate_internal_geometry(self):
        """Рассчитывает геометрию для отрисовки и проверки попадания."""
        # Внешняя окружность (проекция всего тора)
        self.outer_ellipse_rx = self.outer_radius_upscaled
        self.outer_ellipse_ry = self.outer_radius_upscaled # <--- ИЗМЕНЕНИЕ: ry = rx

        # Внутренняя окружность (проекция отверстия)
        hole_radius = self.outer_radius_upscaled - self.tube_radius_upscaled 
        
        if hole_radius <= 0 : 
            self.inner_ellipse_rx = 0
            self.inner_ellipse_ry = 0
        else:
            self.inner_ellipse_rx = hole_radius
            self.inner_ellipse_ry = hole_radius # <--- ИЗМЕНЕНИЕ: ry = rx
        
        self.bbox_upscaled_coords: List[float] = [
            float(self.cx_upscaled - self.outer_ellipse_rx),
            float(self.cy_upscaled - self.outer_ellipse_ry),
            float(self.cx_upscaled + self.outer_ellipse_rx),
            float(self.cy_upscaled + self.outer_ellipse_ry)
        ]
        
    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,
            "cy_upscaled": self.cy_upscaled,
            "outer_radius": self.outer_radius_upscaled,
            "tube_radius": self.tube_radius_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad, # Хотя не используется, для консистентности
            "highlight_factor": self.highlight_factor,
            "shadow_factor": self.shadow_factor
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
        brightness_factor_for_outline: Optional[float] = None,
        background_color_rgb_actual: Optional[Tuple[int, int, int]] = (255,255,255) 
    ):
        # (Логика отрисовки остается такой же, как я предоставлял для Тора,
        # она использует self.outer_ellipse_rx/ry и self.inner_ellipse_rx/ry,
        # которые теперь будут определять окружности, а не эллипсы)
        line_color = color_utils.get_contrasting_line_color(fill_color_rgb_actual)
        
        bbox_outer_pil = [
            self.cx_upscaled - self.outer_ellipse_rx, self.cy_upscaled - self.outer_ellipse_ry,
            self.cx_upscaled + self.outer_ellipse_rx, self.cy_upscaled + self.outer_ellipse_ry
        ]
        
        num_torus_grad_steps = max(10, int(self.tube_radius_upscaled * 1.5))
        
        draw_context.ellipse(bbox_outer_pil, fill=color_utils.adjust_brightness(fill_color_rgb_actual, self.shadow_factor), outline=None)

        if num_torus_grad_steps > 0 and self.inner_ellipse_rx > 0 and self.inner_ellipse_ry > 0 : # Добавил inner_ellipse_rx/ry > 0
            for i_torus in range(num_torus_grad_steps, 0, -1):
                ratio_to_outer_edge = i_torus / float(num_torus_grad_steps)
                
                current_grad_rx = self.inner_ellipse_rx + int((self.outer_ellipse_rx - self.inner_ellipse_rx) * ratio_to_outer_edge)
                current_grad_ry = self.inner_ellipse_ry + int((self.outer_ellipse_ry - self.inner_ellipse_ry) * ratio_to_outer_edge)
                
                current_grad_brightness = self.shadow_factor + (self.highlight_factor - self.shadow_factor) * (1.0 - ratio_to_outer_edge)
                current_grad_color = color_utils.adjust_brightness(fill_color_rgb_actual, current_grad_brightness)

                if current_grad_rx > self.inner_ellipse_rx and current_grad_ry > self.inner_ellipse_ry : 
                     current_bbox_grad = [
                         self.cx_upscaled - current_grad_rx, self.cy_upscaled - current_grad_ry, 
                         self.cx_upscaled + current_grad_rx, self.cy_upscaled + current_grad_ry
                    ]
                     draw_context.ellipse(current_bbox_grad, fill=current_grad_color, outline=None)
        
        if self.inner_ellipse_rx > 0 and self.inner_ellipse_ry > 0:
            actual_hole_color = background_color_rgb_actual if background_color_rgb_actual else (255,255,255)
            bbox_inner_pil = [
                self.cx_upscaled - self.inner_ellipse_rx, self.cy_upscaled - self.inner_ellipse_ry,
                self.cx_upscaled + self.inner_ellipse_rx, self.cy_upscaled + self.inner_ellipse_ry
            ]
            draw_context.ellipse(bbox_inner_pil, fill=actual_hole_color, outline=line_color, width=outline_width_upscaled)
        
        draw_context.ellipse(bbox_outer_pil, fill=None, outline=line_color, width=outline_width_upscaled)


    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # Используем geometry_utils.is_point_in_circle, так как проекции теперь круглые
        in_outer_circle = geometry_utils.is_point_in_circle(
            point_x_upscaled, point_y_upscaled,
            self.cx_upscaled, self.cy_upscaled,
            self.outer_ellipse_rx # rx и ry равны для окружности
        )
        
        if not in_outer_circle:
            return False
            
        if self.inner_ellipse_rx > 0 : # Проверяем только если есть отверстие
            in_inner_circle = geometry_utils.is_point_in_circle(
                point_x_upscaled, point_y_upscaled,
                self.cx_upscaled,
                self.cy_upscaled,
                self.inner_ellipse_rx # rx и ry равны для окружности
            )
            return not in_inner_circle 
        else:
            return True # Нет отверстия, значит если внутри внешнего, то это попадание