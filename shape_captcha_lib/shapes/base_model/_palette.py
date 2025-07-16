# shape_captcha_lib/shapes/base_model/_palette.py (или registry.py для AVAILABLE_COLORS_GENERAL)
from typing import List, Union, Tuple

AVAILABLE_COLORS: List[Union[str, Tuple[int, int, int]]] = [
    # Яркие и чистые цвета
    "red", "blue", "green", "magenta", "cyan", "yellow",
    "orange", "purple", "lime", "deepskyblue", "hotpink",
    
    # Пастельные и светлые оттенки
    (255, 182, 193),  # LightPink
    (255, 160, 122),  # LightSalmon
    (255, 218, 185),  # PeachPuff
    (173, 216, 230),  # LightBlue
    (152, 251, 152),  # PaleGreen
    (240, 230, 140),  # Khaki
    (221, 160, 221),  # Plum
    (127, 255, 212),  # Aquamarine
    (255, 127, 80),   # Coral
    (64, 224, 208),   # Turquoise
    (218, 112, 214),  # Orchid
    
    # Дополнительные варианты
    (255, 99, 71),   # Tomato
    (30, 144, 255),   # DodgerBlue
    (50, 205, 50),   # LimeGreen (ярче, чем 'lime')
    (255, 192, 203)   # Pink (повтор из старого списка, но хороший)
    # Можно добавить еще, если нужно, или использовать hex-коды
    # "#FFBF00", # Янтарный (был в вашем общем списке)
    # (0, 128, 128), # Teal (был в вашем общем списке) - может быть темноват, но контрастен
]