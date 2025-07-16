# shape_captcha_lib/challenge_service.py
import uuid
import json
import random
from typing import Dict, Any, List, Tuple, Optional, Union
import logging
import importlib 

import redis.asyncio as redis
from PIL.Image import Image as PILImage 

from .image_generator import (
    generate_captcha_image,
    DEFAULT_CAPTCHA_WIDTH,
    DEFAULT_CAPTCHA_HEIGHT,
    DEFAULT_UPSCALE_FACTOR,
    NUM_SHAPES_TO_DRAW
)
from .utils import geometry_utils 
from .registry import get_model_shape_types, get_shape_class 

logger = logging.getLogger(__name__)
DEFAULT_CAPTCHA_TTL_SECONDS = 300

class CaptchaChallengeService:
    def __init__(
        self,
        redis_client: redis.Redis,
        model_name: str = "base_model",
        captcha_ttl_seconds: int = DEFAULT_CAPTCHA_TTL_SECONDS,
        captcha_image_width: int = DEFAULT_CAPTCHA_WIDTH,
        captcha_image_height: int = DEFAULT_CAPTCHA_HEIGHT,
        captcha_upscale_factor: int = DEFAULT_UPSCALE_FACTOR,
        num_shapes_on_image: int = NUM_SHAPES_TO_DRAW
    ):
        self.redis_client = redis_client
        self.captcha_ttl = captcha_ttl_seconds
        self.image_width = captcha_image_width
        self.image_height = captcha_image_height
        self.upscale_factor = captcha_upscale_factor
        self.redis_key_prefix = "captcha_challenge:"
        self.model_name = model_name
        self.num_shapes_on_image_config = num_shapes_on_image

        self.current_model_shape_types: List[str] = get_model_shape_types(self.model_name)
        
        self.current_model_colors: List[Union[str, Tuple[int,int,int]]] = []
        try:
            model_drawing_module_name_part = None
            if self.model_name == "base_model":
                model_drawing_module_name_part = "drawing_2d"
            elif self.model_name == "td_model":
                 model_drawing_module_name_part = "drawing_3d"
            
            if model_drawing_module_name_part:
                model_module_full_path = f"shape_captcha_lib.models.{model_name}.{model_drawing_module_name_part}"
                try:
                    module_spec = importlib.util.find_spec(model_module_full_path)
                    if module_spec:
                        model_drawing_module = importlib.import_module(model_module_full_path)
                        if hasattr(model_drawing_module, "AVAILABLE_COLORS"):
                            self.current_model_colors = getattr(model_drawing_module, "AVAILABLE_COLORS")
                            logger.info(f"Loaded {len(self.current_model_colors)} specific colors for model '{self.model_name}' from {model_module_full_path}.")
                    else:
                        logger.info(f"No specific drawing module found at {model_module_full_path} for model-specific colors of model '{self.model_name}'.")
                except (ImportError, AttributeError, ModuleNotFoundError) as e_model_color:
                    logger.info(f"Could not load specific 'AVAILABLE_COLORS' for model '{self.model_name}' via {model_module_full_path} (Error: {e_model_color}).")
            else:
                logger.info(f"No specific drawing module name defined for model '{self.model_name}' to load custom colors.")
        
        except Exception as e_path_build:
             logger.warning(f"Error determining module path for model-specific colors for '{self.model_name}': {e_path_build}.")

        if not self.current_model_colors:
            from . import registry as local_registry_ref
            self.current_model_colors = local_registry_ref.AVAILABLE_COLORS_GENERAL
            logger.info(f"Using {len(self.current_model_colors)} general colors for model '{self.model_name}'.")

        if not self.current_model_shape_types:
             raise RuntimeError(
                 f"Failed to load shape types for CAPTCHA model '{self.model_name}'. "
                 "Make sure shapes are discovered and registered (e.g., via registry.discover_shapes() in package __init__).")
        if not self.current_model_colors:
             raise RuntimeError(f"Failed to load any available colors for CAPTCHA model '{self.model_name}'.")
        
        logger.info(f"CaptchaChallengeService initialized for model '{self.model_name}'. "
                    f"Found {len(self.current_model_shape_types)} shape types.")

    async def create_challenge(self) -> Tuple[PILImage, str, str]: # Порядок возврата изменен на image, id, prompt
        captcha_id = uuid.uuid4().hex
        
        if not self.current_model_shape_types:
            logger.error(f"No shape types available for model '{self.model_name}' to create a challenge.")
            # Возвращаем ошибку или "пустую" CAPTCHA, чтобы приложение могло это обработать
            # Для согласованности с сигнатурой типа, лучше вызвать исключение
            raise ValueError(f"No shape types available for model '{self.model_name}'.")

        actual_num_shapes_to_draw = min(self.num_shapes_on_image_config, len(self.current_model_shape_types))
        if actual_num_shapes_to_draw <= 0:
            logger.error(f"Cannot draw any shapes for model '{self.model_name}', "
                         f"num_shapes_on_image_config: {self.num_shapes_on_image_config}, "
                         f"available types: {len(self.current_model_shape_types)}.")
            raise ValueError("Not enough shape types in model for a valid challenge.")
        
        logger.info(f"For model '{self.model_name}', attempting to generate image with {actual_num_shapes_to_draw} shapes.")
        
        image_object, drawn_shapes_info_list = generate_captcha_image(
            model_name=self.model_name,
            model_shape_types=self.current_model_shape_types,
            model_available_colors=self.current_model_colors,
            final_width=self.image_width, 
            final_height=self.image_height,
            num_shapes=actual_num_shapes_to_draw, 
            upscale_factor=self.upscale_factor,
        )
        
        if not drawn_shapes_info_list:
            logger.error(f"Failed to generate any shapes for the CAPTCHA challenge with model '{self.model_name}'.")
            raise ValueError("Failed to generate shapes for the CAPTCHA challenge.")

        target_shape_dict = random.choice(drawn_shapes_info_list)
        target_shape_type = target_shape_dict["shape_type"]
        
        prompt_text = f"Пожалуйста, кликните на фигуру типа: {target_shape_type.replace('_', ' ')}" 
        
        redis_data = {"target_shape_type": target_shape_type, "all_drawn_shapes": drawn_shapes_info_list}
        
        try:
            await self.redis_client.set(f"{self.redis_key_prefix}{captcha_id}", json.dumps(redis_data), ex=self.captcha_ttl)
            logger.info(f"CAPTCHA challenge {captcha_id} (target: {target_shape_type}) stored in Redis.")
        except Exception as e:
            logger.error(f"Error saving CAPTCHA data to Redis for ID {captcha_id}: {e}", exc_info=True)
            raise ConnectionError(f"Could not save CAPTCHA challenge to Redis: {e}")
            
        # Изменен порядок возвращаемых значений в соответствии с одним из ваших ранних примеров в документации
        # (id, image, prompt) -> (image, id, prompt) или наоборот. 
        # Давайте вернем к (id, image, prompt) как было в тестах
        return captcha_id, image_object, prompt_text

    async def verify_solution(self, captcha_id: str, click_x: int, click_y: int) -> bool:
        key_to_check = f"{self.redis_key_prefix}{captcha_id}"
        stored_data_json = await self.redis_client.get(key_to_check)
        
        if not stored_data_json:
            logger.warning(f"CAPTCHA ID {captcha_id} not found/expired.")
            return False
        
        try:
            # Удаляем ключ сразу после получения, чтобы предотвратить повторное использование
            await self.redis_client.delete(key_to_check)
        except Exception as e:
            logger.error(f"Could not delete CAPTCHA key {key_to_check} from Redis: {e}", exc_info=True)
            # Не прерываем проверку, если удаление не удалось, но логируем

        try:
            challenge_data = json.loads(stored_data_json)
        except json.JSONDecodeError:
            logger.warning(f"JSON decode error for CAPTCHA ID {captcha_id}.")
            return False
        
        target_shape_type_from_challenge = challenge_data.get("target_shape_type")
        all_drawn_shapes_data: Optional[List[Dict[str, Any]]] = challenge_data.get("all_drawn_shapes")

        if not target_shape_type_from_challenge or not all_drawn_shapes_data:
            logger.warning(f"Invalid data structure in Redis for CAPTCHA {captcha_id}.")
            return False

        upscaled_click_x = click_x * self.upscale_factor
        upscaled_click_y = click_y * self.upscale_factor
        
        logger.info(f"Verifying CAPTCHA ID {captcha_id}: Click (orig): ({click_x},{click_y}) "
                    f"-> Upscaled: ({upscaled_click_x},{upscaled_click_y}). "
                    f"Target type from challenge: '{target_shape_type_from_challenge}'")

        clicked_correct_shape = False
        # Итерируем в обратном порядке, чтобы сначала проверять фигуры "сверху" (последние нарисованные)
        for shape_data_dict in reversed(all_drawn_shapes_data):
            shape_type_on_image = shape_data_dict.get("shape_type")
            params_from_storage = shape_data_dict.get("params_for_storage")
            color_from_storage = shape_data_dict.get("color_name_or_rgb")

            if not shape_type_on_image or not params_from_storage or color_from_storage is None:
                logger.warning(f"Skipping shape with missing data in verify_solution: {shape_data_dict}")
                continue
            
            hit_this_shape = False
            try:
                ShapeClass = get_shape_class(self.model_name, shape_type_on_image)
                if ShapeClass:
                    logger.debug(f"Using ShapeClass '{ShapeClass.__name__}' for verification of type '{shape_type_on_image}'.")
                    try: 
                        # Общие аргументы для __init__ большинства фигур
                        init_args_common = {
                            "color_name_or_rgb": color_from_storage,
                            "rotation_angle_rad": params_from_storage.get("rotation_rad", 0.0)
                            # cx_upscaled и cy_upscaled будут добавлены ниже
                        }
                        specific_size_params = {} 
                        params_are_valid = True # Инициализируем флаг для каждой фигуры

                        # 1. Обработка фигур со специфичными именами ключей для координат центра
                        if shape_type_on_image == "cylinder":
                            init_args_common["cx_upscaled"] = params_from_storage.get("cx_top")
                            init_args_common["cy_upscaled"] = params_from_storage.get("cy_top")
                            if not (isinstance(init_args_common["cx_upscaled"], (int, float)) and isinstance(init_args_common["cy_upscaled"], (int, float))):
                                logger.warning(f"Missing 'cx_top' or 'cy_top' for cylinder {shape_data_dict}.")
                                params_are_valid = False
                            if params_are_valid:
                                required_keys = ["radius", "height", "perspective_factor_ellipse"]
                                if all(k in params_from_storage for k in required_keys):
                                    for k in required_keys: specific_size_params[k] = params_from_storage[k]
                                    opt_keys = ["top_brightness_factor", "side_gradient_start_factor", "side_gradient_end_factor"]
                                    for k_opt in opt_keys:
                                        if k_opt in params_from_storage: specific_size_params[k_opt] = params_from_storage[k_opt]
                                else: params_are_valid = False; logger.warning(f"Missing dimensions for cylinder {shape_data_dict}.")
                        
                        elif shape_type_on_image == "cone":
                            init_args_common["cx_upscaled"] = params_from_storage.get("cx_base")
                            init_args_common["cy_upscaled"] = params_from_storage.get("cy_base")
                            if not (isinstance(init_args_common["cx_upscaled"], (int, float)) and isinstance(init_args_common["cy_upscaled"], (int, float))):
                                logger.warning(f"Missing 'cx_base' or 'cy_base' for cone {shape_data_dict}.")
                                params_are_valid = False
                            if params_are_valid:
                                required_keys = ["base_radius", "height", "perspective_factor_base"]
                                if all(k in params_from_storage for k in required_keys):
                                    for k in required_keys: specific_size_params[k] = params_from_storage[k]
                                    opt_keys = ["side_gradient_start_factor", "side_gradient_end_factor"]
                                    for k_opt in opt_keys:
                                        if k_opt in params_from_storage: specific_size_params[k_opt] = params_from_storage[k_opt]
                                else: params_are_valid = False; logger.warning(f"Missing dimensions for cone {shape_data_dict}.")

                        elif shape_type_on_image == "pyramid":
                            init_args_common["cx_upscaled"] = params_from_storage.get("cx_base")
                            init_args_common["cy_upscaled"] = params_from_storage.get("cy_base")
                            if not (isinstance(init_args_common["cx_upscaled"], (int, float)) and isinstance(init_args_common["cy_upscaled"], (int, float))):
                                logger.warning(f"Missing 'cx_base' or 'cy_base' for pyramid {shape_data_dict}.")
                                params_are_valid = False
                            if params_are_valid: 
                                required_keys = ["base_side", "height", "depth_factor_base"]
                                if all(k in params_from_storage for k in required_keys):
                                    for k in required_keys: specific_size_params[k] = params_from_storage[k]
                                    opt_keys = ["face_brightness_factors", "base_brightness_factor"]
                                    for k_opt in opt_keys:
                                        if k_opt in params_from_storage: specific_size_params[k_opt] = params_from_storage[k_opt]
                                else:
                                    logger.warning(f"Missing one of {required_keys} for pyramid {shape_data_dict}.")
                                    params_are_valid = False
                        
                        # 2. Фигуры, использующие стандартные 'cx', 'cy'
                        else: 
                            init_args_common["cx_upscaled"] = params_from_storage.get("cx")
                            init_args_common["cy_upscaled"] = params_from_storage.get("cy")
                            if not (isinstance(init_args_common["cx_upscaled"], (int, float)) and isinstance(init_args_common["cy_upscaled"], (int, float))):
                                logger.warning(f"Missing 'cx' or 'cy' for {shape_type_on_image} {shape_data_dict}.")
                                params_are_valid = False
                            
                            if params_are_valid: # Только если общие cx/cy в порядке
                                if shape_type_on_image == "circle" or shape_type_on_image == "sphere":
                                    if "r" in params_from_storage: specific_size_params["radius"] = params_from_storage["r"]
                                    else: params_are_valid = False; logger.warning(f"Missing 'r' for {shape_type_on_image} {shape_data_dict}.")
                                elif shape_type_on_image == "square":
                                    if "side" in params_from_storage: specific_size_params["side"] = params_from_storage["side"]
                                    else: params_are_valid = False; logger.warning(f"Missing 'side' for square {shape_data_dict}.")
                                elif shape_type_on_image == "rectangle": 
                                    if "width" in params_from_storage and "height" in params_from_storage:
                                        specific_size_params["width"] = params_from_storage["width"]
                                        specific_size_params["height"] = params_from_storage["height"]
                                    else: params_are_valid = False; logger.warning(f"Missing 'width' or 'height' for rectangle {shape_data_dict}.")
                                elif shape_type_on_image == "equilateral_triangle":
                                    if "side_length" in params_from_storage: specific_size_params["side_length"] = params_from_storage["side_length"]
                                    else: params_are_valid = False; logger.warning(f"Missing 'side_length' for equilateral_triangle {shape_data_dict}.")
                                elif shape_type_on_image == "pentagon" or shape_type_on_image == "hexagon":
                                    if "radius" in params_from_storage: specific_size_params["radius"] = params_from_storage["radius"]
                                    else: params_are_valid = False; logger.warning(f"Missing 'radius' for {shape_type_on_image} {shape_data_dict}.")
                                elif shape_type_on_image == "star5":
                                    if "outer_radius" in params_from_storage and "inner_radius" in params_from_storage:
                                        specific_size_params["outer_radius"] = params_from_storage["outer_radius"]
                                        specific_size_params["inner_radius"] = params_from_storage["inner_radius"]
                                    else: params_are_valid = False; logger.warning(f"Missing radii for star5 {shape_data_dict}.")
                                elif shape_type_on_image == "rhombus":
                                    if "d1" in params_from_storage and "d2" in params_from_storage:
                                        specific_size_params["d1"] = params_from_storage["d1"]
                                        specific_size_params["d2"] = params_from_storage["d2"]
                                    else: params_are_valid = False; logger.warning(f"Missing d1/d2 for rhombus {shape_data_dict}.")
                                elif shape_type_on_image == "trapezoid":
                                    if "height" in params_from_storage and "bottom_width" in params_from_storage and "top_width" in params_from_storage:
                                        specific_size_params["height"] = params_from_storage["height"]
                                        specific_size_params["bottom_width"] = params_from_storage["bottom_width"]
                                        specific_size_params["top_width"] = params_from_storage["top_width"]
                                    else: params_are_valid = False; logger.warning(f"Missing dimensions for trapezoid {shape_data_dict}.")
                                elif shape_type_on_image == "cross":
                                    if "size" in params_from_storage and "thickness" in params_from_storage:
                                        specific_size_params["size"] = params_from_storage["size"]
                                        specific_size_params["thickness"] = params_from_storage["thickness"]
                                    else: params_are_valid = False; logger.warning(f"Missing size/thickness for cross {shape_data_dict}.")
                                elif shape_type_on_image == "cube": 
                                    if "side" in params_from_storage and "depth_factor" in params_from_storage:
                                        specific_size_params["side"] = params_from_storage["side"]
                                        specific_size_params["depth_factor"] = params_from_storage["depth_factor"]
                                        bf_keys = ["top_face_brightness_factor", "side_face_brightness_factor"]
                                        for k_bf in bf_keys:
                                            if k_bf in params_from_storage: specific_size_params[k_bf] = params_from_storage[k_bf]
                                    else: params_are_valid = False; logger.warning(f"Missing params for cube {shape_data_dict}.")
                                elif shape_type_on_image == "cuboid": # Добавлен Cuboid
                                    if "width" in params_from_storage and "height" in params_from_storage and "depth" in params_from_storage:
                                        specific_size_params["width"] = params_from_storage["width"]
                                        specific_size_params["height"] = params_from_storage["height"]
                                        specific_size_params["depth"] = params_from_storage["depth"]
                                        opt_keys = ["depth_factor_visual", "top_face_brightness_factor", "side_face_brightness_factor"]
                                        for k_opt in opt_keys:
                                            if k_opt in params_from_storage: specific_size_params[k_opt] = params_from_storage[k_opt]
                                    else: params_are_valid = False; logger.warning(f"Missing dimensions for cuboid {shape_data_dict}.")

                                elif shape_type_on_image == "octahedron":
                                    # cx_upscaled и cy_upscaled уже должны быть установлены в init_args_common
                                    # из params_from_storage.get("cx") и params_from_storage.get("cy")
                                    # в родительском блоке 'else'.
                                    # Проверяем наличие специфичных размеров.
                                    required_keys = ["size"] # Основной параметр для OctahedronShape
                                    if all(k in params_from_storage for k in required_keys):
                                        for k in required_keys:
                                            specific_size_params[k] = params_from_storage[k]
                                        # Опциональные параметры
                                        optional_keys = ["tilt_angle_rad", "perspective_factor_z", "brightness_factors"]
                                        for k_opt in optional_keys:
                                            if k_opt in params_from_storage:
                                                specific_size_params[k_opt] = params_from_storage[k_opt]
                                    else:
                                        logger.warning(f"Missing 'size' for octahedron {shape_data_dict}.")
                                        params_are_valid = False # Используйте имя вашего флага валидности

                                elif shape_type_on_image == "torus": # <--- ОБНОВЛЕННЫЙ БЛОК
                                    # cx_upscaled и cy_upscaled берутся из общих params_from_storage.get("cx"), .get("cy")
                                    # в родительском блоке 'else' (Torus использует стандартные cx/cy)
                                    if not (isinstance(init_args_common.get("cx_upscaled"), (int, float)) and \
                                            isinstance(init_args_common.get("cy_upscaled"), (int, float))):
                                        logger.warning(f"Missing 'cx' or 'cy' for torus {shape_data_dict}.")
                                        params_are_valid = False # Используйте имя вашего флага валидности
                                    if params_are_valid:
                                        # perspective_factor больше не нужен для __init__
                                        required_keys = ["outer_radius", "tube_radius"] 
                                        if all(k in params_from_storage for k in required_keys):
                                            for k in required_keys: specific_size_params[k] = params_from_storage[k]
                                            # Опциональные факторы яркости
                                            opt_keys = ["highlight_factor", "shadow_factor"] 
                                            for k_opt in opt_keys:
                                                if k_opt in params_from_storage: specific_size_params[k_opt] = params_from_storage[k_opt]
                                        else:
                                            logger.warning(f"Missing one of {required_keys} for torus {shape_data_dict}.")
                                            params_are_valid = False

                                elif shape_type_on_image == "cross_3d": # <--- НОВЫЙ БЛОК
                                    # cx_upscaled и cy_upscaled берутся из общих params_from_storage.get("cx"), .get("cy")
                                    # в родительском блоке 'else' (если cross_3d не требует особых имен для cx/cy)
                                    if not (isinstance(init_args_common.get("cx_upscaled"), (int, float)) and \
                                        isinstance(init_args_common.get("cy_upscaled"), (int, float))):
                                        logger.warning(f"Missing 'cx' or 'cy' for cross_3d {shape_data_dict}.")
                                        params_are_valid = False

                                    if params_are_valid:
                                        required_keys = ["arm_length", "arm_thickness", "depth_factor"]
                                        if all(k in params_from_storage for k in required_keys):
                                            for k in required_keys: specific_size_params[k] = params_from_storage[k]
                                            opt_keys = ["top_face_brightness_factor", "side_face_brightness_factor"]
                                            for k_opt in opt_keys:
                                                if k_opt in params_from_storage: specific_size_params[k_opt] = params_from_storage[k_opt]
                                        else:
                                            logger.warning(f"Missing one of {required_keys} for cross_3d {shape_data_dict}.")
                                            params_are_valid = False

                                elif shape_type_on_image == "star5_3d": # <--- НОВЫЙ БЛОК
                                    # cx_upscaled и cy_upscaled уже должны быть установлены из params_from_storage.get("cx") и .get("cy")
                                    if params_are_valid: # Проверяем, что cx/cy были успешно извлечены ранее
                                        required_keys = ["outer_radius", "inner_radius", "depth_factor"]
                                        if all(k in params_from_storage for k in required_keys):
                                            for k in required_keys: specific_size_params[k] = params_from_storage[k]
                                            opt_keys = ["top_face_brightness_factor", "side_face_brightness_factor"]
                                            for k_opt in opt_keys:
                                                if k_opt in params_from_storage: specific_size_params[k_opt] = params_from_storage[k_opt]
                                        else:
                                            logger.warning(f"Missing one of {required_keys} for star5_3d {shape_data_dict}.")
                                            params_are_valid = False

                                # TODO: Добавьте сюда elif для других реализованных классов td_model
                                else: 
                                    logger.warning(f"ShapeClass '{ShapeClass.__name__}' type '{shape_type_on_image}' (uses std cx/cy) "
                                                   "has no specific size param extraction logic in verify_solution.")
                                    params_are_valid = False 
                        
                        if not params_are_valid:
                            logger.info(f"Skipping shape {shape_type_on_image} due to missing/invalid parameters after specific handling.")
                            continue 
                        
                        final_init_args = {**init_args_common, **specific_size_params}
                        
                        shape_instance = ShapeClass(**final_init_args)
                        hit_this_shape = shape_instance.is_point_inside(upscaled_click_x, upscaled_click_y)
                    
                    except KeyError as e_key:
                        logger.error(f"KeyError during shape re-instantiation for {shape_type_on_image}: {e_key}. Params: {params_from_storage}", exc_info=True)
                    except TypeError as e_type:
                         logger.error(f"TypeError during shape re-instantiation for {shape_type_on_image}: {e_type}. Args: {final_init_args if 'final_init_args' in locals() else init_args_common if 'init_args_common' in locals() else 'unknown'}", exc_info=True)
                    except Exception as e_inst:
                        logger.error(f"Failed to re-instantiate or check shape {shape_type_on_image}: {e_inst}", exc_info=True)
                
                # --- Старая логика для фигур, которые ЕЩЕ не классы, или если ShapeClass не был найден ---
                elif shape_type_on_image == "sphere" and not ShapeClass: # Это условие теперь маловероятно, т.к. Sphere - класс
                    if all(k in params_from_storage for k in ["cx", "cy", "r"]):
                        if geometry_utils.is_point_in_circle(upscaled_click_x, upscaled_click_y, params_from_storage["cx"], params_from_storage["cy"], params_from_storage["r"]):
                            hit_this_shape = True
                elif shape_type_on_image == "ellipse" and not ShapeClass: # Если эллипс будет фигурой, но еще не класс
                     if all(k in params_from_storage for k in ["cx", "cy", "rx", "ry"]):
                        if geometry_utils.is_point_in_ellipse(upscaled_click_x, upscaled_click_y, params_from_storage["cx"], params_from_storage["cy"], params_from_storage["rx"], params_from_storage["ry"]):
                             hit_this_shape = True
                # Эта логика для старых 3D фигур, у которых params_from_storage["clickable_polygons"]
                # или params_from_storage["vertices"] могли быть напрямую.
                # По мере перевода 3D фигур в классы, эта fallback-логика будет все менее актуальной.
                elif "clickable_polygons" in params_from_storage and not ShapeClass: 
                    for polygon_face in params_from_storage.get("clickable_polygons", []):
                        if "vertices" in polygon_face and geometry_utils.is_point_in_polygon(upscaled_click_x, upscaled_click_y, polygon_face["vertices"]):
                            hit_this_shape = True; break
                elif "vertices" in params_from_storage and not ShapeClass: 
                    if geometry_utils.is_point_in_polygon(upscaled_click_x, upscaled_click_y, params_from_storage["vertices"]):
                        hit_this_shape = True
                else:
                    if not ShapeClass: # Только если класс не был найден ВООБЩЕ
                        logger.warning(f"Verify: No ShapeClass and no fallback logic for shape type '{shape_type_on_image}'.")

            except Exception as e_outer:
                logger.error(f"Unexpected error during geometric check logic for {shape_type_on_image}: {e_outer}", exc_info=True)
            
            if hit_this_shape:
                logger.debug(f"  Click HIT shape of type '{shape_type_on_image}' (Target was '{target_shape_type_from_challenge}').")
                if shape_type_on_image == target_shape_type_from_challenge:
                    clicked_correct_shape = True
                    logger.info(f"    This was the CORRECT target shape type for CAPTCHA {captcha_id}.")
                else:
                    logger.info(f"    This was NOT the target shape type for CAPTCHA {captcha_id} (hit '{shape_type_on_image}', expected '{target_shape_type_from_challenge}').")
                break
        
        if not hit_this_shape and not clicked_correct_shape:
            logger.info(f"  Click for CAPTCHA {captcha_id} DID NOT HIT any shape geometry for which verification logic exists or passed.")

        if clicked_correct_shape:
            logger.info(f"CAPTCHA ID {captcha_id}: Verification SUCCESS.")
        else:
            logger.info(f"CAPTCHA ID {captcha_id}: Verification FAILED.")
            
        return clicked_correct_shape

 
 
