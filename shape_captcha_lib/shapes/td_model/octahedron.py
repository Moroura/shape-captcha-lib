# shape_captcha_lib/shapes/td_model/octahedron.py
import random
import math
from typing import Dict, Any, Tuple, Union, Optional, List
import logging

from PIL import ImageDraw

from ..abc import AbstractShape, ShapeDrawingDetails
from ...utils import geometry_utils # Понадобится для 3D вращений и проекции
from ...utils import color_utils

logger = logging.getLogger(__name__)

class OctahedronShape(AbstractShape):
    """
    Представление фигуры "Псевдо-3D Октаэдр" для CAPTCHA.
    cx_upscaled, cy_upscaled в __init__ - это центр октаэдра.
    """

    @staticmethod
    def get_shape_type() -> str:
        return "octahedron"

    @staticmethod
    def generate_size_params(
        image_width_upscaled: int,
        image_height_upscaled: int,
        min_primary_size_upscaled: int,   # Для "размера" (радиуса описанной сферы)
        max_primary_size_upscaled: int,   # Для "размера"
        min_secondary_size_upscaled: Optional[int] = None, # Не используется напрямую
        max_secondary_size_upscaled: Optional[int] = None, # Не используется напрямую
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if max_primary_size_upscaled <= min_primary_size_upscaled:
            size = max(10, min_primary_size_upscaled)
        else:
            size = random.randint(min_primary_size_upscaled, max_primary_size_upscaled)
        
        constraints = model_specific_constraints or {}
        # Фиксированные углы для статичного вида, но позволяем их переопределить через constraints
        tilt_angle_rad = constraints.get("tilt_angle_rad", 0.0) # По умолчанию без наклона
        # rotation_angle_rad будет устанавливаться в image_generator,
        # но мы можем предложить стандартное значение для preview или если image_generator не задаст.
        # Или же, если октаэдр ВСЕГДА должен быть без вращения, то это нужно учесть в image_generator.py.
        # Пока что rotation_angle_rad будет приходить извне.

        perspective_factor_z = constraints.get("perspective_factor_z", 0.4) # Уменьшим для меньшего искажения
        brightness_factors = constraints.get("brightness_factors", [1.0, 0.85, 0.75, 0.65, 0.8, 0.7, 0.6, 0.5])


        return {
            "size": size, 
            "tilt_angle_rad": tilt_angle_rad, # Теперь может быть фиксированным
            "perspective_factor_z": perspective_factor_z,
            "brightness_factors": brightness_factors,
        }

    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0, # Может быть установлен в 0 в image_generator для октаэдра
        size: Optional[int] = None,
        tilt_angle_rad: float = 0.0,     # Принимаем из generate_size_params
        perspective_factor_z: float = 0.4, # Используем обновленное значение
        brightness_factors: Optional[List[float]] = None,
        **kwargs: Any
    ):
        super().__init__(
            cx_upscaled=cx_upscaled,
            cy_upscaled=cy_upscaled,
            color_name_or_rgb=color_name_or_rgb,
            rotation_angle_rad=rotation_angle_rad 
        )
        if size is None:
            raise ValueError("Size must be provided for OctahedronShape.")
        if not (isinstance(size, int) and size > 0):
            raise ValueError(f"Size must be a positive integer, got s={size}.")

        self.size_upscaled: int = size
        self.tilt_angle_rad: float = tilt_angle_rad
        self.perspective_factor_z: float = perspective_factor_z
        self.brightness_factors = brightness_factors or [1.0, 0.9, 0.8, 0.7, 0.85, 0.75, 0.65, 0.55]
        
        self._calculate_internal_geometry()

    def _apply_rotations_and_projection(self, point_3d: Tuple[float, float, float]) -> Tuple[int, int]:
        x, y, z = point_3d
        
        # 1. Применяем наклон (вокруг оси X)
        y_t = y * math.cos(self.tilt_angle_rad) - z * math.sin(self.tilt_angle_rad)
        z_t = y * math.sin(self.tilt_angle_rad) + z * math.cos(self.tilt_angle_rad)
        x_t = x

        # 2. Применяем вращение (вокруг оси Y)
        x_r = x_t * math.cos(self.rotation_angle_rad) + z_t * math.sin(self.rotation_angle_rad)
        z_r = -x_t * math.sin(self.rotation_angle_rad) + z_t * math.cos(self.rotation_angle_rad)
        y_r = y_t
        
        # 3. Проекция на 2D и смещение в центр CAPTCHA
        # Простая ортографическая проекция с учетом перспективы по Z
        projected_x = self.cx_upscaled + int(round(x_r))
        projected_y = self.cy_upscaled + int(round(y_r + z_r * self.perspective_factor_z))
        
        return projected_x, projected_y

    def _get_vertex_avg_z_after_transform(self, point_3d: Tuple[float, float, float]) -> float:
        """ Вспомогательная функция для получения Z-координаты вершины ПОСЛЕ всех трансформаций,
            но ПЕРЕД финальной проекцией на экран (используется для сортировки граней).
        """
        x, y, z = point_3d
        y_t = y * math.cos(self.tilt_angle_rad) - z * math.sin(self.tilt_angle_rad)
        z_t = y * math.sin(self.tilt_angle_rad) + z * math.cos(self.tilt_angle_rad)
        x_t = x
        # x_r = x_t * math.cos(self.rotation_angle_rad) + z_t * math.sin(self.rotation_angle_rad) # не нужен для Z
        z_r = -x_t * math.sin(self.rotation_angle_rad) + z_t * math.cos(self.rotation_angle_rad)
        return z_r


    def _calculate_internal_geometry(self):
        s = float(self.size_upscaled)
        
        # 1. Канонические 3D вершины октаэдра (Y - вертикальная ось)
        v_top_3d    = (0, -s, 0)  # Верхняя
        v_bottom_3d = (0,  s, 0)  # Нижняя
        v_eq1_3d    = (s,  0, 0)  # Экваториальная (+X)
        v_eq2_3d    = (0,  0, s)  # Экваториальная (+Z, "передняя")
        v_eq3_3d    = (-s, 0, 0)  # Экваториальная (-X)
        v_eq4_3d    = (0,  0, -s) # Экваториальная (-Z, "задняя")
        
        canonical_vertices_3d = [v_top_3d, v_bottom_3d, v_eq1_3d, v_eq2_3d, v_eq3_3d, v_eq4_3d]

        # 2. Применяем трансформации и проекцию к каждой вершине
        self.projected_vertices: Dict[str, Tuple[int, int]] = {
            "top":    self._apply_rotations_and_projection(v_top_3d),
            "bottom": self._apply_rotations_and_projection(v_bottom_3d),
            "eq1":    self._apply_rotations_and_projection(v_eq1_3d), # +X
            "eq2":    self._apply_rotations_and_projection(v_eq2_3d), # +Z
            "eq3":    self._apply_rotations_and_projection(v_eq3_3d), # -X
            "eq4":    self._apply_rotations_and_projection(v_eq4_3d)  # -Z
        }
        
        # Для сортировки граней, получаем Z-координаты после трансформаций
        self.transformed_vertices_avg_z: Dict[str, float] = {
            name: self._get_vertex_avg_z_after_transform(v_3d)
            for name, v_3d in zip(
                ["top", "bottom", "eq1", "eq2", "eq3", "eq4"],
                canonical_vertices_3d
            )
        }

        # 3. Определяем 8 треугольных граней по спроецированным вершинам
        # Грани именуются по вершинам, из которых они состоят
        # Верхние 4 грани (с v_top)
        # Нижние 4 грани (с v_bottom)
        # Порядок вершин важен для вычисления нормалей (если бы мы их использовали),
        # но для 2D отрисовки просто определяет полигон.
        # Для сортировки будем использовать среднюю Z-координату вершин грани.
        
        pv = self.projected_vertices # короткое имя для спроецированных вершин
        
        # Определяем грани и их средние Z-координаты для сортировки
        # Каждая грань - это список вершин и ее средняя Z-координата (до проекции на 2D)
        self.faces_data_for_drawing: List[Dict[str, Any]] = []
        
        # Список ребер экватора: (eq1,eq2), (eq2,eq3), (eq3,eq4), (eq4,eq1)
        equatorial_edges = [
            ("eq1", "eq2", v_eq1_3d, v_eq2_3d), 
            ("eq2", "eq3", v_eq2_3d, v_eq3_3d),
            ("eq3", "eq4", v_eq3_3d, v_eq4_3d),
            ("eq4", "eq1", v_eq4_3d, v_eq1_3d)
        ]

        for v1_name, v2_name, v1_3d, v2_3d in equatorial_edges:
            # Верхняя грань
            avg_z_top_face = (self._get_vertex_avg_z_after_transform(v_top_3d) + 
                              self._get_vertex_avg_z_after_transform(v1_3d) +
                              self._get_vertex_avg_z_after_transform(v2_3d)) / 3.0
            self.faces_data_for_drawing.append({
                "vertices_2d": [pv["top"], pv[v1_name], pv[v2_name]],
                "avg_z_transformed": avg_z_top_face,
                "name": f"top_{v1_name}_{v2_name}"
            })
            # Нижняя грань (порядок вершин изменен для возможной правильной нормали, если бы она была)
            avg_z_bottom_face = (self._get_vertex_avg_z_after_transform(v_bottom_3d) +
                                 self._get_vertex_avg_z_after_transform(v1_3d) +
                                 self._get_vertex_avg_z_after_transform(v2_3d)) / 3.0
            self.faces_data_for_drawing.append({
                "vertices_2d": [pv["bottom"], pv[v2_name], pv[v1_name]], # Изменен порядок v1, v2
                "avg_z_transformed": avg_z_bottom_face,
                "name": f"bottom_{v2_name}_{v1_name}"
            })
            
        # Кликабельные полигоны - это просто 2D-вершины граней
        self.clickable_polygons_params: List[Dict[str, Any]] = [
            {"name": face["name"], "vertices": face["vertices_2d"]} for face in self.faces_data_for_drawing
        ]
        
        # Общий bbox
        all_projected_vertices_list = list(self.projected_vertices.values())
        self.bbox_upscaled_coords: List[float] = \
            geometry_utils.calculate_polygon_bounding_box(all_projected_vertices_list)

    def get_draw_details(self) -> ShapeDrawingDetails:
        params_for_storage = {
            "cx_upscaled": self.cx_upscaled,
            "cy_upscaled": self.cy_upscaled,
            "size": self.size_upscaled,
            "rotation_angle_rad": self.rotation_angle_rad,
            "tilt_angle_rad": self.tilt_angle_rad,
            "perspective_factor_z": self.perspective_factor_z,
            "brightness_factors": self.brightness_factors
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
        # Сортируем грани для отрисовки: те, у кого средняя Z-координата (после трансформаций)
        # МЕНЬШЕ (т.е. дальше от наблюдателя, если +Z к нам), рисуются ПЕРВЫМИ.
        sorted_faces = sorted(self.faces_data_for_drawing, key=lambda f: f["avg_z_transformed"])
        
        line_color = color_utils.get_contrasting_line_color(fill_color_rgb_actual, dark_factor=0.2, light_factor=2.0)

        for i, face_data in enumerate(sorted_faces):
            brightness = self.brightness_factors[i % len(self.brightness_factors)]
            face_color = color_utils.adjust_brightness(fill_color_rgb_actual, brightness)
            draw_context.polygon(face_data["vertices_2d"], fill=face_color, outline=None) # Сначала без обводки

        # Рисуем все ребра после заливки всех граней
        # Ребра от верхних/нижних вершин к экваториальным
        pv = self.projected_vertices
        for eq_v_name in ["eq1", "eq2", "eq3", "eq4"]:
            draw_context.line([pv["top"], pv[eq_v_name]], fill=line_color, width=outline_width_upscaled)
            draw_context.line([pv["bottom"], pv[eq_v_name]], fill=line_color, width=outline_width_upscaled)
        
        # Ребра на экваторе
        draw_context.line([pv["eq1"], pv["eq2"]], fill=line_color, width=outline_width_upscaled)
        draw_context.line([pv["eq2"], pv["eq3"]], fill=line_color, width=outline_width_upscaled)
        draw_context.line([pv["eq3"], pv["eq4"]], fill=line_color, width=outline_width_upscaled)
        draw_context.line([pv["eq4"], pv["eq1"]], fill=line_color, width=outline_width_upscaled)


    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        # self.clickable_polygons_params был установлен в _calculate_internal_geometry
        # Итерация в обратном порядке от отрисовки (сначала проверяем "верхние" грани)
        # или в порядке, как они есть, т.к. is_point_in_polygon не учитывает перекрытие.
        # Если точка внутри любого полигона, считаем попаданием.
        for face_data in self.clickable_polygons_params: # Или reversed(self.clickable_polygons_params)
            if geometry_utils.is_point_in_polygon(
                px=point_x_upscaled, 
                py=point_y_upscaled, 
                vertices=face_data["vertices"] # vertices - это vertices_2d
            ):
                return True
        return False