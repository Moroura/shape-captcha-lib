# shape_captcha_lib/shapes/td_model/pyramid.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import logging

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

logger = logging.getLogger(__name__)

class PyramidShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Пирамида" (с квадратным основанием) для CAPTCHA.
    cx_upscaled, cy_upscaled в __init__ - это центр квадратного основания на плоскости отрисовки.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "pyramid"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Для стороны основания (base_side)
        max_primary_size_upscaled: int,   # Для стороны основания (base_side)
        min_secondary_size_upscaled: Optional[int] = None, # Для высоты (height)
        max_secondary_size_upscaled: Optional[int] = None, # Для высоты (height)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            base_side = max(10, min_primary_size_upscaled)
        else:
            base_side = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        min_h = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(int(base_side * 0.7), 10)
        max_h = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_h + 1, int(base_side * 1.3))
        
        if max_h <= min_h:
            height = max(5, min_h)
        else:
            height = random.randint(min_h, max_h)
        
        depth_factor_base = random.uniform(0.45, 0.6) # Для перспективы основания
        
        constraints = model_specific_constraints or {}
        # Факторы яркости граней и основания
        face_brightness_factors = constraints.get("face_brightness_factors", [1.2, 0.95, 0.75, 0.6])
        base_brightness_factor = constraints.get("base_brightness_factor", 0.45)

        return {
            "base_side": base_side, 
            "height": height,
            "depth_factor_base": depth_factor_base,
            "face_brightness_factors": face_brightness_factors,
            "base_brightness_factor": base_brightness_factor
        }

    def __init__(
        self,
        cx_upscaled: int, # Центр X основания на плоскости отрисовки
        cy_upscaled: int, # Центр Y основания на плоскости отрисовки
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0, # Угол поворота основания вокруг его центра
        base_side: Optional[int] = None,
        height: Optional[int] = None,
        depth_factor_base: float = 0.5,
        face_brightness_factors: Optional[List[float]] = None,
        base_brightness_factor: float = 0.45,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled, # Это cx_base_center
            cy_upscaled=cy_upscaled, # Это cy_base_center
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad 
        )
        if base_side is None or height is None:
            raise ValueError("Base side and height must be provided for PyramidShape.")
        if not (isinstance(base_side, int) and base_side > 0 and isinstance(height, int) and height > 0):
            raise ValueError(f"Base side and height must be positive integers, got bs={base_side}, h={height}.")

        self.base_side_upscaled: int = base_side
        self.height_upscaled: int = height
        self.depth_factor_base: float = depth_factor_base
        self.face_brightness_factors = face_brightness_factors or [1.2, 0.95, 0.75, 0.6]
        self.base_brightness_factor = base_brightness_factor
        
        self._calculate_internal_geometry()

    def _calculate_internal_geometry(self):
        """Рассчитывает геометрию пирамиды."""
        # Апекс (вершина) пирамиды. cy_upscaled - это центр основания, апекс выше.
        self.apex: Tuple[int, int] = (self.cx_upscaled, self.cy_upscaled - self.height_upscaled)
        
        half_s = self.base_side_upscaled / 2.0
        # Вершины квадратного основания, центрированные в (0,0) ДО поворота и проекции
        base_orig_centered: List[Tuple[float, float]] = [
            (-half_s, -half_s), (half_s, -half_s), 
            (half_s, half_s),  (-half_s, half_s)
        ]
        
        # Поворачиваем вершины основания вокруг (0,0) на self.rotation_angle_rad
        base_rotated_centered: List[Tuple[float, float]] = []
        cos_rot = math.cos(self.rotation_angle_rad)
        sin_rot = math.sin(self.rotation_angle_rad)
        for vx, vy in base_orig_centered:
            rvx = vx * cos_rot - vy * sin_rot
            rvy = vx * sin_rot + vy * cos_rot
            base_rotated_centered.append((rvx, rvy))

        # Проецируем повернутые вершины основания на плоскость отрисовки
        # и смещаем к центру self.cx_upscaled, self.cy_upscaled
        self.base_vertices_on_plane: List[Tuple[int, int]] = []
        for rvx, rvy in base_rotated_centered:
            # Применяем depth_factor для создания эффекта перспективы для основания
            # Вершины с большим rvy (дальше от наблюдателя, если rvy > 0 означает "вглубь")
            # или меньшим rvy (если rvy < 0 означает "вглубь" при стандартной ориентации Y вниз)
            # В старом коде: projected_y_offset = rvy * (depth_factor_base if rvy < 0 else 1.0)
            # Это значит, что если Y направлена вниз, то rvy < 0 - это "верхние" (дальние) части основания,
            # и для них применяется depth_factor.
            # Если Y направлена вверх, то rvy > 0 - "дальние" части.
            # Будем считать, что Y в Pillow идет вниз, значит rvy < 0 - это верхняя (дальняя) часть квадрата основания.
            y_perspective_scale = self.depth_factor_base if rvy < 0 else 1.0
            projected_y = rvy * y_perspective_scale
            
            self.base_vertices_on_plane.append(
                (int(round(self.cx_upscaled + rvx)), 
                 int(round(self.cy_upscaled + projected_y)))
            )
        
        b0, b1, b2, b3 = self.base_vertices_on_plane

        # Боковые грани - треугольники, образованные апексом и двумя смежными вершинами основания
        self.side_faces_vertices: List[List[Tuple[int, int]]] = [
            [self.apex, b0, b1],
            [self.apex, b1, b2],
            [self.apex, b2, b3],
            [self.apex, b3, b0]
        ]

        # Кликабельные полигоны: основание и все боковые грани
        self.clickable_polygons_params: List[Dict[str, Any]] = [
            {"name": "base_face", "vertices": self.base_vertices_on_plane}
        ]
        for i, face_verts in enumerate(self.side_faces_vertices):
            self.clickable_polygons_params.append({"name": f"side_face_{i}", "vertices": face_verts})

        # Общий bbox
        all_vertices_for_bbox = [self.apex] + self.base_vertices_on_plane
        self.bbox_upscaled_coords: List[float] = \
            geometry_utils.calculate_polygon_bounding_box(all_vertices_for_bbox)

    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled, # Используем self.cx_upscaled из AbstractShape
            "cy_upscaled": self.cy_upscaled, # Используем self.cy_upscaled из AbstractShape
            "base_side": self.base_side_upscaled,
            "height": self.height_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad,
            "depth_factor_base": self.depth_factor_base,
            "face_brightness_factors": self.face_brightness_factors,
            "base_brightness_factor": self.base_brightness_factor
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
        brightness_factor_for_outline: Optional[float] = None, # Не используется напрямую
        background_color_rgb_actual: Optional[Tuple[int, int, int]] = None
    ):
        line_color = color_utils.get_contrasting_line_color(fill_color_rgb_actual, dark_factor=0.2, light_factor=2.2)
        
        # Цвет основания
        color_base_fill = color_utils.adjust_brightness(fill_color_rgb_actual, self.base_brightness_factor)

        # Собираем все грани (основание + боковые) для сортировки и отрисовки
        # avg_y_base - средняя Y координата вершин основания грани, для Z-сортировки
        # Для основания используем среднюю Y всех его вершин
        faces_to_draw_data = []
        
        # Основание
        avg_y_base_plane = sum(v[1] for v in self.base_vertices_on_plane) / 4.0
        faces_to_draw_data.append({
            "vertices": self.base_vertices_on_plane, 
            "color": color_base_fill,
            "sort_key": avg_y_base_plane # Основание обычно дальше, если смотреть сверху
        })

        # Боковые грани
        for i, face_verts in enumerate(self.side_faces_vertices):
            # Для боковой грани, ключ сортировки - средняя Y ее двух вершин на основании
            avg_y_side_face_base = (face_verts[1][1] + face_verts[2][1]) / 2.0 
            face_color = color_utils.adjust_brightness(
                fill_color_rgb_actual, 
                self.face_brightness_factors[i % len(self.face_brightness_factors)]
            )
            faces_to_draw_data.append({
                "vertices": face_verts,
                "color": face_color,
                "sort_key": avg_y_side_face_base
            })
        
        # Сортируем грани: те, у которых "средняя Y основания" больше (ниже на экране), рисуются раньше (дальше)
        # Однако, для пирамиды, если смотрим сверху, основание всегда "дальше" боковых граней,
        # а боковые грани сортируются по Y их "нижних" ребер.
        # Старый код сортировал только боковые грани: faces_data.sort(key=lambda f: f["avg_y_base"], reverse=False)
        # где avg_y_base это средняя Y вершин ребра на основании.
        # Если reverse=False, то грани с меньшей средней Y (выше на экране) рисуются раньше.
        # Это неверно для перекрытия. Нужно reverse=True или рисовать по sort_key от меньшего к большему.
        # Меньшие Y (выше) должны рисоваться позже, если они перекрывают.
        # Или, дальние грани (большие Y, если Y растет вниз) рисуются первыми.
        
        # Правильная Z-сортировка для простого случая: рисуем сначала основание,
        # затем боковые грани, отсортированные так, чтобы "дальние" (с большей средней Y двух нижних вершин) рисовались первыми.
        
        draw_context.polygon(self.base_vertices_on_plane, fill=color_base_fill, outline=None)

        # Собираем только боковые грани для сортировки
        side_faces_render_data = []
        for i, face_verts in enumerate(self.side_faces_vertices):
            avg_y_face_base_edge = (face_verts[1][1] + face_verts[2][1]) / 2.0
            face_color = color_utils.adjust_brightness(
                fill_color_rgb_actual,
                self.face_brightness_factors[i % len(self.face_brightness_factors)]
            )
            side_faces_render_data.append({
                "vertices": face_verts,
                "color": face_color,
                "avg_y": avg_y_face_base_edge # Для сортировки
            })
        
        # Сортируем боковые грани: те, у кого средняя Y ребра на основании БОЛЬШЕ (они "дальше" вглубь),
        # рисуются РАНЬШЕ.
        side_faces_render_data.sort(key=lambda f: f["avg_y"], reverse=True)

        for face_data in side_faces_render_data:
            draw_context.polygon(face_data["vertices"], fill=face_data["color"], outline=None)

        # Рисуем ребра поверх
        for i in range(4): # Ребра основания
            draw_context.line([self.base_vertices_on_plane[i], self.base_vertices_on_plane[(i + 1) % 4]], 
                              fill=line_color, width=outline_width_upscaled)
        for i in range(4): # Боковые ребра к апексу
            draw_context.line([self.base_vertices_on_plane[i], self.apex], 
                              fill=line_color, width=outline_width_upscaled)


    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # self.clickable_polygons_params был установлен в _calculate_internal_geometry
        for face_data in self.clickable_polygons_params:
            if geometry_utils.is_point_in_polygon(
                px=point_x_upscaled, 
                py=point_y_upscaled, 
                vertices=face_data["vertices"]
            ):
                # print(f"DEBUG [PyramidShape@{id(self)}]: HIT on face {face_data.get('name', 'unknown')}")
                return True
        # print(f"DEBUG [PyramidShape@{id(self)}]: MISS on all faces for point ({point_x_upscaled}, {point_y_upscaled})")
        return False