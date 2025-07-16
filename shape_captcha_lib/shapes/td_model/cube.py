# shape_captcha_lib/shapes/td_model/cube.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import colorsys

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils # Для is_point_in_polygon, calculate_rotated_polygon_vertices, calculate_polygon_bounding_box
from ...utils import color_utils   # Для get_rgb_color, adjust_brightness, get_contrasting_line_color

class CubeShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Куб" для CAPTCHA.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "cube"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Длина стороны (side)
        max_primary_size_upscaled: int,   # Длина стороны (side)
        min_secondary_size_upscaled: Optional[int] = None, # Не используется напрямую для основных размеров
        max_secondary_size_upscaled: Optional[int] = None, # Не используется напрямую для основных размеров
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            side = max(10, min_primary_size_upscaled) 
        else:
            side = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)
        
        # depth_factor определяет визуальную глубину куба
        depth_factor = random.uniform(0.4, 0.6) 
        
        # Факторы яркости для граней (можно сделать конфигурируемыми)
        top_face_brightness_factor = model_specific_constraints.get("top_face_brightness_factor", 1.45) \
            if model_specific_constraints else 1.45
        side_face_brightness_factor = model_specific_constraints.get("side_face_brightness_factor", 0.7) \
            if model_specific_constraints else 0.7

        return {
            "side": side, 
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
        side: Optional[int] = None,
        depth_factor: Optional[float] = None,
        top_face_brightness_factor: float = 1.45, # Значения по умолчанию из drawing_3d
        side_face_brightness_factor: float = 0.7, # Значения по умолчанию из drawing_3d
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad
        )
        if side is None or depth_factor is None:
            raise ValueError("Side and depth_factor must be provided for CubeShape.")
        if not (isinstance(side, int) and side > 0 and isinstance(depth_factor, float) and 0 < depth_factor < 1):
            raise ValueError(f"Side must be positive int, depth_factor positive float < 1. Got side={side}, depth_factor={depth_factor}")

        self.side_upscaled: int = side
        self.depth_factor: float = depth_factor
        self.top_face_brightness_factor = top_face_brightness_factor
        self.side_face_brightness_factor = side_face_brightness_factor

        self._calculate_internal_geometry()


    def _calculate_internal_geometry(self):
        """Рассчитывает вершины граней куба."""
        half_side = self.side_upscaled / 2.0
        
        # Вершины передней грани, центрированные относительно (0,0)
        front_face_orig_centered: List[Tuple[float, float]] = [
            (-half_side, -half_side), (half_side, -half_side),
            (half_side, half_side),  (-half_side, half_side)
        ]
        
        # Поворачиваем и смещаем вершины передней грани
        self.front_vertices: List[Tuple[int, int]] = \
            geometry_utils.calculate_rotated_polygon_vertices(
                self.cx_upscaled, self.cy_upscaled,
                front_face_orig_centered, self.rotation_angle_rad
            )

        # Угол для отображения глубины (немного зависит от основного угла поворота)
        # Это создает иллюзию перспективы для "уходящих" ребер
        depth_display_angle = -math.pi / 4 + self.rotation_angle_rad 
        
        # Смещение для задних вершин
        dx_depth = int(self.side_upscaled * self.depth_factor * math.cos(depth_display_angle))
        dy_depth = int(self.side_upscaled * self.depth_factor * math.sin(depth_display_angle)) 
        
        self.back_vertices: List[Tuple[int, int]] = [
            (v[0] + dx_depth, v[1] + dy_depth) for v in self.front_vertices
        ]
        
        # Определяем видимые грани (эти списки будут использоваться для is_point_inside и draw)
        # Порядок вершин важен для корректной отрисовки и проверки полигонов
        self.top_face_vertices: List[Tuple[int, int]] = [
            self.front_vertices[0], self.front_vertices[1], 
            self.back_vertices[1], self.back_vertices[0]
        ]
        self.side_face_vertices: List[Tuple[int, int]] = [ # Обычно это правая боковая грань
            self.front_vertices[1], self.back_vertices[1], 
            self.back_vertices[2], self.front_vertices[2]
        ]
        
        # Собираем все вершины для расчета общего bbox
        all_vertices_for_bbox = self.front_vertices + self.back_vertices
        # Убираем дубликаты, если они есть (хотя здесь их быть не должно)
        unique_vertices_for_bbox = list(dict.fromkeys(all_vertices_for_bbox))
        
        self.bbox_upscaled_coords: List[float] = \
            geometry_utils.calculate_polygon_bounding_box(unique_vertices_for_bbox)

        # Грани, по которым можно кликать
        self.clickable_polygons: List[Dict[str, Any]] = [
            {"name": "front_face", "vertices": self.front_vertices},
            {"name": "top_face", "vertices": self.top_face_vertices},
            {"name": "side_face", "vertices": self.side_face_vertices}
        ]


    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,
            "cy_upscaled": self.cy_upscaled,
            "side": self.side_upscaled,
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
        fill_color_rgb_actual: Tuple[int, int, int], # Базовый RGB цвет заливки
        outline_width_upscaled: int,
        brightness_factor_for_outline: Optional[float] = None, # Не используется напрямую
        background_color_rgb_actual: Optional[Tuple[int, int, int]] = None
    ):
        # Определяем цвета для граней на основе базового fill_color_rgb_actual
        # и факторов яркости, сохраненных в экземпляре
        color_front_fill = fill_color_rgb_actual # Передняя грань - базовый цвет
        color_top_fill = color_utils.adjust_brightness(fill_color_rgb_actual, self.top_face_brightness_factor)
        color_side_fill = color_utils.adjust_brightness(fill_color_rgb_actual, self.side_face_brightness_factor)

        # Улучшение для очень темных цветов (из drawing_3d.py)
        _r, _g, _b = [x / 255.0 for x in fill_color_rgb_actual]
        _, base_l, base_s = colorsys.rgb_to_hls(_r, _g, _b)
        if base_l < 0.25: 
            color_side_fill = color_utils.adjust_brightness(fill_color_rgb_actual, 1.25, max_l_for_lighten=0.45) 
            color_top_fill = color_utils.adjust_brightness(fill_color_rgb_actual, 1.55, max_l_for_lighten=0.55)  
            if base_s < 0.2: # Если почти серый, добавляем насыщенности
                 color_side_fill = color_utils.adjust_brightness(color_side_fill, 1.0, saturation_boost_amount=0.3)
                 color_top_fill = color_utils.adjust_brightness(color_top_fill, 1.0, saturation_boost_amount=0.3)
        
        line_color = color_utils.get_contrasting_line_color(fill_color_rgb_actual, dark_factor=0.2, light_factor=2.2)

        # Рисуем грани (от дальних к ближним или в зависимости от видимости)
        # Порядок отрисовки важен для правильного перекрытия.
        # Сначала боковую и верхнюю, потом переднюю.
        draw_context.polygon(self.side_face_vertices, fill=color_side_fill, outline=None) # Без контура для самой грани
        draw_context.polygon(self.top_face_vertices, fill=color_top_fill, outline=None)
        draw_context.polygon(self.front_vertices, fill=color_front_fill, outline=None)
        
        # Рисуем ребра поверх залитых граней
        for i in range(4):
            draw_context.line([self.front_vertices[i], self.front_vertices[(i + 1) % 4]], fill=line_color, width=outline_width_upscaled)
            draw_context.line([self.back_vertices[i], self.back_vertices[(i + 1) % 4]], fill=line_color, width=outline_width_upscaled)
            draw_context.line([self.front_vertices[i], self.back_vertices[i]], fill=line_color, width=outline_width_upscaled)


    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # Проверяем попадание в любую из "кликабельных" граней
        # self.clickable_polygons был установлен в _calculate_internal_geometry (вызванном из __init__)
        for face_data in self.clickable_polygons:
            if geometry_utils.is_point_in_polygon(
                px=point_x_upscaled, 
                py=point_y_upscaled, 
                vertices=face_data["vertices"]
            ):
                # print(f"DEBUG [CubeShape@{id(self)}]: HIT on face {face_data['name']}")
                return True
        # print(f"DEBUG [CubeShape@{id(self)}]: MISS on all faces for point ({point_x_upscaled}, {point_y_upscaled})")
        return False