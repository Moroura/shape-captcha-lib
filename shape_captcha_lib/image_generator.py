# shape_captcha_lib/image_generator.py
from PIL import Image, ImageDraw, ImageFont
import random
import math
from typing import List, Dict, Any, Tuple, Union, Optional
import logging
import string
import os
# Импорты из вашего пакета
from . import registry # Для доступа к get_shape_class
from .shapes.abc import ShapeDrawingDetails # Для аннотации возвращаемого типа
from .utils import color_utils

logger = logging.getLogger(__name__)

DEFAULT_CAPTCHA_WIDTH = 400
DEFAULT_CAPTCHA_HEIGHT = 250
NUM_SHAPES_TO_DRAW = 10 # Целевое количество фигур
MIN_SHAPE_DISTANCE_FINAL = 1
DEFAULT_UPSCALE_FACTOR = 3

TARGET_MIN_FINAL_SHAPE_DIM = 30 # Минимальный "основной" размер фигуры на финальном изображении
TARGET_MAX_FINAL_SHAPE_DIM = 50 # Максимальный "основной" размер

MAX_PLACEMENT_ATTEMPTS_PER_SHAPE = 300
MAX_SIZE_REDUCTION_ATTEMPTS = 4

LIGHT_BACKGROUND_COLORS: List[Union[str, Tuple[int, int, int]]] = [
    (248, 249, 250), (250, 250, 250), (240, 248, 255), (250, 250, 210),
    (240, 255, 240), (255, 250, 240), (248, 248, 255), (255, 240, 245),
    (230, 230, 250), (253, 245, 230), "white"
]

# --- Новые константы для водяных знаков/шума (можно сделать параметрами) ---
MODULE_DIR_FOR_FONT = os.path.dirname(os.path.abspath(__file__)) # Путь к текущему файлу (image_generator.py)
DEFAULT_WATERMARK_FONT_SIZE_RATIO = 0.1 # Относительно высоты изображения
DEFAULT_WATERMARK_OPACITY = 60 # Из 255
DEFAULT_NOISE_LINE_OPACITY = 50
WATERMARK_CANDIDATE_CHARS = string.ascii_uppercase + string.digits
MODULE_DIR_WHERE_IMAGE_GENERATOR_IS = os.path.dirname(os.path.abspath(__file__)) 

def _get_default_font_path():
    bundled_font_name = "LiberationMono-Regular.ttf" # Или "DejaVuSans-Bold.ttf"
    
    # Путь к директории 'fonts' должен быть относительно директории 'shape_captcha_lib'
    # Если 'fonts' лежит прямо внутри 'shape_captcha_lib', то:
    # MODULE_DIR_WHERE_IMAGE_GENERATOR_IS это /.../shape_captcha_lib/
    # Тогда путь к шрифтам будет os.path.join(MODULE_DIR_WHERE_IMAGE_GENERATOR_IS, "fonts", bundled_font_name)
    
    # Если вы следовали предложению 'shape_captcha_lib/assets/fonts/':
    # bundled_font_path = os.path.join(MODULE_DIR_WHERE_IMAGE_GENERATOR_IS, "assets", "fonts", bundled_font_name)

    # Судя по выводу find, у вас директория fonts находится прямо в shape_captcha_lib:
    # /usr/local/lib/python3.12/site-packages/shape_captcha_lib/fonts/DejaVuSans-Bold.ttf
    # Значит, путь должен быть:
    bundled_font_path = os.path.join(MODULE_DIR_WHERE_IMAGE_GENERATOR_IS, "fonts", bundled_font_name)
    
    normalized_bundled_font_path = os.path.normpath(bundled_font_path)

    if os.path.exists(normalized_bundled_font_path):
        logger.info(f"Using bundled font: {normalized_bundled_font_path}")
        return normalized_bundled_font_path
    else:
        logger.warning(f"Bundled font '{bundled_font_name}' not found at calculated path: {normalized_bundled_font_path}. Attempting system fonts.")

    # Попытка найти другой забандленный шрифт, если первый не найден, на всякий случай
    # (например, если вы переключитесь на DejaVuSans-Bold.ttf)
    if bundled_font_name != "DejaVuSans-Bold.ttf": # Избегаем рекурсии, если это и есть второй шрифт
        bundled_font_name_alt = "DejaVuSans-Bold.ttf"
        bundled_font_path_alt = os.path.join(MODULE_DIR_WHERE_IMAGE_GENERATOR_IS, "fonts", bundled_font_name_alt)
        normalized_bundled_font_path_alt = os.path.normpath(bundled_font_path_alt)
        if os.path.exists(normalized_bundled_font_path_alt):
            logger.info(f"Using alternative bundled font: {normalized_bundled_font_path_alt}")
            return normalized_bundled_font_path_alt
        else:
            logger.warning(f"Alternative bundled font '{bundled_font_name_alt}' not found at: {normalized_bundled_font_path_alt}.")


    # ... (ваша логика поиска системных шрифтов остается)
    system_font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular", # У вас LiberationMono-Regular.ttf, но этот путь для LiberationSans-Bold
        # Для LiberationMono-Regular.ttf может быть другой путь в liberation2, если он там есть, 
        # или он может быть в liberation/LiberationMono-Regular.ttf
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf", 
        "C:/Windows/Fonts/Arial.ttf",
    ]
    for font_path in system_font_paths:
        if os.path.exists(font_path):
            logger.info(f"Using system font: {font_path}")
            return font_path
        
    logger.warning("No bundled or specific system font found. Watermarks may use a very basic default Pillow font or fail.")
    return None

