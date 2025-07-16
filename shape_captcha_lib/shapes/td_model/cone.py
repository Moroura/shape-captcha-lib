# shape_captcha_lib/shapes/td_model/cone.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import logging

from PIL import ImageDraw, Image # Image может понадобиться для сложных градиентов, пока не используется

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

logger = logging.getLogger(__name__)

class ConeShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Конус" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "cone"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Для высоты (height)
        max_primary_size_upscaled: int,   # Для высоты (height)
        min_secondary_size_upscaled: Optional[int] = None, # Для радиуса основания (base_radius)
        max_secondary_size_upscaled: Optional[int] = None, # Для радиуса основания (base_radius)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            height = max(10, min_primary_size_upscaled)
        else:
            height = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        min_r = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(5, int(height * 0.3))
        max_r = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_r + 1, int(height * 0.7))
        
        if max_r <= min_r:
            base_radius = max(3, min_r)
        else:
            base_radius = random.randint(min_r, max_r)
        
        perspective_factor_base = random.uniform(0.3, 0.5)
        
        constraints = model_specific_constraints or {}
        side_gradient_start_factor = constraints.get("side_gradient_start_factor", 1.1)
        side_gradient_end_factor = constraints.get("side_gradient_end_factor", 0.7)

        return {
            "base_radius": base_radius, 
            "height": height,
            "perspective_factor_base": perspective_factor_base,
            "side_gradient_start_factor": side_gradient_start_factor,
            "side_gradient_end_factor": side_gradient_end_factor
        }

    def __init__(
        self,
        cx_upscaled: int, # Центр X основания конуса
        cy_upscaled: int, # Центр Y основания конуса
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0, # Обычно конусы не вращают
        base_radius: Optional[int] = None,
        height: Optional[int] = None,
        perspective_factor_base: float = 0.4,
        side_gradient_start_factor: float = 1.1,
        side_gradient_end_factor: float = 0.7,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled, # Это cx_base
            cy_upscaled=cy_upscaled, # Это cy_base
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if base_radius is None or height is None:
            raise ValueError("Base radius and height must be provided for ConeShape.")
        if not (isinstance(base_radius, int) and base_radius > 0 and isinstance(height, int) and height > 0):
            raise ValueError(f"Base radius and height must be positive integers, got r={base_radius}, h={height}.")

        self.base_radius_upscaled: int = base_radius
        self.height_upscaled: int = height
        self.perspective_factor_base: float = perspective_factor_base
        self.side_gradient_start_factor = side_gradient_start_factor
        self.side_gradient_end_factor = side_gradient_end_factor
        
        self._calculate_internal_geometry()

    def _calculate_internal_geometry(self):
        """Рассчитывает геометрию для отрисовки и проверки попадания."""
        self.base_ellipse_cx: int = self.cx_upscaled # Центр основания
        self.base_ellipse_cy: int = self.cy_upscaled # Центр основания
        
        self.apex_x: int = self.base_ellipse_cx
        self.apex_y: int = self.base_ellipse_cy - self.height_upscaled # Вершина конуса сверху

        self.ellipse_rx_upscaled: int = self.base_radius_upscaled
        self.ellipse_ry_upscaled: int = max(1, int(self.base_radius_upscaled * self.perspective_factor_base))

        # Для is_point_inside
        self.clickable_base_ellipse_params: Dict[str, Any] = {
            "cx": self.base_ellipse_cx, "cy": self.base_ellipse_cy,
            "rx": self.ellipse_rx_upscaled, "ry": self.ellipse_ry_upscaled
        }
        # Треугольная проекция тела конуса
        self.cone_body_triangle_vertices: List[Tuple[int, int]] = [
            (self.apex_x, self.apex_y),
            (self.base_ellipse_cx - self.ellipse_rx_upscaled, self.base_ellipse_cy), # Левая точка основания
            (self.base_ellipse_cx + self.ellipse_rx_upscaled, self.base_ellipse_cy)  # Правая точка основания
        ]

        # Общий bbox
        self.bbox_upscaled_coords: List[float] = [
            float(self.base_ellipse_cx - self.ellipse_rx_upscaled),
            float(self.apex_y), # Верхняя точка - апекс
            float(self.base_ellipse_cx + self.ellipse_rx_upscaled),
            float(self.base_ellipse_cy + self.ellipse_ry_upscaled) # Нижняя точка эллипса основания
        ]
        
    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,  # Используем стандартное имя из AbstractShape
            "cy_upscaled": self.cy_upscaled,  # Используем стандартное имя из AbstractShape
            "base_radius": self.base_radius_upscaled,
            "height": self.height_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad,  # Добавляем для полноты
            "perspective_factor_base": self.perspective_factor_base,
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
        line_color = color_utils.get_contrasting_line_color(
            fill_color_rgb_actual, dark_factor=0.3, light_factor=1.8
        )

        base_ellipse_bbox = [
            self.base_ellipse_cx - self.ellipse_rx_upscaled, 
            self.base_ellipse_cy - self.ellipse_ry_upscaled,
            self.base_ellipse_cx + self.ellipse_rx_upscaled, 
            self.base_ellipse_cy + self.ellipse_ry_upscaled
        ]

        # Рисуем "тело" конуса градиентными сегментами (адаптировано из drawing_3d.py)
        num_gradient_segments = max(16, self.base_radius_upscaled * 2)
        if num_gradient_segments > 0:
            for i in range(num_gradient_segments):
                angle1 = (i / float(num_gradient_segments)) * 2 * math.pi
                angle2 = ((i + 1) / float(num_gradient_segments)) * 2 * math.pi
                
                # Проекция точек окружности основания на эллипс
                x1_on_circle = self.base_radius_upscaled * math.cos(angle1)
                y1_on_circle_projected = self.base_radius_upscaled * math.sin(angle1) * self.perspective_factor_base
                
                x2_on_circle = self.base_radius_upscaled * math.cos(angle2)
                y2_on_circle_projected = self.base_radius_upscaled * math.sin(angle2) * self.perspective_factor_base

                v1_base_projected = (
                    int(round(self.base_ellipse_cx + x1_on_circle)),
                    int(round(self.base_ellipse_cy + y1_on_circle_projected))
                )
                v2_base_projected = (
                    int(round(self.base_ellipse_cx + x2_on_circle)),
                    int(round(self.base_ellipse_cy + y2_on_circle_projected))
                )
                
                segment_vertices = [(self.apex_x, self.apex_y), v1_base_projected, v2_base_projected]
                
                avg_angle_segment = (angle1 + angle2) / 2.0
                # Яркость зависит от угла (имитация бокового освещения)
                brightness_pos_factor = (math.cos(avg_angle_segment) + 1) / 2.0 
                current_side_brightness = self.side_gradient_end_factor + \
                                          (self.side_gradient_start_factor - self.side_gradient_end_factor) * brightness_pos_factor
                segment_color = color_utils.adjust_brightness(fill_color_rgb_actual, current_side_brightness)
                
                draw_context.polygon(segment_vertices, fill=segment_color, outline=None)

        # Рисуем дуги основания и боковые линии поверх градиента
        # Видимая (нижняя) часть дуги основания
        draw_context.arc(base_ellipse_bbox, 0, 180, fill=line_color, width=outline_width_upscaled)
        # Невидимая (верхняя) часть дуги основания (можно другим цветом или тоньше, если нужно)
        # draw_context.arc(base_ellipse_bbox, 180, 360, fill=color_utils.adjust_brightness(line_color, 1.5), width=max(1, outline_width_upscaled // 2))
        # Для простоты пока не рисуем заднюю часть дуги отдельно или используем тот же цвет
        draw_context.arc(base_ellipse_bbox, 180, 360, fill=line_color, width=outline_width_upscaled)


        # Боковые образующие линии
        draw_context.line([
            (self.base_ellipse_cx - self.ellipse_rx_upscaled, self.base_ellipse_cy), 
            (self.apex_x, self.apex_y)
        ], fill=line_color, width=outline_width_upscaled)
        draw_context.line([
            (self.base_ellipse_cx + self.ellipse_rx_upscaled, self.base_ellipse_cy),
            (self.apex_x, self.apex_y)
        ], fill=line_color, width=outline_width_upscaled)


    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # 1. Проверка попадания в эллиптическое основание
        if geometry_utils.is_point_in_ellipse(
            point_x_upscaled, point_y_upscaled,
            self.clickable_base_ellipse_params["cx"], self.clickable_base_ellipse_params["cy"],
            self.clickable_base_ellipse_params["rx"], self.clickable_base_ellipse_params["ry"]
        ):
            # Убедимся, что клик ниже апекса (вершины конуса) по Y
            if point_y_upscaled >= self.apex_y:
                # print(f"DEBUG [ConeShape]: HIT on base_ellipse")
                return True
        
        # 2. Проверка попадания в треугольную проекцию тела конуса
        if geometry_utils.is_point_in_polygon(
            point_x_upscaled, point_y_upscaled,
            self.cone_body_triangle_vertices
        ):
            # print(f"DEBUG [ConeShape]: HIT on cone_body_triangle_projection")
            return True
            
        # print(f"DEBUG [ConeShape]: MISS on all parts for point ({point_x_upscaled}, {point_y_upscaled})")
        return False