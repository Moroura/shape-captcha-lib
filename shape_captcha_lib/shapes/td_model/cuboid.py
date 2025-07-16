# shape_captcha_lib/shapes/td_model/cuboid.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import logging
import colorsys # Убедимся, что импортирован

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils
from ...utils import color_utils

logger = logging.getLogger(__name__)

class CuboidShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Кубоид (Параллелепипед)" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "cuboid"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Для ширины (width)
        max_primary_size_upscaled: int,   # Для ширины (width)
        min_secondary_size_upscaled: Optional[int] = None, # Для высоты (height)
        max_secondary_size_upscaled: Optional[int] = None, # Для высоты (height)
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        constraints = model_specific_constraints or {}

        if max_primary_size_upscaled <= min_primary_size_upscaled:
            width = max(10, min_primary_size_upscaled)
        else:
            width = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)

        # Высота как secondary или пропорционально ширине
        min_h = min_secondary_size_upscaled if min_secondary_size_upscaled is not None else max(int(width * 0.4), 5)
        max_h = max_secondary_size_upscaled if max_secondary_size_upscaled is not None else max(min_h + 1, int(width * 0.7))
        if max_h <= min_h: height = max(5, min_h)
        else: height = random.randint(min_h, max_h)

        # Глубина, например, пропорционально ширине или высоте
        min_d_factor = constraints.get("min_depth_factor_of_width", 0.3)
        max_d_factor = constraints.get("max_depth_factor_of_width", 0.6)
        depth = int(width * random.uniform(min_d_factor, max_d_factor))
        depth = max(5, depth)
        
        depth_factor_visual = random.uniform(0.4, 0.6)
        top_face_brightness_factor = constraints.get("top_face_brightness_factor", 1.4)
        side_face_brightness_factor = constraints.get("side_face_brightness_factor", 0.75)

        return {
            "width": width, "height": height, "depth": depth,
            "depth_factor_visual": depth_factor_visual,
            "top_face_brightness_factor": top_face_brightness_factor,
            "side_face_brightness_factor": side_face_brightness_factor
        }

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        depth: Optional[int] = None,
        depth_factor_visual: float = 0.5,
        top_face_brightness_factor: float = 1.4,
        side_face_brightness_factor: float = 0.75,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if width is None or height is None or depth is None:
            raise ValueError("Width, height, and depth must be provided for CuboidShape.")
        if not (isinstance(width, int) and width > 0 and \
                isinstance(height, int) and height > 0 and \
                isinstance(depth, int) and depth > 0):
            raise ValueError(f"Dimensions must be positive integers, got w={width}, h={height}, d={depth}.")

        self.width_upscaled: int = width
        self.height_upscaled: int = height
        self.depth_upscaled: int = depth # Глубина самого объекта
        self.depth_factor_visual: float = depth_factor_visual # Визуальный фактор глубины проекции
        self.top_face_brightness_factor = top_face_brightness_factor
        self.side_face_brightness_factor = side_face_brightness_factor
        
        self._calculate_internal_geometry()

    def _calculate_internal_geometry(self):
        half_w = self.width_upscaled / 2.0
        half_h = self.height_upscaled / 2.0
        
        front_face_orig_centered: List[Tuple[float, float]] = [
            (-half_w, -half_h), (half_w, -half_h),
            (half_w, half_h),  (-half_w, half_h)
        ]
        
        self.front_vertices: List[Tuple[int, int]] = \
            geometry_utils.calculate_rotated_polygon_vertices(
                self.cx_upscaled, self.cy_upscaled,
                front_face_orig_centered, self.rotation_angle_rad
            )

        depth_display_angle = -math.pi / 4 + self.rotation_angle_rad
        dx_depth = int(self.depth_upscaled * self.depth_factor_visual * math.cos(depth_display_angle))
        dy_depth = int(self.depth_upscaled * self.depth_factor_visual * math.sin(depth_display_angle))
        
        self.back_vertices: List[Tuple[int, int]] = [
            (v[0] + dx_depth, v[1] + dy_depth) for v in self.front_vertices
        ]
        
        self.top_face_vertices: List[Tuple[int, int]] = [
            self.front_vertices[0], self.front_vertices[1], 
            self.back_vertices[1], self.back_vertices[0]
        ]
        self.side_face_vertices: List[Tuple[int, int]] = [
            self.front_vertices[1], self.back_vertices[1], 
            self.back_vertices[2], self.front_vertices[2]
        ]
        
        all_vertices_for_bbox = self.front_vertices + self.back_vertices
        unique_vertices_for_bbox = list(dict.fromkeys(all_vertices_for_bbox))
        
        self.bbox_upscaled_coords: List[float] = \
            geometry_utils.calculate_polygon_bounding_box(unique_vertices_for_bbox)

        self.clickable_polygons: List[Dict[str, Any]] = [
            {"name": "front_face", "vertices": self.front_vertices},
            {"name": "top_face", "vertices": self.top_face_vertices},
            {"name": "side_face", "vertices": self.side_face_vertices}
        ]

    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,
            "cy_upscaled": self.cy_upscaled,
            "width": self.width_upscaled,
            "height": self.height_upscaled,
            "depth": self.depth_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad,
            "depth_factor_visual": self.depth_factor_visual,
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
        color_front_fill = fill_color_rgb_actual
        color_top_fill = color_utils.adjust_brightness(fill_color_rgb_actual, self.top_face_brightness_factor)
        color_side_fill = color_utils.adjust_brightness(fill_color_rgb_actual, self.side_face_brightness_factor)

        _r, _g, _b = [x / 255.0 for x in fill_color_rgb_actual]
        _, base_l, base_s = colorsys.rgb_to_hls(_r, _g, _b) # colorsys должен быть импортирован
        if base_l < 0.25: 
            color_side_fill = color_utils.adjust_brightness(fill_color_rgb_actual, 1.20, max_l_for_lighten=0.4) 
            color_top_fill = color_utils.adjust_brightness(fill_color_rgb_actual, 1.50, max_l_for_lighten=0.5)  
            if base_s < 0.2: 
                 color_side_fill = color_utils.adjust_brightness(color_side_fill, 1.0, saturation_boost_amount=0.25)
                 color_top_fill = color_utils.adjust_brightness(color_top_fill, 1.0, saturation_boost_amount=0.25)
        
        line_color = color_utils.get_contrasting_line_color(fill_color_rgb_actual, dark_factor=0.2, light_factor=2.2)

        # Порядок отрисовки: дальние грани -> ближние грани
        # Здесь упрощенный порядок, который обычно работает для такого угла обзора
        draw_context.polygon(self.side_face_vertices, fill=color_side_fill, outline=None)
        draw_context.polygon(self.top_face_vertices, fill=color_top_fill, outline=None)
        draw_context.polygon(self.front_vertices, fill=color_front_fill, outline=None)
        
        for i in range(4):
            draw_context.line([self.front_vertices[i], self.front_vertices[(i + 1) % 4]], fill=line_color, width=outline_width_upscaled)
            draw_context.line([self.back_vertices[i], self.back_vertices[(i + 1) % 4]], fill=line_color, width=outline_width_upscaled)
            draw_context.line([self.front_vertices[i], self.back_vertices[i]], fill=line_color, width=outline_width_upscaled)

    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        for face_data in self.clickable_polygons:
            if geometry_utils.is_point_in_polygon(
                px=point_x_upscaled, 
                py=point_y_upscaled, 
                vertices=face_data["vertices"]
            ):
                return True
        return False