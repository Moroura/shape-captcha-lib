# shape_captcha_lib/shapes/td_model/cross_3d.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import logging
import colorsys # Для adjust_brightness, если используется напрямую

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

logger = logging.getLogger(__name__)

class Cross3DShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Крест" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "cross_3d"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Для arm_length
        max_primary_size_upscaled: int,   # Для arm_length
        min_secondary_size_upscaled: Optional[int] = None, # Для arm_thickness
        max_secondary_size_upscaled: Optional[int] = None, # Для arm_thickness
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            arm_length = max(10, min_primary_size_upscaled)
        else:
            arm_length = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        min_thick = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(1, int(arm_length * 0.25))
        max_thick = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_thick + 1, int(arm_length * 0.4))
        
        if max_thick <= min_thick:
            arm_thickness = max(1, min_thick)
        else:
            arm_thickness = random.randint(min_thick, max_thick)
        
        if arm_thickness * 2 >= arm_length : # Убедимся, что толщина меньше половины длины руки
            arm_thickness = max(1, int(arm_length / 3))

        depth_factor = random.uniform(0.25, 0.4) # Визуальная глубина экструзии
        
        constraints = model_specific_constraints or {}
        top_face_brightness_factor = constraints.get("top_face_brightness_factor", 1.25)
        side_face_brightness_factor = constraints.get("side_face_brightness_factor", 0.75)

        return {
            "arm_length": arm_length, 
            "arm_thickness": arm_thickness,
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
        arm_length: Optional[int] = None,
        arm_thickness: Optional[int] = None,
        depth_factor: float = 0.3,
        top_face_brightness_factor: float = 1.25,
        side_face_brightness_factor: float = 0.75,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if arm_length is None or arm_thickness is None:
            raise ValueError("Arm_length and arm_thickness must be provided for Cross3DShape.")
        if not (isinstance(arm_length, int) and arm_length > 0 and \
                isinstance(arm_thickness, int) and arm_thickness > 0):
            raise ValueError("Arm_length and arm_thickness must be positive integers.")
        if arm_thickness * 2 >= arm_length:
             raise ValueError(f"Arm_thickness ({arm_thickness}) is too large for arm_length ({arm_length}).")

        self.arm_length_upscaled: int = arm_length
        self.arm_thickness_upscaled: int = arm_thickness
        self.depth_factor: float = depth_factor
        self.top_face_brightness_factor = top_face_brightness_factor
        self.side_face_brightness_factor = side_face_brightness_factor
        
        self._calculate_internal_geometry()

    def _calculate_internal_geometry(self):
        """Рассчитывает геометрию 3D-креста."""
        half_len = self.arm_length_upscaled / 2.0 # Половина длины "руки" от виртуального центра креста до конца руки
        half_thick = self.arm_thickness_upscaled / 2.0 # Половина толщины "руки"

        # Вершины 2D-креста, центрированные относительно (0,0)
        # Это форма передней грани
        cross_orig_centered: List[Tuple[float, float]] = [
            (-half_thick, -half_len), (half_thick, -half_len), (half_thick, -half_thick),
            (half_len, -half_thick),  (half_len, half_thick),  (half_thick, half_thick),
            (half_thick, half_len),   (-half_thick, half_len), (-half_thick, half_thick),
            (-half_len, half_thick),  (-half_len, -half_thick),(-half_thick, -half_thick)
        ]
        
        self.front_vertices: List[Tuple[int, int]] = \
            geometry_utils.calculate_rotated_polygon_vertices(
                self.cx_upscaled, self.cy_upscaled,
                cross_orig_centered, self.rotation_angle_rad
            )

        # Угол для отображения глубины
        depth_display_angle = -math.pi / 4 + self.rotation_angle_rad 
        
        # Фактическая глубина смещения для задних вершин (толщина креста в 3D)
        # Используем arm_thickness как меру "глубины" фигуры
        actual_depth_offset = int(self.arm_thickness_upscaled * self.depth_factor) 
        
        dx_depth = int(actual_depth_offset * math.cos(depth_display_angle))
        dy_depth = int(actual_depth_offset * math.sin(depth_display_angle))
        
        self.back_vertices: List[Tuple[int, int]] = [
            (v[0] + dx_depth, v[1] + dy_depth) for v in self.front_vertices
        ]
        
        # Боковые соединяющие полигоны (их 12)
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
            "arm_length": self.arm_length_upscaled,
            "arm_thickness": self.arm_thickness_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad,  # Ключ унифицирован
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

        # 1. Рисуем заднюю грань (если она видна или для полноты) - можно темнее
        # Для простоты, можно ее не рисовать, если боковые грани ее полностью закроют
        # draw_context.polygon(self.back_vertices, fill=color_side_fill, outline=line_color, width=1) # Слегка видна

        # 2. Рисуем боковые соединяющие полигоны
        for polygon_verts in self.side_connecting_polygons:
            draw_context.polygon(polygon_verts, fill=color_side_fill, outline=None) # Без outline для граней

        # 3. Рисуем переднюю грань
        draw_context.polygon(self.front_vertices, fill=color_top_fill, outline=None)

        # 4. Рисуем контуры поверх всего
        num_front_verts = len(self.front_vertices)
        for i in range(num_front_verts):
            # Ребра передней грани
            draw_context.line([self.front_vertices[i], self.front_vertices[(i + 1) % num_front_verts]], 
                              fill=line_color, width=outline_width_upscaled)
            # Ребра задней грани (если она рисовалась)
            draw_context.line([self.back_vertices[i], self.back_vertices[(i + 1) % num_front_verts]], 
                              fill=line_color, width=outline_width_upscaled)
            # Соединяющие ребра
            draw_context.line([self.front_vertices[i], self.back_vertices[i]], 
                              fill=line_color, width=outline_width_upscaled)

    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # Проверяем попадание только в переднюю грань
        return geometry_utils.is_point_in_polygon(
            px=point_x_upscaled, py=point_y_upscaled,
            vertices=self.front_vertices # self.front_vertices рассчитываются в __init__
        )