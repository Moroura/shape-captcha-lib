# test_generator.py (в корне shape_captcha_project/)
import sys
import os
from typing import List

# Добавляем корневую директорию проекта в sys.path,
# чтобы можно было импортировать shape_captcha_lib как модуль,
# даже если библиотека не установлена через pip install -e .
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shape_captcha_lib.image_generator import generate_captcha_image
from shape_captcha_lib.registry import get_model_shape_types, get_model_colors

if __name__ == "__main__":
    # Получаем доступные фигуры и цвета из модели по умолчанию
    # Это делает тест более надежным, так как он не зависит от жестко заданных списков
    model_name = "base_model"
    shape_types = get_model_shape_types(model_name)
    available_colors = get_model_colors(model_name)

    captcha_image, shapes_info = generate_captcha_image(
        model_name=model_name,
        model_shape_types=shape_types,
        model_available_colors=available_colors
    )
    captcha_image.save("captcha_example.png")
    print(f"Generated CAPTCHA image 'captcha_example.png' with {len(shapes_info)} shapes.")
    # ... (возможно, вывод информации о фигурах)