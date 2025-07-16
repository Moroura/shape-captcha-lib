# shape_captcha_lib/logic_core.py
import random
from typing import List, Tuple, Dict, Any, Union, Optional
import gettext
import os
import logging

from PIL.Image import Image as PILImage

from .image_generator import (
    generate_captcha_image,
    DEFAULT_CAPTCHA_WIDTH,
    DEFAULT_CAPTCHA_HEIGHT,
    DEFAULT_UPSCALE_FACTOR,
    NUM_SHAPES_TO_DRAW,
    TARGET_MIN_FINAL_SHAPE_DIM as DEFAULT_TARGET_MIN_FINAL_SHAPE_DIM,
    TARGET_MAX_FINAL_SHAPE_DIM as DEFAULT_TARGET_MAX_FINAL_SHAPE_DIM
)
from .registry import get_model_shape_types, get_shape_class, get_model_colors

logger = logging.getLogger(__name__)

# Путь к директории с переводами относительно текущего файла
# Это позволит библиотеке находить свои файлы локализации, когда она установлена
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOCALE_DIR = os.path.join(MODULE_DIR, 'locales')
DEFAULT_TRANSLATION_DOMAIN = 'shape_captcha_lib'


class CaptchaLogicCore:
    def __init__(
        self,
        model_name: str = "base_model",
        captcha_image_width: int = DEFAULT_CAPTCHA_WIDTH,
        captcha_image_height: int = DEFAULT_CAPTCHA_HEIGHT,
        captcha_upscale_factor: int = DEFAULT_UPSCALE_FACTOR,
        num_shapes_on_image: int = NUM_SHAPES_TO_DRAW,
        target_min_final_shape_dim: int = DEFAULT_TARGET_MIN_FINAL_SHAPE_DIM,
        target_max_final_shape_dim: int = DEFAULT_TARGET_MAX_FINAL_SHAPE_DIM,
        brightness_factor_for_outline: Optional[float] = 0.4,
        default_language: str = 'en',
        localedir: Optional[str] = DEFAULT_LOCALE_DIR,
        translation_domain: str = DEFAULT_TRANSLATION_DOMAIN,
        # --- Новые параметры для водяных знаков/шума ---
        add_watermark_text: bool = False, # Включить/выключить текстовые водяные знаки
        watermark_text: Optional[str] = None, # Текст для водяного знака (если None, можно генерировать случайный)
        num_watermark_lines: int = 3,    # Количество линий текста водяного знака
        add_noise_lines: bool = False,   # Включить/выключить шумовые линии
        num_noise_lines: int = 10,       # Количество шумовых линий
        add_point_noise: bool = False,   # Включить/выключить точечный шум
        point_noise_density: float = 0.02 # Плотность точечного шума (доля пикселей)
        # TODO: Продумать передачу model_specific_constraints для ShapeClass.generate_size_params, если необходимо

    ):
        self.model_name = model_name
        self.image_width = captcha_image_width
        self.image_height = captcha_image_height
        self.upscale_factor = captcha_upscale_factor
        self.num_shapes_on_image_config = num_shapes_on_image
        
        self.target_min_final_shape_dim = target_min_final_shape_dim
        self.target_max_final_shape_dim = target_max_final_shape_dim
        self.brightness_factor_for_outline = brightness_factor_for_outline
        
        self.default_language = default_language
        self.localedir = localedir
        self.translation_domain = translation_domain

        # --- Сохраняем новые параметры для помех---
        self.add_watermark_text = add_watermark_text
        self.watermark_text = watermark_text
        self.num_watermark_lines = num_watermark_lines
        self.add_noise_lines = add_noise_lines
        self.num_noise_lines = num_noise_lines
        self.add_point_noise = add_point_noise
        self.point_noise_density = point_noise_density

        self.current_model_shape_types: List[str] = get_model_shape_types(self.model_name)
        self.current_model_colors: List[Union[str, Tuple[int, int, int]]] = get_model_colors(self.model_name)

        if not self.current_model_shape_types:
            raise ValueError(
                f"CaptchaLogicCore: No shape types for model '{self.model_name}'."
            )
        if not self.current_model_colors:
            raise ValueError(
                f"CaptchaLogicCore: No colors for model '{self.model_name}'."
            )

        logger.info(
            f"CaptchaLogicCore initialized for model '{self.model_name}'. "
            f"Shapes: {len(self.current_model_shape_types)}, Colors: {len(self.current_model_colors)}."
        )

    def _get_translator(self, language_code: Optional[str] = None) -> gettext.GNUTranslations:
        lang_to_use = language_code or self.default_language
        translation = gettext.NullTranslations() # По умолчанию, если ничего не найдено
        try:
            if self.localedir and os.path.isdir(self.localedir): # Проверяем, существует ли директория
                translation = gettext.translation(
                    self.translation_domain,
                    localedir=self.localedir,
                    languages=[lang_to_use],
                    fallback=True # Если lang_to_use не найден, попытается использовать fallback (обычно 'en' или системный)
                                  # или вернет NullTranslations, если и fallback не найден
                )
            else:
                logger.warning(f"Locale directory '{self.localedir}' not found or not specified. Using NullTranslations.")
        except FileNotFoundError:
            logger.warning(
                f"Translations not found for language '{lang_to_use}' or default "
                f"in domain '{self.translation_domain}' at '{self.localedir}'. Using NullTranslations."
            )
        return translation

    def generate_challenge_data(
        self, 
        language_code: Optional[str] = None
    ) -> Tuple[PILImage, List[Dict[str, Any]], str, str]:
        # ... (логика генерации image_object, drawn_shapes_details_list, target_shape_type_key как раньше)
        actual_num_shapes = min(self.num_shapes_on_image_config, len(self.current_model_shape_types))
        if actual_num_shapes <= 0:
            logger.error(f"Cannot draw shapes for model '{self.model_name}', num_shapes: {actual_num_shapes}")
            raise ValueError("Not enough shape types or num_shapes_on_image_config is zero for CAPTCHA generation.")

        image_object, drawn_shapes_details_list = generate_captcha_image(
            model_name=self.model_name,
            model_shape_types=self.current_model_shape_types,
            model_available_colors=self.current_model_colors,
            final_width=self.image_width,
            final_height=self.image_height,
            num_shapes=actual_num_shapes,
            upscale_factor=self.upscale_factor,
            target_min_final_shape_dim=self.target_min_final_shape_dim,
            target_max_final_shape_dim=self.target_max_final_shape_dim,
            brightness_factor_for_outline=self.brightness_factor_for_outline,
            # --- Передаем новые параметры помех ---
            add_watermark_text=self.add_watermark_text,
            watermark_text=self.watermark_text,
            num_watermark_lines=self.num_watermark_lines,
            add_noise_lines=self.add_noise_lines,
            num_noise_lines=self.num_noise_lines,
            add_point_noise=self.add_point_noise,
            point_noise_density=self.point_noise_density
        )

        if not drawn_shapes_details_list:
            logger.error(f"generate_captcha_image returned no shapes for model '{self.model_name}'.")
            raise ValueError("Failed to generate shapes for the CAPTCHA challenge.")

        target_shape_dict = random.choice(drawn_shapes_details_list)
        target_shape_type_key = target_shape_dict["shape_type"]

        translator = self._get_translator(language_code)
        _ = translator.gettext

        # Ключ для перевода имени фигуры (например, "circle", "square", "cross_3d")
        # В .po файле это будет: msgid "circle" msgstr "круг"
        translated_shape_name = _(target_shape_type_key)
        if translated_shape_name == target_shape_type_key: # Если перевод не найден, форматируем ключ
            translated_shape_name = target_shape_type_key.replace('_', ' ')

        # Шаблон подсказки
        # В .po: msgid "Please click on a shape of type: %s"
        #         msgstr "Пожалуйста, кликните на фигуру типа: %s"
        prompt_template = _("Please click on a shape of type: %s")
        prompt_text = prompt_template % translated_shape_name
        
        return image_object, drawn_shapes_details_list, target_shape_type_key, prompt_text

    def verify_solution(
        self,
        click_x: int,
        click_y: int,
        target_shape_type_from_challenge: str,
        all_drawn_shapes_data: List[Dict[str, Any]]
    ) -> bool:
        # Этот метод не требует изменений для i18n, так как работает с ключами, а не отображаемыми именами
        upscaled_click_x = click_x * self.upscale_factor
        upscaled_click_y = click_y * self.upscale_factor

        logger.debug(
            f"Verifying click ({click_x},{click_y}) -> upscaled ({upscaled_click_x},{upscaled_click_y}). "
            f"Target: '{target_shape_type_from_challenge}', Model: '{self.model_name}'"
        )
        # ... (остальная логика verify_solution без изменений) ...
        clicked_correct_shape = False
        for shape_data_dict in reversed(all_drawn_shapes_data):
            shape_type_on_image = shape_data_dict.get("shape_type")
            params_from_storage = shape_data_dict.get("params_for_storage")
            color_from_storage = shape_data_dict.get("color_name_or_rgb")

            if not all([shape_type_on_image, params_from_storage, color_from_storage is not None]):
                logger.warning(f"Skipping shape with missing data in verify_solution: {shape_data_dict}")
                continue

            shape_class = get_shape_class(self.model_name, shape_type_on_image)
            if not shape_class:
                logger.warning(f"Shape class for type '{shape_type_on_image}' in model '{self.model_name}' not found. Skipping.")
                continue
            
            hit_this_shape = False
            try:
                shape_instance = shape_class(
                    color_name_or_rgb=color_from_storage,
                    **params_from_storage
                )
                hit_this_shape = shape_instance.is_point_inside(upscaled_click_x, upscaled_click_y)
            except Exception as e:
                logger.error(
                    f"Failed to re-instantiate or check shape {shape_type_on_image}: {e}. Params: {params_from_storage}",
                    exc_info=True
                )
                continue

            if hit_this_shape:
                logger.debug(f"  Click HIT shape of type '{shape_type_on_image}'.")
                if shape_type_on_image == target_shape_type_from_challenge:
                    clicked_correct_shape = True
                    logger.info("    This was the CORRECT target shape type.")
                else:
                    logger.info(
                        f"    This was NOT the target shape type (hit '{shape_type_on_image}', "
                        f"expected '{target_shape_type_from_challenge}')."
                    )
                break 
        
        if not clicked_correct_shape and not hit_this_shape :
            logger.info("  Click DID NOT HIT any identifiable shape geometry for which verification logic exists.")
            
        return clicked_correct_shape