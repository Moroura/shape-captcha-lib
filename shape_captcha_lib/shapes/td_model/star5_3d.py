# shape_captcha_lib/shapes/td_model/star5_3d.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import logging
import colorsys # Для adjust_brightness, если используется напрямую

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils # calculate_star_centered_vertices, calculate_rotated_polygon_vertices, etc.
from ...utils import color_utils

logger = logging.getLogger(__name__)

class Star5_3DShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Пятиконечная Звезда" для CAPTCHA.
    """
    NUM_POINTS = 5

    @staticmethod
    def get_shape_type() -> str:
        return "star5_3d"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Для внешнего радиуса (outer_radius)
        max_primary_size_upscaled: int,   # Для внешнего радиуса (outer_radius)
        min_secondary_size_upscaled: Optional[int] = None, # Для внутреннего радиуса (inner_radius)
        max_secondary_size_upscaled: Optional[int] = None, # Для внутреннего радиуса (inner_radius)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            outer_radius = max(int(Star5_3DShape.NUM_POINTS * 4), min_primary_size_upscaled) # Звезда требует большего радиуса
        else:
            outer_radius = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        # --- ИЗМЕНЕНИЯ ДЛЯ БОЛЕЕ ОСТРЫХ ЛУЧЕЙ ---
        # Устанавливаем более строгие рамки для соотношения внутреннего и внешнего радиусов.
        # Внутренний радиус должен быть в диапазоне, например, от 30% до 50% от внешнего.
        # Это сделает лучи длиннее и заметнее.
        min_inner_radius_ratio = 0.30  # Минимальное отношение внутреннего радиуса к внешнему
        max_inner_radius_ratio = 0.50  # Максимальное отношение

        # Рассчитываем абсолютные min/max для внутреннего радиуса на основе этих соотношений
        # и переданных min/max_secondary_size_upscaled, если они есть
        
        abs_min_inner_from_ratio = max(1, int(outer_radius * min_inner_radius_ratio))
        abs_max_inner_from_ratio = max(abs_min_inner_from_ratio + 1, int(outer_radius * max_inner_radius_ratio))

        final_min_inner_r = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else abs_min_inner_from_ratio
        final_min_inner_r = max(final_min_inner_r, abs_min_inner_from_ratio) # Убедимся, что не меньше чем по ratio

        final_max_inner_r = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else abs_max_inner_from_ratio
        final_max_inner_r = min(final_max_inner_r, abs_max_inner_from_ratio) # Убедимся, что не больше чем по ratio
        final_max_inner_r = max(final_min_inner_r + 1, final_max_inner_r) # Гарантируем, что max > min

        if final_max_inner_r <= final_min_inner_r:
            inner_radius = max(1, final_min_inner_r)
        else:
            inner_radius = random.randint(final_min_inner_r, final_max_inner_r)
        
        # Дополнительная гарантия: если inner_radius все еще слишком большой
        if inner_radius >= outer_radius * (max_inner_radius_ratio + 0.05): # +0.05 для небольшого запаса
            inner_radius = int(outer_radius * max_inner_radius_ratio)
        
        inner_radius = max(1, inner_radius) # Должен быть хотя бы 1
        if inner_radius >= outer_radius: # Самый крайний случай
            logger.warning(f"Star5_3D: Correcting inner_radius ({inner_radius}) to be less than outer_radius ({outer_radius}).")
            inner_radius = max(1, int(outer_radius * min_inner_radius_ratio)) # Берем минимально допустимое отношение
            if inner_radius >= outer_radius: # Если и это не помогло (outer_radius слишком мал)
                inner_radius = max(1, outer_radius -1) if outer_radius > 1 else 1


        # --- КОНЕЦ ИЗМЕНЕНИЙ ДЛЯ ЛУЧЕЙ ---


        depth_factor = random.uniform(0.15, 0.3) # Визуальная глубина экструзии
        
        constraints = model_specific_constraints or {}
        top_face_brightness_factor = constraints.get("top_face_brightness_factor", 1.25)
        side_face_brightness_factor = constraints.get("side_face_brightness_factor", 0.7)

        return {
            "outer_radius": outer_radius, 
            "inner_radius": inner_radius,
            "depth_factor": depth_factor,
            "top_face_brightness_factor": top_face_brightness_factor,
            "side_face_brightness_factor": side_face_brightness_factor
        }

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        outer_radius: Optional[int] = None,
        inner_radius: Optional[int] = None,
        depth_factor: float = 0.2,
        top_face_brightness_factor: float = 1.25,
        side_face_brightness_factor: float = 0.7,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if outer_radius is None or inner_radius is None:
            raise ValueError("Outer and inner radius must be provided for Star5_3DShape.")
        if not (isinstance(outer_radius, int) and outer_radius > 0 and \
                isinstance(inner_radius, int) and inner_radius > 0):
            raise ValueError(f"Radii must be positive integers, got R={outer_radius}, r={inner_radius}.")
        if inner_radius >= outer_radius:
             raise ValueError(f"Inner radius ({inner_radius}) must be smaller than outer radius ({outer_radius}).")

        self.outer_radius_upscaled: int = outer_radius
        self.inner_radius_upscaled: int = inner_radius
        self.depth_factor: float = depth_factor
        self.top_face_brightness_factor = top_face_brightness_factor
        self.side_face_brightness_factor = side_face_brightness_factor
        
        self._calculate_internal_geometry()

    def _calculate_internal_geometry(self):
        # 1. Вершины передней грани (2D звезда)
        star_orig_centered: List[Tuple[float, float]] = \
            geometry_utils.calculate_star_centered_vertices(
                outer_radius=float(self.outer_radius_upscaled),
                inner_radius=float(self.inner_radius_upscaled),
                num_points=self.NUM_POINTS,
                start_angle_offset_rad=-math.pi / 2 # Один луч направлен вверх
            )
        
        self.front_vertices: List[Tuple[int, int]] = \
            geometry_utils.calculate_rotated_polygon_vertices(
                self.cx_upscaled, self.cy_upscaled,
                star_orig_centered, self.rotation_angle_rad
            )

        # 2. Смещение для задней грани
        # Глубина экструзии, может зависеть от "толщины" звезды, например, inner_radius
        actual_depth_offset = int(self.inner_radius_upscaled * self.depth_factor * 2) # Увеличим немного для заметности
        actual_depth_offset = max(1, actual_depth_offset)

        depth_display_angle = -math.pi / 4 + self.rotation_angle_rad 
        dx_depth = int(actual_depth_offset * math.cos(depth_display_angle))
        dy_depth = int(actual_depth_offset * math.sin(depth_display_angle))
        
        self.back_vertices: List[Tuple[int, int]] = [
            (v[0] + dx_depth, v[1] + dy_depth) for v in self.front_vertices
        ]
        
        # 3. Боковые соединяющие полигоны
        self.side_connecting_polygons: List[List[Tuple[int, int]]] = []
        num_front_verts = len(self.front_vertices)
        for i in range(num_front_verts):
            p1 = self.front_vertices[i]
            p2 = self.front_vertices[(i + 1) % num_front_verts]
            p3 = self.back_vertices[(i + 1) % num_front_verts]
            p4 = self.back_vertices[i]
            self.side_connecting_polygons.append([p1, p2, p3, p4])
            
        all_vertices_for_bbox = self.front_vertices + self.back_vertices
        self.bbox_upscaled_coords: List[float] = \
            geometry_utils.calculate_polygon_bounding_box(all_vertices_for_bbox)

        # Кликабельной считаем только переднюю грань
        self.clickable_polygons_params: List[Dict[str, Any]] = [
            {"name": "front_face", "vertices": self.front_vertices}
        ]

    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,
            "cy_upscaled": self.cy_upscaled,
            "outer_radius": self.outer_radius_upscaled,
            "inner_radius": self.inner_radius_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad,
            "depth_factor": self.depth_factor,
            "top_face_brightness_factor": self.top_face_brightness_factor,
            "side_face_brightness_factor": self.side_face_brightness_factor
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
        color_top_fill = color_utils.adjust_brightness(fill_color_rgb_actual, self.top_face_brightness_factor)
        color_side_fill = color_utils.adjust_brightness(fill_color_rgb_actual, self.side_face_brightness_factor)

        # 1. Рисуем заднюю грань (можно темнее боковых или тем же цветом)
        draw_context.polygon(self.back_vertices, fill=color_side_fill, outline=None) 

        # 2. Рисуем боковые соединяющие полигоны
        # Для лучшего 3D эффекта, можно было бы сортировать боковые грани
        # или применять к ним градиент яркости, но для начала так.
        for polygon_verts in self.side_connecting_polygons:
            # Можно варьировать цвет боковых граней для лучшего эффекта
            # Например, на основе их ориентации относительно источника света (если он есть)
            # Пока все одним цветом color_side_fill
            draw_context.polygon(polygon_verts, fill=color_side_fill, outline=None)

        # 3. Рисуем переднюю грань
        draw_context.polygon(self.front_vertices, fill=color_top_fill, outline=None) 

        # 4. Рисуем контуры поверх всего
        num_front_verts = len(self.front_vertices)
        for i in range(num_front_verts):
            draw_context.line([self.front_vertices[i], self.front_vertices[(i + 1) % num_front_verts]], 
                              fill=line_color, width=outline_width_upscaled)
            draw_context.line([self.back_vertices[i], self.back_vertices[(i + 1) % num_front_verts]], 
                              fill=line_color, width=outline_width_upscaled)
            draw_context.line([self.front_vertices[i], self.back_vertices[i]], 
                              fill=line_color, width=outline_width_upscaled)

    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # Проверяем попадание только в переднюю грань
        return geometry_utils.is_point_in_polygon(
            px=point_x_upscaled, py=point_y_upscaled,
            vertices=self.front_vertices
        )