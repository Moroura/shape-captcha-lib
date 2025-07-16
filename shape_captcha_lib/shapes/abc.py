# shape_captcha_lib/shapes/abc.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Union, Type, Optional # Добавлен Optional
from PIL import ImageDraw
from pydantic import BaseModel, Field

class ShapeDrawingDetails(BaseModel):
    shape_type: str = Field(..., description="Тип фигуры, например, 'circle' или 'cube'")
    color_name_or_rgb: Union[str, Tuple[int, int, int]] = Field(..., description="Имя цвета или RGB кортеж")
    params_for_storage: Dict[str, Any] = Field(..., description="Отмасштабированные параметры фигуры для сохранения в хранилище")
    bbox_upscaled: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Отмасштабированный Bounding Box [x_min, y_min, x_max, y_max]"
    )

class AbstractShape(ABC):
    @staticmethod
    @abstractmethod
    def get_shape_type() -> str:
        pass

    @staticmethod
    @abstractmethod
    def generate_size_params(
        image_width_upscaled: int,      # Для контекста, может не использоваться всеми фигурами напрямую
        image_height_upscaled: int,     # Для контекста
        min_primary_size_upscaled: int, # Минимальный основной размер (например, радиус, сторона) для фигуры
        max_primary_size_upscaled: int, # Максимальный основной размер
        min_secondary_size_upscaled: Optional[int] = None, # Опциональный минимальный вторичный размер
        max_secondary_size_upscaled: Optional[int] = None, # Опциональный максимальный вторичный размер
        model_specific_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует параметры размера для фигуры (например, {'radius': 50}).
        Размеры должны быть в отмасштабированных (upscaled) значениях.
        """
        pass

    @abstractmethod
    def __init__(
        self,
        cx_upscaled: int,
        cy_upscaled: int,
        color_name_or_rgb: Union[str, Tuple[int, int, int]],
        rotation_angle_rad: float = 0.0,
        **specific_size_params_upscaled: Any
    ):
        self.cx_upscaled = cx_upscaled
        self.cy_upscaled = cy_upscaled
        self.color_name_or_rgb = color_name_or_rgb
        self.rotation_angle_rad = rotation_angle_rad

    @abstractmethod
    def get_draw_details(self) -> ShapeDrawingDetails:
        pass

    @abstractmethod
    def draw(
        self,
        draw_context: ImageDraw.ImageDraw,
        fill_color_rgb_actual: Tuple[int, int, int],
        outline_width_upscaled: int,
        brightness_factor_for_outline: Optional[float] = None,
        background_color_rgb_actual: Optional[Tuple[int, int, int]] = None
    ):
        pass

    @abstractmethod
    def is_point_inside(self, point_x_upscaled: int, point_y_upscaled: int) -> bool:
        pass