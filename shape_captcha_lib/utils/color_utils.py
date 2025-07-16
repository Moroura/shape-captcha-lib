# shape_captcha_lib/utils/color_utils.py
from PIL import ImageColor
from typing import Tuple, Union, Optional, List
import colorsys
import logging

logger = logging.getLogger(__name__)

def get_rgb_color(color_value: Union[str, Tuple[int, int, int], List[int]]) -> Optional[Tuple[int, int, int]]: # Добавлен List[int]
    try:
        if isinstance(color_value, str):
            return ImageColor.getrgb(color_value)
        # Проверяем, является ли это кортежем или списком из 3 чисел
        elif isinstance(color_value, (tuple, list)) and len(color_value) == 3: 
            if all(isinstance(c, int) and 0 <= c <= 255 for c in color_value):
                return tuple(color_value) # Всегда возвращаем кортеж для консистентности
        logger.warning(f"Invalid color format/value: {color_value}")
        return None
    except ValueError as e:
        logger.warning(f"Could not parse color '{color_value}': {e}")
        return None

def adjust_brightness(
    color_value: Union[str, Tuple[int, int, int]],
    factor: float,
    min_l_for_darken: float = 0.03, # Нижний порог светлоты при затемнении (если исходная > ~0.01)
    max_l_for_lighten: float = 0.97, # Верхний порог светлоты при осветлении (если исходная < ~0.99)
    # Параметры для более тонкой настройки насыщенности (из drawing_3d.py)
    saturation_original_threshold: float = 0.2, # Порог исходной насыщенности, выше которого применяем спец. логику
    saturation_change_l_threshold: float = 0.3, # Порог изменения светлоты для буста насыщенности
    saturation_low_s_threshold: float = 0.5,    # Порог текущей насыщенности, ниже которого применяем буст
    saturation_boost_amount: float = 0.2       # Величина увеличения насыщенности
) -> Tuple[int, int, int]:
    """
    Изменяет яркость (светлоту) цвета с более детальной настройкой насыщенности.
    """
    base_rgb = get_rgb_color(color_value)
    if base_rgb is None:
        logger.warning(f"Could not parse base_rgb for adjust_brightness from {color_value}, returning grey.")
        return (100, 100, 100) # Средне-серый, как было в drawing_3d

    r, g, b = [x / 255.0 for x in base_rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    original_l = l
    original_s = s

    l_adjusted = l * factor

    if factor < 1.0:  # Затемняем
        # Используем значения из drawing_3d для min_l_for_darken
        l_adjusted = max(min_l_for_darken if original_l > 0.01 else 0.0, l_adjusted) 
    elif factor > 1.0:  # Осветляем
        # Используем значения из drawing_3d для max_l_for_lighten
        l_adjusted = min(max_l_for_lighten if original_l < 0.99 else 1.0, l_adjusted)
    
    l_adjusted = max(0.0, min(1.0, l_adjusted))

    # Логика буста насыщенности из drawing_3d._adjust_brightness
    if (original_s > saturation_original_threshold) and \
       (((original_l < 0.3 and factor > 1.1) or \
         (original_l > 0.7 and factor < 0.9)) or \
        (abs(l_adjusted - original_l) > saturation_change_l_threshold and s < saturation_low_s_threshold)):
        s = min(1.0, original_s + saturation_boost_amount)
    
    r_new, g_new, b_new = colorsys.hls_to_rgb(h, l_adjusted, s)
    return (int(r_new * 255), int(g_new * 255), int(b_new * 255))


def get_contrasting_outline_color( # Эта функция для 2D контуров
    fill_color_val: Union[str, Tuple[int, int, int]],
    dark_factor: float = 0.4,
    light_factor: float = 1.7,
    lightness_threshold: float = 0.5,
    min_l_for_dark_outline: float = 0.05,
    max_l_for_light_outline: float = 0.95
) -> Tuple[int, int, int]:
    # (Эта функция остается как была для 2D фигур)
    base_rgb = get_rgb_color(fill_color_val)
    if base_rgb is None:
        return (0, 0, 0)
    r, g, b = [x / 255.0 for x in base_rgb]
    _, l, _ = colorsys.rgb_to_hls(r, g, b)
    if l > lightness_threshold:
        return adjust_brightness(base_rgb, dark_factor, min_l_for_darken=min_l_for_dark_outline)
    else:
        return adjust_brightness(base_rgb, light_factor, max_l_for_lighten=max_l_for_light_outline)

def get_contrasting_line_color( # Новая/обновленная функция для 3D линий (из drawing_3d.py)
    base_fill_color_val: Union[str, Tuple[int, int, int]],
    dark_factor: float = 0.25,
    light_factor: float = 2.0,
    lightness_threshold: float = 0.45,
    saturation_threshold_for_default: float = 0.15, # Порог насыщенности для выбора "дефолтных" линий
    default_dark_line: Tuple[int,int,int] = (40,40,40),
    default_light_line: Tuple[int,int,int] = (200,200,200)
) -> Tuple[int, int, int]:
    """
    Определяет контрастный цвет для линий (например, ребер 3D фигур).
    Адаптировано из drawing_3d.py.
    """
    base_rgb = get_rgb_color(base_fill_color_val)
    if base_rgb is None: return default_dark_line

    r_norm, g_norm, b_norm = [x / 255.0 for x in base_rgb]
    _, l_norm, s_norm = colorsys.rgb_to_hls(r_norm, g_norm, b_norm)
    
    # Специальная обработка для очень светлых/темных почти серых цветов (из drawing_3d)
    if l_norm > 0.9 and s_norm < saturation_threshold_for_default: return (80, 80, 80) 
    if l_norm < 0.1 and s_norm < saturation_threshold_for_default: return (170, 170, 170)
    
    if l_norm > lightness_threshold:
        # Для светлой заливки - темная линия
        return adjust_brightness(base_rgb, dark_factor, min_l_for_darken=0.02) 
    else:
        # Для темной заливки - светлая линия
        return adjust_brightness(base_rgb, light_factor, max_l_for_lighten=0.98)