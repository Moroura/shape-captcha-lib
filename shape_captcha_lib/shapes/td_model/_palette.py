# shape_captcha_lib/shapes/base_model/_palette.py (или registry.py для AVAILABLE_COLORS_GENERAL)
from typing import List, Union, Tuple

AVAILABLE_COLORS: List[Union[str, Tuple[int, int, int]]] = [
    # Яркие и чистые цвета
    "crimson", "royalblue", "forestgreen", "darkorchid", "gold",
    "orangered", "mediumspringgreen", "deepskyblue", "mediumvioletred",
    
    # Светлые и контрастные оттенки
    (255, 105, 97),   # Pastel Red
    (173, 216, 230),  # LightBlue (повтор, но хороший)
    (144, 238, 144),  # LightGreen
    (255, 179, 71),   # Mandy (пастельно-оранжевый)
    (204, 153, 255),  # Lavender (светло-фиолетовый)
    (244, 154, 194),  # Pink Sherbet
    (135, 206, 250),  # LightSkyBlue
    (255, 223, 186),  # NavajoWhite (для светлых граней)
    (60, 179, 113),   # MediumSeaGreen (повтор, но хороший)
    (255, 160, 122),   # LightSalmon (повтор)
    
    # Дополнительные варианты
    (255, 99, 71),   # Tomato
    (30, 144, 255),   # DodgerBlue
    (50, 205, 50),   # LimeGreen (ярче, чем 'lime')
    (255, 192, 203)   # Pink (повтор из старого списка, но хороший)
    # Можно добавить еще, если нужно, или использовать hex-коды
    # "#FFBF00", # Янтарный (был в вашем общем списке)
    # (0, 128, 128), # Teal (был в вашем общем списке) - может быть темноват, но контрастен
]