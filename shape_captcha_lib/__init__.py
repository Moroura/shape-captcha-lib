# shape_captcha_project/shape_captcha_lib/__init__.py

# Импортируем модули, чтобы их содержимое было доступно
# и чтобы выполнились необходимые инициализации.

from . import shapes # Важно для доступа к shapes.abc.AbstractShape из registry
from . import registry
from . import utils
from . import challenge_service # <--- ДОБАВИТЬ ИМПОРТ МОДУЛЯ С СЕРВИСОМ

# --- Вызов обнаружения фигур ---
registry.discover_shapes()

# Явно импортируем ключевые классы и функции, чтобы сделать их частью публичного API пакета
from .challenge_service import CaptchaChallengeService # <--- ДОБАВИТЬ ЭТУ СТРОКУ

# Сервисы async/sync будут добавлены позже, когда мы их создадим
# from .services.async_service import AsyncCaptchaChallengeService
# from .services.sync_service import SyncCaptchaChallengeService

from .image_generator import generate_captcha_image
from .registry import (
    get_shape_class,
    get_model_shape_types,
    get_all_registered_models,
    AVAILABLE_COLORS_GENERAL,
    discover_shapes # Экспортируем, если нужна возможность переинициализации извне
)
from .shapes.abc import AbstractShape, ShapeDrawingDetails

__version__ = "0.2.1" # Немного увеличим версию для этого изменения

# Определяем, что будет импортировано при 'from shape_captcha_lib import *'
# Также помогает инструментам статического анализа понимать публичный интерфейс
__all__ = [
    "CaptchaChallengeService",      # <--- ДОБАВИТЬ ЭТУ СТРОКУ
    # "AsyncCaptchaChallengeService", # Будут добавлены
    # "SyncCaptchaChallengeService",  # Будут добавлены
    "generate_captcha_image",
    "get_shape_class",
    "get_model_shape_types",
    "get_all_registered_models",
    "AVAILABLE_COLORS_GENERAL",
    "AbstractShape",
    "ShapeDrawingDetails",
    "discover_shapes",
]