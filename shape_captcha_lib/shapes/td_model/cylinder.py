# shape_captcha_lib/shapes/td_model/cylinder.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import logging # Добавим логирование

from PIL import ImageDraw, Image # <--- Убедитесь, что Image импортирован

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

logger = logging.getLogger(__name__)

class CylinderShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Цилиндр" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "cylinder"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Будет для высоты (height)
        max_primary_size_upscaled: int,   # Будет для высоты (height)
        min_secondary_size_upscaled: Optional[int] = None, # Для радиуса основания (radius)
        max_secondary_size_upscaled: Optional[int] = None, # Для радиуса основания (radius)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            height = max(10, min_primary_size_upscaled) # Минимальная высота
        else:
            height = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        min_r = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(5, int(height * 0.2))
        max_r = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_r + 1, int(height * 0.5))
        
        if max_r <= min_r:
            radius = max(3, min_r) # Минимальный радиус
        else:
            radius = random.randint(min_r, max_r)
        
        perspective_factor_ellipse = random.uniform(0.3, 0.5)
        
        # Используем get с значениями по умолчанию, если model_specific_constraints это None или не содержит ключей
        constraints = model_specific_constraints or {}
        top_brightness_factor = constraints.get("top_brightness_factor", 1.3)
        side_gradient_start_factor = constraints.get("side_gradient_start_factor", 0.9)
        side_gradient_end_factor = constraints.get("side_gradient_end_factor", 0.5)

        return {
            "radius": radius, 
            "height": height,
            "perspective_factor_ellipse": perspective_factor_ellipse,
            "top_brightness_factor": top_brightness_factor,
            "side_gradient_start_factor": side_gradient_start_factor,
            "side_gradient_end_factor": side_gradient_end_factor
        }

    def __init__(
        self,
        cx_upscaled: int, # Центр X верхнего эллипса
        cy_upscaled: int, # Центр Y верхнего эллипса
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0, # Цилиндр обычно не вращаем по этой оси
        radius: Optional[int] = None,
        height: Optional[int] = None,
        perspective_factor_ellipse: float = 0.4,
        top_brightness_factor: float = 1.3,
        side_gradient_start_factor: float = 0.9,
        side_gradient_end_factor: float = 0.5,
        **kwargs: Any # Для прочих параметров, если они будут
    ):
        super().__init__(
            cx_upscaled=cx_upscaled, # Сохраняется как self.cx_upscaled
            cy_upscaled=cy_upscaled, # Сохраняется как self.cy_upscaled
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad 
        )
        if radius is None or height is None:
            raise ValueError("Radius and height must be provided for CylinderShape.")
        if not (isinstance(radius, int) and radius > 0 and isinstance(height, int) and height > 0):
            raise ValueError(f"Radius and height must be positive integers, got r={radius}, h={height}.")

        self.radius_upscaled: int = radius
        self.height_upscaled: int = height
        self.perspective_factor_ellipse: float = perspective_factor_ellipse
        self.top_brightness_factor = top_brightness_factor
        self.side_gradient_start_factor = side_gradient_start_factor
        self.side_gradient_end_factor = side_gradient_end_factor
        
        self._calculate_internal_geometry()

    def _calculate_internal_geometry(self):
        """Рассчитывает геометрию для отрисовки и проверки попадания."""
        self.ellipse_rx_upscaled: int = self.radius_upscaled
        self.ellipse_ry_upscaled: int = max(1, int(self.radius_upscaled * self.perspective_factor_ellipse))

        # self.cx_upscaled и self.cy_upscaled из super().__init__ - это центр верхнего эллипса
        self.top_ellipse_cx: int = self.cx_upscaled
        self.top_ellipse_cy: int = self.cy_upscaled 
        
        self.bottom_ellipse_cx: int = self.cx_upscaled
        self.bottom_ellipse_cy: int = self.cy_upscaled + self.height_upscaled

        # Для is_point_inside
        self.clickable_ellipses_params: List[Dict[str, Any]] = [
            {"name": "top_ellipse", "params": {
                "cx": self.top_ellipse_cx, "cy": self.top_ellipse_cy, 
                "rx": self.ellipse_rx_upscaled, "ry": self.ellipse_ry_upscaled}
            },
            {"name": "bottom_ellipse", "params": { # Весь нижний эллипс считаем кликабельным для простоты
                "cx": self.bottom_ellipse_cx, "cy": self.bottom_ellipse_cy,
                "rx": self.ellipse_rx_upscaled, "ry": self.ellipse_ry_upscaled}
            }
        ]
        
        self.side_body_vertices: List[Tuple[int, int]] = [
            (self.top_ellipse_cx - self.ellipse_rx_upscaled, self.top_ellipse_cy),
            (self.top_ellipse_cx + self.ellipse_rx_upscaled, self.top_ellipse_cy),
            (self.bottom_ellipse_cx + self.ellipse_rx_upscaled, self.bottom_ellipse_cy),
            (self.bottom_ellipse_cx - self.ellipse_rx_upscaled, self.bottom_ellipse_cy)
        ]
        # clickable_polygons - это список словарей, где каждый словарь - полигон
        self.clickable_polygons_params: List[Dict[str, Any]] = [
            {"name": "side_body_projection", "vertices": self.side_body_vertices}
        ]

        self.bbox_upscaled_coords: List[float] = [
            float(self.top_ellipse_cx - self.ellipse_rx_upscaled),
            float(self.top_ellipse_cy - self.ellipse_ry_upscaled),
            float(self.top_ellipse_cx + self.ellipse_rx_upscaled),
            float(self.bottom_ellipse_cy + self.ellipse_ry_upscaled)
        ]
        
    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled, # Используем self.cx_upscaled из AbstractShape
            "cy_upscaled": self.cy_upscaled, # Используем self.cy_upscaled из AbstractShape
            "radius": self.radius_upscaled,
            "height": self.height_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad, # Добавляем для полноты, хотя цилиндр обычно не вращается
            "perspective_factor_ellipse": self.perspective_factor_ellipse,
            "top_brightness_factor": self.top_brightness_factor,
            "side_gradient_start_factor": self.side_gradient_start_factor,
            "side_gradient_end_factor": self.side_gradient_end_factor
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
        background_color_rgb_actual: Optional[Tuple[int, int, int]] = None
    ):
        line_color = color_utils.get_contrasting_line_color(fill_color_rgb_actual)
        color_top_face = color_utils.adjust_brightness(fill_color_rgb_actual, self.top_brightness_factor)

        top_ellipse_bbox = [
            self.top_ellipse_cx - self.ellipse_rx_upscaled, self.top_ellipse_cy - self.ellipse_ry_upscaled,
            self.top_ellipse_cx + self.ellipse_rx_upscaled, self.top_ellipse_cy + self.ellipse_ry_upscaled
        ]
        bottom_ellipse_bbox = [
            self.bottom_ellipse_cx - self.ellipse_rx_upscaled, self.bottom_ellipse_cy - self.ellipse_ry_upscaled,
            self.bottom_ellipse_cx + self.ellipse_rx_upscaled, self.bottom_ellipse_cy + self.ellipse_ry_upscaled
        ]

        # Отрисовка тела цилиндра (упрощенная версия с градиентными полосами из drawing_3d.py)
        # Эта часть может быть сложной и ресурсоемкой, можно начать с более простой заливки
        num_gradient_bands = max(10, self.radius_upscaled * 2 // 3)
        if num_gradient_bands > 0 : # Защита от деления на ноль, если radius очень мал
            for i in range(num_gradient_bands):
                # Коэффициент для косинуса, чтобы получить плавный переход от одного края к другому и обратно
                ratio_for_cos = i / float(num_gradient_bands -1 if num_gradient_bands > 1 else 1)
                # brightness_pos_factor от 0 до 1 и обратно (имитация освещения сбоку)
                brightness_pos_factor = (math.cos(ratio_for_cos * math.pi * 2 - math.pi) + 1) / 2.0 
                
                current_side_brightness = self.side_gradient_end_factor + \
                                          (self.side_gradient_start_factor - self.side_gradient_end_factor) * brightness_pos_factor
                band_color = color_utils.adjust_brightness(fill_color_rgb_actual, current_side_brightness)
                
                # x координата текущей вертикальной полосы
                current_x = (self.top_ellipse_cx - self.ellipse_rx_upscaled) + ratio_for_cos * (self.ellipse_rx_upscaled * 2)
                
                # Динамический расчет y для нижней точки полосы на эллипсе
                # (x-h)^2/a^2 + (y-k)^2/b^2 = 1 => y = k +/- b * sqrt(1 - (x-h)^2/a^2)
                # Здесь x - это current_x, h - это self.bottom_ellipse_cx, k - self.bottom_ellipse_cy
                # a - self.ellipse_rx_upscaled, b - self.ellipse_ry_upscaled
                # Нам нужна нижняя дуга, поэтому k + b * ...
                x_rel_sq = ((current_x - self.bottom_ellipse_cx) / self.ellipse_rx_upscaled)**2 if self.ellipse_rx_upscaled > 0 else 1.0
                if x_rel_sq > 1.0: x_rel_sq = 1.0 # Ограничение из-за дискретности
                
                dynamic_bottom_y = self.bottom_ellipse_cy + self.ellipse_ry_upscaled * math.sqrt(max(0, 1 - x_rel_sq))
                
                # Рисуем вертикальную полосу. Ширина полосы должна покрывать промежутки.
                band_pixel_width = math.ceil((self.ellipse_rx_upscaled * 2) / num_gradient_bands) + 2 # +2 для перекрытия
                
                # Верхняя точка всегда на уровне self.top_ellipse_cy для этой x
                # Для более точного прилегания к верхнему эллипсу, y_top также должен быть динамическим,
                # но для простоты пока оставим так.
                # y_top_on_ellipse = self.top_ellipse_cy - self.ellipse_ry_upscaled * math.sqrt(max(0,1-x_rel_sq)) (для верхней дуги)
                # или просто self.top_ellipse_cy, если полосы начинаются от прямой линии между краями эллипса

                draw_context.line([
                    (current_x, self.top_ellipse_cy), 
                    (current_x, int(round(dynamic_bottom_y)))
                ], fill=band_color, width=int(round(band_pixel_width)))

        # Обводка эллипсов и боковых сторон
        draw_context.ellipse(bottom_ellipse_bbox, outline=line_color, width=outline_width_upscaled, fill=None)
        draw_context.line([
            (self.top_ellipse_cx - self.ellipse_rx_upscaled, self.top_ellipse_cy),
            (self.bottom_ellipse_cx - self.ellipse_rx_upscaled, self.bottom_ellipse_cy)
        ], fill=line_color, width=outline_width_upscaled)
        draw_context.line([
            (self.top_ellipse_cx + self.ellipse_rx_upscaled, self.top_ellipse_cy),
            (self.bottom_ellipse_cx + self.ellipse_rx_upscaled, self.bottom_ellipse_cy)
        ], fill=line_color, width=outline_width_upscaled)
        draw_context.ellipse(top_ellipse_bbox, fill=color_top_face, outline=line_color, width=outline_width_upscaled)


    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # Проверяем попадание в верхний эллипс
        top_ellipse_data = self.clickable_ellipses_params[0]
        if geometry_utils.is_point_in_ellipse(
            point_x_upscaled, point_y_upscaled,
            top_ellipse_data["params"]["cx"], top_ellipse_data["params"]["cy"],
            top_ellipse_data["params"]["rx"], top_ellipse_data["params"]["ry"]
        ):
            # print(f"DEBUG [CylinderShape]: HIT on top_ellipse")
            return True
        
        # Проверяем попадание в тело (прямоугольная проекция)
        # Важно: эта проверка должна быть до нижнего эллипса, если тело его перекрывает
        side_body_data = self.clickable_polygons_params[0]
        if geometry_utils.is_point_in_polygon(
            point_x_upscaled, point_y_upscaled,
            side_body_data["vertices"]
        ):
            # Дополнительно убедимся, что клик не на "дырке" внутри тела, если бы она была.
            # Для простого цилиндра эта проверка достаточна для тела.
            # print(f"DEBUG [CylinderShape]: HIT on side_body_projection")
            return True

        # Проверяем попадание в нижний эллипс (если не попали в тело или верхний эллипс)
        # Это может быть избыточно, если is_point_in_polygon для тела уже покрывает эту область,
        # но полезно, если тело рисуется так, что нижний эллипс "выступает".
        bottom_ellipse_data = self.clickable_ellipses_params[1]
        if geometry_utils.is_point_in_ellipse(
            point_x_upscaled, point_y_upscaled,
            bottom_ellipse_data["params"]["cx"], bottom_ellipse_data["params"]["cy"],
            bottom_ellipse_data["params"]["rx"], bottom_ellipse_data["params"]["ry"]
        ):
            # print(f"DEBUG [CylinderShape]: HIT on bottom_ellipse")
            return True
            
        # print(f"DEBUG [CylinderShape]: MISS on all parts for point ({point_x_upscaled}, {point_y_upscaled})")
        return False