DEFAULT_FONT_PATH = _get_default_font_path()

DEFAULT_FONT_PATH = _get_default_font_path()

def _check_overlap(bbox1: List[float], bbox2: List[float], min_distance: int) -> bool:
    # bbox теперь List[float] из ShapeDrawingDetails
    if not bbox1 or not bbox2 or len(bbox1) != 4 or len(bbox2) != 4:
        logger.warning(f"Invalid bbox provided to _check_overlap: bbox1={bbox1}, bbox2={bbox2}")
        return True
    b1_x1, b1_y1, b1_x2, b1_y2 = bbox1
    b2_x1, b2_y1, b2_x2, b2_y2 = bbox2
    return not (
        b1_x2 + min_distance < b2_x1 or b1_x1 - min_distance > b2_x2 or
        b1_y2 + min_distance < b2_y1 or b1_y1 - min_distance > b2_y2
    )

def generate_captcha_image(
    model_name: str, # Имя модели для получения классов фигур
    model_shape_types: List[str],
    model_available_colors: List[Union[str, Tuple[int, int, int]]],
    final_width: int = DEFAULT_CAPTCHA_WIDTH,
    final_height: int = DEFAULT_CAPTCHA_HEIGHT,
    num_shapes: int = NUM_SHAPES_TO_DRAW,
    min_distance_final: int = MIN_SHAPE_DISTANCE_FINAL,
    upscale_factor: int = DEFAULT_UPSCALE_FACTOR,
    target_min_final_shape_dim: int = TARGET_MIN_FINAL_SHAPE_DIM,
    target_max_final_shape_dim: int = TARGET_MAX_FINAL_SHAPE_DIM,
    # Опциональные параметры для передачи в draw методы фигур
    brightness_factor_for_outline: Optional[float] = 0.4,
    # --- Новые параметры для помех ---
    add_watermark_text: bool = False,
    watermark_text: Optional[str] = None,
    num_watermark_lines: int = 3,
    add_noise_lines: bool = False,
    num_noise_lines: int = 10,
    add_point_noise: bool = False,
    point_noise_density: float = 0.02
) -> Tuple[Image.Image, List[Dict[str, Any]]]: # Возвращаем список словарей (из model_dump())

    actual_num_shapes_to_draw = min(num_shapes, len(model_shape_types))
    if actual_num_shapes_to_draw <= 0:
        logger.error("Cannot draw any shapes: num_shapes is 0 or no model_shape_types provided.")
        # Возвращаем пустое изображение и пустой список, или вызываем исключение
        empty_img = Image.new("RGB", (final_width, final_height), "white")
        return empty_img, [] # Или raise ValueError(...)

    if not model_shape_types or len(model_shape_types) < actual_num_shapes_to_draw:
        logger.error(f"Not enough unique shape types provided by model '{model_name}' ({len(model_shape_types)}) for {actual_num_shapes_to_draw} shapes.")
        empty_img = Image.new("RGB", (final_width, final_height), "white")
        return empty_img, [] # Или raise ValueError(...)
    if not model_available_colors or len(model_available_colors) < actual_num_shapes_to_draw:
        logger.error(f"Not enough unique colors available ({len(model_available_colors)}) for {actual_num_shapes_to_draw} shapes.")
        empty_img = Image.new("RGB", (final_width, final_height), "white")
        return empty_img, [] # Или raise ValueError(...)

    upscaled_width = final_width * upscale_factor
    upscaled_height = final_height * upscale_factor
    scaled_min_distance = min_distance_final * upscale_factor
    outline_width_upscaled = max(1, 1 * upscale_factor)

    background_color_choice = random.choice(LIGHT_BACKGROUND_COLORS)
    actual_background_rgb = color_utils.get_rgb_color(background_color_choice)
    if actual_background_rgb is None: # На случай, если в LIGHT_BACKGROUND_COLORS ошибка
        actual_background_rgb = (255, 255, 255)
        
    image = Image.new("RGB", (upscaled_width, upscaled_height), color=actual_background_rgb)
    draw = ImageDraw.Draw(image)
    
    # Список для хранения информации о нарисованных фигурах (объекты ShapeDrawingDetails, конвертированные в dict)
    drawn_shapes_info_list: List[Dict[str, Any]] = []

    selected_shape_types = random.sample(model_shape_types, actual_num_shapes_to_draw)
    selected_colors = random.sample(model_available_colors, actual_num_shapes_to_draw)

    # Рассчитываем абсолютные размеры для передачи в generate_size_params
    min_primary_size_upscaled = target_min_final_shape_dim * upscale_factor
    max_primary_size_upscaled = target_max_final_shape_dim * upscale_factor
    
    # Для некоторых фигур может потребоваться вторичный размер, определим его аналогично
    # (например, для эллипса, прямоугольника)
    # Пока сделаем его немного меньше основного
    min_secondary_size_upscaled = int(min_primary_size_upscaled * 0.5)
    max_secondary_size_upscaled = int(max_primary_size_upscaled * 0.8)
    min_secondary_size_upscaled = max(1 * upscale_factor, min_secondary_size_upscaled)
    if max_secondary_size_upscaled <= min_secondary_size_upscaled:
        max_secondary_size_upscaled = min_secondary_size_upscaled + max(1*upscale_factor, int(min_primary_size_upscaled*0.1))


    logger.info(f"Attempting to place {actual_num_shapes_to_draw} shapes from model '{model_name}'. "
                f"Upscaled primary size range: {min_primary_size_upscaled}-{max_primary_size_upscaled}.")

    for i in range(actual_num_shapes_to_draw):
        shape_type = selected_shape_types[i]
        fill_color_selected = selected_colors[i] # Это может быть имя или RGB

        shape_class = registry.get_shape_class(model_name, shape_type)
        if not shape_class:
            logger.warning(f"Shape class for type '{shape_type}' in model '{model_name}' not found. Skipping.")
            continue

        current_shape_placed = False
        # Адаптация цикла уменьшения размера
        current_max_primary_size = max_primary_size_upscaled
        current_max_secondary_size = max_secondary_size_upscaled

        for size_reduction_attempt in range(MAX_SIZE_REDUCTION_ATTEMPTS):
            if current_shape_placed: break

            if size_reduction_attempt > 0:
                reduction_factor = 0.9
                current_max_primary_size = int(current_max_primary_size * reduction_factor)
                current_max_secondary_size = int(current_max_secondary_size * reduction_factor)
                
                if current_max_primary_size < min_primary_size_upscaled:
                    logger.debug(f"Shape {shape_type} reached min primary allowable size. Stopping size reduction.")
                    break
                current_max_secondary_size = max(min_secondary_size_upscaled, current_max_secondary_size)


            # Генерируем параметры размера через класс фигуры
            try:
                size_params = shape_class.generate_size_params(
                    image_width_upscaled=upscaled_width,
                    image_height_upscaled=upscaled_height,
                    min_primary_size_upscaled=min_primary_size_upscaled, # Передаем диапазон
                    max_primary_size_upscaled=current_max_primary_size, # Текущий максимум с учетом уменьшения
                    min_secondary_size_upscaled=min_secondary_size_upscaled,
                    max_secondary_size_upscaled=current_max_secondary_size,
                    model_specific_constraints=None # TODO: Передавать, если нужно
                )
            except Exception as e_size_param:
                logger.error(f"Error generating size params for {shape_type}: {e_size_param}", exc_info=True)
                continue # К следующей попытке уменьшения или к следующей фигуре

            placement_attempts_for_current_size = MAX_PLACEMENT_ATTEMPTS_PER_SHAPE // MAX_SIZE_REDUCTION_ATTEMPTS
            for placement_attempt in range(placement_attempts_for_current_size):
                # Устанавливаем rotation_rad.
                if shape_type in ["circle", "ellipse", "sphere", "cone", "cylinder", "pyramid", "octahedron", "torus"]: # <--- ДОБАВЛЕН "octahedron"
                    rotation_rad = 0.0 
                    # Для октаэдра также важен tilt_angle_rad,
                    # он генерируется в OctahedronShape.generate_size_params
                    # и передается в конструктор через **size_params.
                    # Если вы хотите полностью фиксированное положение октаэдра,
                    # то и tilt_angle_rad должен быть фиксированным (например, 0 или небольшое значение).
                    # Это можно обеспечить в OctahedronShape.generate_size_params,
                    # сделав возвращаемый им tilt_angle_rad неслучайным.
                elif shape_type in ["cube", "cuboid", "cross_3d", "star5_3d"]: 
                     rotation_rad = math.pi / random.choice([12, 16, 20, 24, 28, 32]) * random.choice([-1,1]) # Уменьшенные углы
                else: 
                    rotation_rad = random.uniform(0, 2 * math.pi)

                # Для получения bbox для проверки коллизий, создаем "пробный" экземпляр
                # или используем статический метод, если бы он был.
                # Создание экземпляра проще для начала.
                try:
                    preview_shape_instance = shape_class(
                        cx_upscaled=0, cy_upscaled=0, # Положение не важно для bbox относительно начала координат
                        color_name_or_rgb=fill_color_selected, # Цвет не важен для bbox
                        rotation_angle_rad=rotation_rad,
                        **size_params
                    )
                    preview_details = preview_shape_instance.get_draw_details()
                    bbox_at_origin = preview_details.bbox_upscaled # Это bbox относительно (0,0) фигуры
                except Exception as e_preview:
                    logger.error(f"Error creating preview instance or getting details for {shape_type}: {e_preview}", exc_info=True)
                    break # К следующей попытке уменьшения размера

                shape_w_upscaled = bbox_at_origin[2] - bbox_at_origin[0]
                shape_h_upscaled = bbox_at_origin[3] - bbox_at_origin[1]

                if shape_w_upscaled <= 0 or shape_h_upscaled <= 0:
                    logger.debug(f"Shape {shape_type} has zero or negative width/height from preview. Skipping placement attempt.")
                    continue

                # Определяем допустимые границы для центра фигуры (cx, cy)
                # cx_offset_from_origin = -bbox_at_origin[0] # Насколько bbox смещен от (0,0), если центр фигуры в (0,0)
                # cy_offset_from_origin = -bbox_at_origin[1]
                # min_cx = scaled_min_distance + cx_offset_from_origin
                # max_cx = upscaled_width - scaled_min_distance - (shape_w_upscaled - cx_offset_from_origin)
                # min_cy = scaled_min_distance + cy_offset_from_origin
                # max_cy = upscaled_height - scaled_min_distance - (shape_h_upscaled - cy_offset_from_origin)

                # Упрощенный расчет границ для центра, предполагая, что bbox_at_origin - это [xmin, ymin, xmax, ymax] для фигуры с центром в (0,0)
                # Тогда cx должен быть в [ -bbox_at_origin[0] + scaled_min_distance, upscaled_width - bbox_at_origin[2] - scaled_min_distance ]
                min_cx_for_shape = -bbox_at_origin[0] + scaled_min_distance
                max_cx_for_shape = upscaled_width - bbox_at_origin[2] - scaled_min_distance
                min_cy_for_shape = -bbox_at_origin[1] + scaled_min_distance
                max_cy_for_shape = upscaled_height - bbox_at_origin[3] - scaled_min_distance


                if min_cx_for_shape >= max_cx_for_shape or min_cy_for_shape >= max_cy_for_shape:
                    logger.debug(f"Shape {shape_type} (w:{shape_w_upscaled}, h:{shape_h_upscaled}) too large for canvas placement with current scaled_min_distance. "
                                 f"min_cx:{min_cx_for_shape}, max_cx:{max_cx_for_shape}. Size attempt {size_reduction_attempt + 1}.")
                    break # Прерываем попытки размещения для текущего размера, переходим к уменьшению

                target_cx_upscaled = random.randint(int(min_cx_for_shape), int(max_cx_for_shape))
                target_cy_upscaled = random.randint(int(min_cy_for_shape), int(max_cy_for_shape))
                
                # Рассчитываем bbox фигуры на холсте
                prospective_bbox_on_canvas = [
                    bbox_at_origin[0] + target_cx_upscaled, bbox_at_origin[1] + target_cy_upscaled,
                    bbox_at_origin[2] + target_cx_upscaled, bbox_at_origin[3] + target_cy_upscaled
                ]

                has_collision = False
                for placed_shape_dict in drawn_shapes_info_list:
                    if _check_overlap(prospective_bbox_on_canvas, placed_shape_dict["bbox_upscaled"], scaled_min_distance):
                        has_collision = True; break
                
                if not has_collision:
                    actual_fill_rgb = color_utils.get_rgb_color(fill_color_selected)
                    if actual_fill_rgb is None: actual_fill_rgb = (128, 128, 128) # Default

                    final_shape_instance = shape_class(
                        cx_upscaled=target_cx_upscaled,
                        cy_upscaled=target_cy_upscaled,
                        color_name_or_rgb=fill_color_selected,
                        rotation_angle_rad=rotation_rad,
                        **size_params
                    )
                    final_shape_instance.draw(
                        draw_context=draw,
                        fill_color_rgb_actual=actual_fill_rgb,
                        outline_width_upscaled=outline_width_upscaled,
                        brightness_factor_for_outline=brightness_factor_for_outline,
                        background_color_rgb_actual=actual_background_rgb
                    )
                    
                    # Сохраняем информацию о нарисованной фигуре
                    shape_details_for_storage = final_shape_instance.get_draw_details()
                    drawn_shapes_info_list.append(shape_details_for_storage.model_dump())
                    
                    current_shape_placed = True
                    logger.info(f"Placed {len(drawn_shapes_info_list)}/{actual_num_shapes_to_draw}: {shape_type} at ({target_cx_upscaled},{target_cy_upscaled})")
                    break # к следующей фигуре
            
            if current_shape_placed: break # из цикла уменьшения размера

        if not current_shape_placed:
            logger.warning(f"Could not place shape {shape_type} (color: {fill_color_selected}) after all attempts.")

    if len(drawn_shapes_info_list) < actual_num_shapes_to_draw and len(drawn_shapes_info_list) == 0 :
        logger.error(f"Failed to place any shapes for model '{model_name}'. Returning empty/default image.")
        # Можно вернуть здесь базовое изображение с текстом об ошибке или просто пустое
        # Для простоты, сейчас вернем то, что есть, даже если фигур 0
    elif len(drawn_shapes_info_list) < actual_num_shapes_to_draw:
        logger.warning(f"Placed only {len(drawn_shapes_info_list)}/{actual_num_shapes_to_draw} shapes for model '{model_name}'.")
    else:
        logger.info(f"Successfully placed all {len(drawn_shapes_info_list)} shapes for model '{model_name}'.")

    # === НАЧАЛО: Добавление шума и водяных знаков ===
    # Это делается ПОСЛЕ отрисовки основных фигур, но ДО финального resize

    if add_watermark_text:
        font_size = int(upscaled_height * DEFAULT_WATERMARK_FONT_SIZE_RATIO)
        try:
            # Если DEFAULT_FONT_PATH is None, ImageFont.truetype пытается загрузить шрифт по умолчанию.
            # Это может вызвать различные ошибки, если подходящий шрифт не найден в системе.
            if DEFAULT_FONT_PATH:
                font = ImageFont.truetype(DEFAULT_FONT_PATH, font_size)
            else:
                # Пытаемся загрузить шрифт по умолчанию Pillow, если наш путь None
                # Это должно либо сработать, либо вызвать ошибку, которую мы поймаем
                font = ImageFont.truetype(None, font_size) 
        except Exception as e_font: # Ловим более широкий спектр исключений
            logger.warning(
                f"Failed to load font (path: {DEFAULT_FONT_PATH}, size: {font_size}): {e_font}. "
                "Falling back to ImageFont.load_default()."
            )
            try:
                font = ImageFont.load_default() # Это очень базовый, не масштабируемый растровый шрифт
            except IOError as e_load_default:
                logger.error(f"Critical: ImageFont.load_default() also failed: {e_load_default}. Watermarks will be disabled.")
                # В этом крайнем случае, если даже load_default не сработал,
                # нужно либо не рисовать текст, либо перехватывать ошибку выше.
                # Для простоты, можно установить add_watermark_text = False здесь, если font не удалось загрузить.
                # Но лучше, чтобы image_generator всегда возвращал изображение, если это возможно.
                # Пока оставим так, что font будет базовым.
                # Если и это не сработает, ошибка возникнет при font.getbbox или draw.textsize
                # и будет перехвачена общим Exception в сервисе.
                # Для большей надежности, можно сделать так:
                # if add_watermark_text:
                #    try: ... font = ...
                #    except: font = None; logger.error(...)
                # if font and add_watermark_text: # тогда рисовать текст только если font есть
                pass # Позволим коду ниже работать с font = ImageFont.load_default()

        for _ in range(num_watermark_lines):
            text_to_draw = watermark_text
            if not text_to_draw: # Генерируем случайный текст, если не задан
                text_len = random.randint(6, 10)
                text_to_draw = ''.join(random.choices(WATERMARK_CANDIDATE_CHARS, k=text_len))
            
            # Получаем реальный цвет фона для определения контрастного цвета водяного знака
            # Или используем фиксированный серый цвет
            # base_wm_color = color_utils.get_contrasting_outline_color(actual_background_rgb, dark_factor=1.3, light_factor=0.7)
            base_wm_color_val = random.randint(100, 180) # Оттенки серого для водяного знака
            wm_color_rgb = (base_wm_color_val, base_wm_color_val, base_wm_color_val)
            
            # Добавляем альфа-канал для полупрозрачности
            wm_color_rgba = wm_color_rgb + (DEFAULT_WATERMARK_OPACITY,)

            # Создаем временное изображение для текста с альфа-каналом
            # чтобы можно было повернуть текст, а затем наложить его
            try:
                # Pillow < 10.0.0 ImageDraw.textbbox, >= 10.0.0 font.getbbox
                if hasattr(font, 'getbbox'):
                    text_bbox = font.getbbox(text_to_draw) # (left, top, right, bottom)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    text_offset_y = text_bbox[1] # Важно для корректного позиционирования
                else: # Fallback для старых версий Pillow
                    text_width, text_height = draw.textsize(text_to_draw, font=font) # type: ignore
                    text_offset_y = 0

            except Exception as e_textsize:
                logger.warning(f"Could not get text dimensions for watermark: {e_textsize}")
                text_width, text_height = font_size * len(text_to_draw) // 2, font_size
                text_offset_y = 0

            if text_width <= 0 or text_height <=0: continue

            text_img = Image.new('RGBA', (text_width, text_height), (0,0,0,0))
            text_draw = ImageDraw.Draw(text_img)
            text_draw.text((0, -text_offset_y), text_to_draw, font=font, fill=wm_color_rgba) # Рисуем на (0,0) временного изображения

            angle = random.randint(-25, 25)
            rotated_text_img = text_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
            
            pos_x = random.randint(0, max(0, upscaled_width - rotated_text_img.width))
            pos_y = random.randint(0, max(0, upscaled_height - rotated_text_img.height))
            
            image.paste(rotated_text_img, (pos_x, pos_y), rotated_text_img) # Наложение с учетом альфа-канала

    if add_noise_lines:
        for _ in range(num_noise_lines):
            x1, y1 = random.randint(0, upscaled_width), random.randint(0, upscaled_height)
            x2, y2 = random.randint(0, upscaled_width), random.randint(0, upscaled_height)
            
            # Цвет линий - можно сделать темнее/светлее фона или случайным
            line_base_color_val = random.randint(120, 200)
            line_color_rgb = (line_base_color_val, line_base_color_val, line_base_color_val)
            line_color_rgba = line_color_rgb + (DEFAULT_NOISE_LINE_OPACITY,)
            
            # Для рисования с альфа-каналом на RGB изображении, нужно создать временный слой
            overlay = Image.new('RGBA', image.size, (255,255,255,0)) # Прозрачный слой
            draw_overlay = ImageDraw.Draw(overlay)
            draw_overlay.line([(x1, y1), (x2, y2)], fill=line_color_rgba, width=int(1 * upscale_factor))
            image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
            # После каждой линии пересоздаем draw, если нужно рисовать дальше на image напрямую
            draw = ImageDraw.Draw(image)


    if add_point_noise and point_noise_density > 0:
        num_noise_pixels = int(upscaled_width * upscaled_height * point_noise_density)
        for _ in range(num_noise_pixels):
            x = random.randint(0, upscaled_width - 1)
            y = random.randint(0, upscaled_height - 1)
            # Шум может быть оттенками серого или цветным
            noise_val = random.randint(0, 255)
            noise_color = (noise_val, noise_val, noise_val) 
            # или случайный цвет:
            # noise_color = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
            image.putpixel((x, y), noise_color)
            
    # === КОНЕЦ: Добавление шума и водяных знаков ===

    final_image = image.resize((final_width, final_height), Image.Resampling.LANCZOS)
    return final_image, drawn_shapes_info_list