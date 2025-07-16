# shape_captcha_lib/shapes/community_plugins/_palette.py
from typing import List, Union, Tuple

AVAILABLE_COLORS: List[Union[str, Tuple[int, int, int]]] = [
    "gold", "silver", "bronze", "skyblue", "salmon",
    (123, 104, 238), # MediumSlateBlue
    (60, 179, 113),  # MediumSeaGreen
    # ... добавьте еще уникальных цветов для плагинов ...
]