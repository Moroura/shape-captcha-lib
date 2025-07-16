# test_generator.py (в корне shape_captcha_project/)
from shape_captcha_lib.image_generator import generate_captcha_image # <--- СТАРЫЙ ИМПОРТ
from typing import List
if __name__ == "__main__":
    captcha_image, shapes_info = generate_captcha_image()
    captcha_image.save("captcha_example.png")
    print(f"Generated CAPTCHA image 'captcha_example.png' with {len(shapes_info)} shapes.")
    # ... (возможно, вывод информации о фигурах)