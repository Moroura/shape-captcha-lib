# shape_captcha_lib/registry.py
import importlib
import inspect
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Type

from .shapes.abc import AbstractShape #

logger = logging.getLogger(__name__)

MODEL_REGISTRIES: Dict[str, Dict[str, Type[AbstractShape]]] = {}
MODEL_COLORS: Dict[str, List[Union[str, Tuple[int, int, int]]]] = {}

AVAILABLE_COLORS_GENERAL: List[Union[str, Tuple[int, int, int]]] = [
    "red", "blue", "green", "#FFBF00", (128, 0, 128), "orange", "grey",
    "deepskyblue", "magenta", "lime", (255, 105, 180), (0, 128, 128),
    (165, 42, 42), (210, 105, 30), (128, 128, 0), (70, 130, 180),
    (60, 179, 113), (255, 192, 203), (255, 160, 122), (173, 216, 230)
]

def discover_shapes(
    base_package_name: str = "shape_captcha_lib",
    shapes_root_module_name: str = "shapes"
):
    global MODEL_REGISTRIES, MODEL_COLORS
    MODEL_REGISTRIES.clear()
    MODEL_COLORS.clear()

    try:
        package_spec = importlib.util.find_spec(base_package_name)
        if package_spec is None or package_spec.origin is None:
            logger.error(f"Could not find package spec for '{base_package_name}'.")
            return

        package_root_dir = Path(package_spec.origin).parent
        shapes_scan_dir = package_root_dir / shapes_root_module_name

        if not shapes_scan_dir.is_dir():
            logger.warning(f"Shapes root directory '{shapes_scan_dir}' not found.")
            return

        logger.info(f"Starting shape discovery in: {shapes_scan_dir}")

        for model_dir in shapes_scan_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith("_") and model_dir.name != "abc":
                model_name = model_dir.name
                logger.debug(f"Scanning model directory: '{model_name}'")

                if model_name not in MODEL_REGISTRIES:
                    MODEL_REGISTRIES[model_name] = {}

                # Загрузка цветов из _palette.py модели
                model_palette_file = model_dir / "_palette.py"
                if model_palette_file.exists():
                    palette_module_to_import = f"{base_package_name}.{shapes_root_module_name}.{model_name}._palette"
                    try:
                        palette_module = importlib.import_module(palette_module_to_import)
                        if hasattr(palette_module, "AVAILABLE_COLORS"):
                            colors = getattr(palette_module, "AVAILABLE_COLORS")
                            if isinstance(colors, list):
                                MODEL_COLORS[model_name] = colors
                                logger.info(f"Loaded {len(colors)} specific colors for model '{model_name}' from _palette.py.")
                            else:
                                logger.warning(f"AVAILABLE_COLORS in {palette_module_to_import} is not a list. Using general palette for '{model_name}'.")
                        else:
                            logger.debug(f"No AVAILABLE_COLORS attribute in {palette_module_to_import} for model '{model_name}'.")
                    except Exception as e_palette:
                        logger.warning(f"Could not load AVAILABLE_COLORS from {palette_module_to_import} for model '{model_name}': {e_palette}")
                else:
                    logger.debug(f"No _palette.py found for model '{model_name}'. Will use general palette if needed.")

                # Обнаружение классов фигур (существующий код)
                for shape_file in model_dir.glob("*.py"):
                    if shape_file.name.startswith("_"): # Пропускаем __init__.py, _palette.py и другие служебные
                        continue
                    # ... (остальной код обнаружения и регистрации классов фигур без изменений) ...
                    module_stem = shape_file.stem
                    module_to_import = f"{base_package_name}.{shapes_root_module_name}.{model_name}.{module_stem}"
                    try:
                        module = importlib.import_module(module_to_import)
                        for member_name, member_obj in inspect.getmembers(module, inspect.isclass):
                            if member_obj is not AbstractShape and issubclass(member_obj, AbstractShape): #
                                shape_class: Type[AbstractShape] = member_obj
                                try:
                                    shape_type_name = shape_class.get_shape_type()
                                    if not shape_type_name or not isinstance(shape_type_name, str):
                                        logger.warning(
                                            f"Class {shape_class.__name__} in {module_to_import} "
                                            f"did not return a valid string from get_shape_type(). Skipping."
                                        )
                                        continue
                                    if shape_type_name in MODEL_REGISTRIES[model_name]:
                                        logger.warning(
                                            f"Shape type '{shape_type_name}' in model '{model_name}' "
                                            f"(from {MODEL_REGISTRIES[model_name][shape_type_name].__module__}) "
                                            f"is being overwritten by class {shape_class.__name__} "
                                            f"from {module_to_import}."
                                        )
                                    MODEL_REGISTRIES[model_name][shape_type_name] = shape_class
                                    logger.debug(
                                        f"Registered shape: model='{model_name}', type='{shape_type_name}', "
                                        f"class='{shape_class.__name__}' from {module_to_import}"
                                    )
                                except AttributeError:
                                    logger.warning(
                                        f"Class {shape_class.__name__} in {module_to_import} "
                                        f"does not have get_shape_type() or it failed. Skipping."
                                    )
                                except Exception as e_get_type:
                                    logger.error(
                                        f"Error calling get_shape_type() on {shape_class.__name__} in {module_to_import}: {e_get_type}"
                                    )
                    except ImportError:
                        logger.error(f"Failed to import module: {module_to_import}")
                    except Exception as e:
                        logger.error(f"Error processing file {shape_file} in model {model_name}: {e}", exc_info=False)

        num_models = len(MODEL_REGISTRIES)
        num_total_shapes = sum(len(shapes) for shapes in MODEL_REGISTRIES.values())
        logger.info(f"Shape discovery complete. Found {num_total_shapes} shape types across {num_models} models.")
        if num_models == 0:
            logger.warning("No CAPTCHA models or shapes were discovered. CAPTCHA generation might fail.")

    except Exception as e:
        logger.error(f"General error during shape discovery process: {e}", exc_info=True)


def get_model_colors(model_name: str) -> List[Union[str, Tuple[int, int, int]]]:
    return MODEL_COLORS.get(model_name, AVAILABLE_COLORS_GENERAL)

def get_shape_class(model_name: str, shape_type: str) -> Optional[Type[AbstractShape]]: #
    model = MODEL_REGISTRIES.get(model_name)
    if model:
        return model.get(shape_type)
    return None

def get_model_shape_types(model_name: str) -> List[str]:
    return list(MODEL_REGISTRIES.get(model_name, {}).keys())

def get_all_registered_models() -> List[str]:
    return list(MODEL_REGISTRIES.keys())