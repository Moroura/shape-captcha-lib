# shape_captcha_project/shape_captcha_lib/geometry_utils.py
from typing import List, Tuple, Dict, Any, Union 
import math # Добавлен для math.isclose в будущем, если понадобится

def is_point_in_circle(px: int, py: int, cx: int, cy: int, r: int) -> bool:
    if r <= 0: return False
    return (px - cx)**2 + (py - cy)**2 <= r**2

def is_point_in_rectangle(px: int, py: int, x1: int, y1: int, x2: int, y2: int) -> bool:
    # Эта функция полезна для axis-aligned bbox, но для повернутых фигур нужна is_point_in_polygon
    return min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2)

def is_point_in_ellipse(px: int, py: int, cx: int, cy: int, rx: int, ry: int) -> bool:
    if rx <= 0 or ry <= 0: return False
    norm_x = (px - cx) / rx
    norm_y = (py - cy) / ry
    return norm_x**2 + norm_y**2 <= 1.0

def is_point_in_polygon(px: int, py: int, vertices: List[Tuple[int, int]]) -> bool:
    """
    Определяет, находится ли точка (px, py) внутри полигона, заданного списком вершин.
    Использует алгоритм пересечения лучей (W. Randolph Franklin).
    https://wrf.ecse.rpi.edu/Research/Short_Notes/pnpoly.html
    """
    num_vertices = len(vertices)
    if num_vertices < 3:
        return False

    inside = False
    
    # p1x, p1y - координаты предыдущей вершины, начинаем с последней вершины полигона
    p1x, p1y = vertices[num_vertices - 1] 

    for i in range(num_vertices):
        p2x, p2y = vertices[i] # Текущая вершина

        # Условие, что ребро (p1, p2) пересекает горизонтальный луч, идущий из точки (px, py) вправо:
        # 1. Y-координата точки должна быть между Y-координатами вершин ребра (одна выше, другая ниже).
        #    ((p1y > py) != (p2y > py))
        # 2. X-координата точки должна быть меньше X-координаты пересечения луча с ребром.
        if ((p1y > py) != (p2y > py)) and \
           (px < (float(p2x - p1x) * (py - p1y)) / (p2y - p1y) + p1x):
            inside = not inside
        
        p1x, p1y = p2x, p2y # Переходим к следующему ребру

    return inside

def calculate_rotated_polygon_vertices(
    cx: int,
    cy: int,
    # Координаты вершин относительно центра (0,0) до поворота
    vertices_orig_centered: List[Tuple[float, float]],
    rotation_angle_rad: float
) -> List[Tuple[int, int]]:
    """
    Поворачивает набор вершин (которые изначально центрированы относительно (0,0))
    на заданный угол, а затем смещает их так, чтобы их новый центр был в (cx, cy).
    Возвращает целочисленные координаты вершин.
    """
    rotated_vertices: List[Tuple[int, int]] = []
    cos_angle = math.cos(rotation_angle_rad)
    sin_angle = math.sin(rotation_angle_rad)

    for vx_orig, vy_orig in vertices_orig_centered:
        # Поворот относительно (0,0)
        rvx = vx_orig * cos_angle - vy_orig * sin_angle
        rvy = vx_orig * sin_angle + vy_orig * cos_angle
        
        # Смещение к новому центру (cx, cy) и округление до целых чисел
        rotated_vertices.append((int(round(cx + rvx)), int(round(cy + rvy))))
    return rotated_vertices

def calculate_polygon_bounding_box(
    vertices: List[Tuple[int, int]]
) -> List[float]: # Возвращаем float для совместимости с ShapeDrawingDetails
    """
    Рассчитывает ограничивающий прямоугольник (bounding box) для полигона.
    Возвращает список [x_min, y_min, x_max, y_max].
    """
    if not vertices:
        return [0.0, 0.0, 0.0, 0.0]
    
    # Транспонирование списка кортежей в два списка координат
    # x_coords = [v[0] for v in vertices]
    # y_coords = [v[1] for v in vertices]
    # Более эффективный способ, если zip используется один раз:
    x_coords, y_coords = zip(*vertices)

    return [
        float(min(x_coords)),
        float(min(y_coords)),
        float(max(x_coords)),
        float(max(y_coords))
    ]

def calculate_regular_polygon_centered_vertices(
    radius: float, # Используем float для радиуса для большей точности внутренних расчетов
    num_vertices: int,
    # Начальный угол, чтобы первая вершина была "сверху" для стандартных полигонов
    start_angle_offset_rad: float = 0.0 
) -> List[Tuple[float, float]]:
    """
    Рассчитывает координаты вершин правильного многоугольника, центрированного в (0,0).
    Вершины возвращаются как float для последующего точного поворота.
    
    Args:
        radius: Радиус описанной окружности.
        num_vertices: Количество вершин.
        start_angle_offset_rad: Смещение начального угла (в радианах) от стандартного верхнего положения.
                                По умолчанию 0 (вершина сверху). -math.pi / 2 для вершины справа.
    Returns:
        Список кортежей (x, y) с float координатами вершин относительно (0,0).
    """
    vertices: List[Tuple[float, float]] = []
    angle_step = 2 * math.pi / num_vertices
    # Стандартный начальный угол для вершины "сверху" (-pi/2 или 3pi/2)
    initial_angle_rad = -math.pi / 2 + start_angle_offset_rad

    for i in range(num_vertices):
        angle = initial_angle_rad + i * angle_step
        vx = radius * math.cos(angle)
        vy = radius * math.sin(angle)
        vertices.append((vx, vy))
    return vertices

def calculate_star_centered_vertices(
    outer_radius: float,
    inner_radius: float,
    num_points: int,
    # Начальный угол, чтобы один из лучей звезды был направлен "вверх"
    start_angle_offset_rad: float = 0.0 
) -> List[Tuple[float, float]]:
    """
    Рассчитывает координаты вершин звезды, центрированной в (0,0).
    Вершины возвращаются как float для последующего точного поворота.

    Args:
        outer_radius: Внешний радиус (до вершин лучей).
        inner_radius: Внутренний радиус (до впадин между лучами).
        num_points: Количество лучей у звезды.
        start_angle_offset_rad: Смещение начального угла. По умолчанию 0 (луч вверх).
    Returns:
        Список кортежей (x, y) с float координатами вершин относительно (0,0).
    """
    vertices: List[Tuple[float, float]] = []
    angle_increment = math.pi / num_points # Угол до следующей точки (вершина или впадина)
    # Начальный угол для первой внешней вершины (обычно "вверх")
    initial_angle_rad = -math.pi / 2 + start_angle_offset_rad

    for i in range(num_points * 2): # Всего num_points * 2 вершин
        current_radius = outer_radius if i % 2 == 0 else inner_radius
        angle = initial_angle_rad + i * angle_increment

        vx = current_radius * math.cos(angle)
        vy = current_radius * math.sin(angle)
        vertices.append((vx, vy))
    return vertices
# Можно также добавить сюда _calculate_star_vertices, если планируем звезду как правильный полигон
# или оставить ее специфичной для класса звезды. Пока не добавляем.
