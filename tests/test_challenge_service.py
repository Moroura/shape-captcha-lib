# tests/test_challenge_service.py
import pytest
import pytest_asyncio
import json
from unittest import mock
from PIL import Image
import redis.asyncio as redis # Для типизации мока
import uuid # Для генерации captcha_id в тестах
import math
from typing import List
from shape_captcha_lib import CaptchaChallengeService, registry
from shape_captcha_lib.image_generator import DEFAULT_CAPTCHA_WIDTH, DEFAULT_CAPTCHA_HEIGHT, DEFAULT_UPSCALE_FACTOR
from shape_captcha_lib.registry import AVAILABLE_COLORS_GENERAL

# ... (фикстура mock_redis_client и тест test_create_challenge_with_circle_shape остаются здесь) ...

# --- Новые тесты для verify_solution ---

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_circle(mock_redis_client):
    """
    Проверяет успешную верификацию при правильном клике на круг.
    """
    model_name = "base_model"
    shape_type = "circle"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR # Используем дефолтный из image_generator или сервиса

    # Параметры для нашего круга (уже отмасштабированные)
    circle_cx_upscaled = 200 * upscale_factor
    circle_cy_upscaled = 150 * upscale_factor
    circle_r_upscaled = 30 * upscale_factor
    selected_color = AVAILABLE_COLORS_GENERAL[0]

    # Данные, которые якобы хранятся в Redis
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [
            {
                "shape_type": shape_type,
                "color_name_or_rgb": selected_color,
                "params_for_storage": {
                    "cx": circle_cx_upscaled,
                    "cy": circle_cy_upscaled,
                    "r": circle_r_upscaled
                    # "rotation_rad": 0.0 # Для круга не критично, можно не хранить
                },
                "bbox_upscaled": [ # Рассчитывается как cx-r, cy-r, cx+r, cy+r
                    float(circle_cx_upscaled - circle_r_upscaled),
                    float(circle_cy_upscaled - circle_r_upscaled),
                    float(circle_cx_upscaled + circle_r_upscaled),
                    float(circle_cy_upscaled + circle_r_upscaled)
                ]
            }
        ]
    }
    # Мокируем redis_client.get, чтобы он вернул наши данные
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)

    service = CaptchaChallengeService(
        redis_client=mock_redis_client,
        model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )

    # Клик точно в центр круга (координаты не отмасштабированные)
    click_x = circle_cx_upscaled // upscale_factor
    click_y = circle_cy_upscaled // upscale_factor

    is_valid = await service.verify_solution(captcha_id, click_x, click_y)

    assert is_valid is True, "Верификация должна быть успешной при клике в центр круга"
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")


@pytest.mark.asyncio
async def test_verify_solution_incorrect_click_miss_circle(mock_redis_client):
    """
    Проверяет неудачную верификацию при клике мимо круга.
    """
    model_name = "base_model"
    shape_type = "circle"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    circle_cx_upscaled = 200 * upscale_factor
    circle_cy_upscaled = 150 * upscale_factor
    circle_r_upscaled = 30 * upscale_factor
    selected_color = AVAILABLE_COLORS_GENERAL[0]

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {"cx": circle_cx_upscaled, "cy": circle_cy_upscaled, "r": circle_r_upscaled},
            "bbox_upscaled": [float(c) for c in [circle_cx_upscaled - circle_r_upscaled, circle_cy_upscaled - circle_r_upscaled, 
                                                 circle_cx_upscaled + circle_r_upscaled, circle_cy_upscaled + circle_r_upscaled]]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)

    service = CaptchaChallengeService(
        redis_client=mock_redis_client,
        model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )

    # Клик далеко от круга (координаты не отмасштабированные)
    click_x = (circle_cx_upscaled + circle_r_upscaled + 10) // upscale_factor
    click_y = (circle_cy_upscaled + circle_r_upscaled + 10) // upscale_factor

    is_valid = await service.verify_solution(captcha_id, click_x, click_y)

    assert is_valid is False, "Верификация должна быть неуспешной при клике мимо круга"
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")


@pytest.mark.asyncio
async def test_verify_solution_captcha_id_not_found(mock_redis_client):
    """
    Проверяет случай, когда captcha_id не найден в Redis (или истек).
    """
    captcha_id = uuid.uuid4().hex
    # mock_redis_client.get уже настроен возвращать None по умолчанию в фикстуре,
    # но для явности можно сделать это здесь:
    mock_redis_client.get.return_value = None

    service = CaptchaChallengeService(redis_client=mock_redis_client)

    click_x, click_y = 10, 10 # Координаты клика не важны в этом тесте
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)

    assert is_valid is False, "Верификация должна быть неуспешной, если captcha_id не найден"
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    # Ключ не должен удаляться, если он не найден
    mock_redis_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_verify_solution_malformed_stored_data(mock_redis_client):
    """
    Проверяет случай с некорректными данными, сохраненными в Redis.
    """
    captcha_id = uuid.uuid4().hex
    # Некорректный JSON
    mock_redis_client.get.return_value = "Это не JSON" 

    service = CaptchaChallengeService(redis_client=mock_redis_client)
    is_valid = await service.verify_solution(captcha_id, 10, 10)
    assert is_valid is False, "Верификация должна быть неуспешной при некорректном JSON"
    # Ключ удаляется в любом случае после попытки чтения (согласно текущей логике verify_solution)
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")

    # Сброс мока для следующей проверки
    mock_redis_client.reset_mock() # Сбрасываем счетчики вызовов и return_value
    mock_redis_client.get.return_value = json.dumps({"target_shape_type": "circle"}) # Нет all_drawn_shapes
    is_valid = await service.verify_solution(captcha_id + "_v2", 10, 10) # Другой ID для чистоты
    assert is_valid is False, "Верификация должна быть неуспешной при отсутствии 'all_drawn_shapes'"
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}_v2")

#===============
@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_square(mock_redis_client):
    """
    Проверяет успешную верификацию при правильном клике на квадрат.
    """
    model_name = "base_model"
    shape_type = "square" # Тестируем квадрат
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    # Параметры для нашего квадрата (уже отмасштабированные)
    sq_cx_upscaled = 250 * upscale_factor
    sq_cy_upscaled = 120 * upscale_factor
    sq_side_upscaled = 40 * upscale_factor # Длина стороны
    sq_rotation_rad = 0.2 # Небольшой угол поворота для интереса
    selected_color = AVAILABLE_COLORS_GENERAL[1] # Другой цвет

    # Для квадрата params_for_storage также включает 'vertices', которые рассчитываются в __init__
    # SquareShape.__init__ ожидает 'side'.
    # SquareShape.get_draw_details() сохранит 'cx', 'cy', 'side', 'rotation_rad', 'vertices'.
    # При воссоздании в verify_solution мы используем 'cx', 'cy', 'side', 'rotation_rad' для __init__.
    
    # Вершины для квадрата (рассчитаем их здесь для теста, чтобы знать, куда кликать)
    # Это эмулирует то, что сделал бы SquareShape.__init__
    half_side = sq_side_upscaled / 2.0
    verts_orig_centered = [
        (-half_side, -half_side), (half_side, -half_side),
        (half_side, half_side), (-half_side, half_side)
    ]
    # Используем geometry_utils для расчета повернутых вершин (если он импортирован в тест)
    # Для простоты теста, если sq_rotation_rad = 0, то вершины будут предсказуемы.
    # Если rotation !=0, то клик должен быть в повернутую фигуру.
    # Для простоты этого теста, давайте сделаем rotation_rad = 0.0 для клика в центр.
    # Если хотим тест с поворотом, то нужно точно рассчитать, где будет центр после поворота,
    # или кликать в одну из вершин.
    # Для клика в центр, поворот не влияет на сам центр.

    # Клик точно в центр квадрата (координаты не отмасштабированные)
    click_x = sq_cx_upscaled // upscale_factor
    click_y = sq_cy_upscaled // upscale_factor

    # Если хотим кликнуть не в центр, а, например, в угол (с учетом поворота),
    # то нужно будет рассчитать координаты этого угла.
    # Для простоты, этот тест кликает в центр, что всегда внутри.

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [
            {
                "shape_type": shape_type,
                "color_name_or_rgb": selected_color,
                "params_for_storage": {
                    "cx": sq_cx_upscaled,
                    "cy": sq_cy_upscaled,
                    "side": sq_side_upscaled,
                    "rotation_rad": sq_rotation_rad,
                    # 'vertices' тоже будут сохранены SquareShape.get_draw_details(),
                    # но для воссоздания экземпляра в verify_solution они не обязательны,
                    # т.к. __init__ их пересчитает из cx, cy, side, rotation_rad.
                    # Но их наличие не помешает.
                },
                "bbox_upscaled": [ # Примерный bbox, точный рассчитает SquareShape
                    float(sq_cx_upscaled - half_side * 1.5), # С запасом из-за возможного поворота
                    float(sq_cy_upscaled - half_side * 1.5),
                    float(sq_cx_upscaled + half_side * 1.5),
                    float(sq_cy_upscaled + half_side * 1.5)
                ]
            }
        ]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)

    service = CaptchaChallengeService(
        redis_client=mock_redis_client,
        model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )

    is_valid = await service.verify_solution(captcha_id, click_x, click_y)

    assert is_valid is True, "Верификация должна быть успешной при клике в центр квадрата"
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")


@pytest.mark.asyncio
async def test_verify_solution_incorrect_click_miss_square(mock_redis_client):
    """
    Проверяет неудачную верификацию при клике мимо квадрата.
    """
    model_name = "base_model"
    shape_type = "square"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    sq_cx_upscaled = 250 * upscale_factor
    sq_cy_upscaled = 120 * upscale_factor
    sq_side_upscaled = 40 * upscale_factor
    sq_rotation_rad = 0.0 # Без поворота для простоты расчета клика "мимо"

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": "blue",
            "params_for_storage": {"cx": sq_cx_upscaled, "cy": sq_cy_upscaled, "side": sq_side_upscaled, "rotation_rad": sq_rotation_rad},
            "bbox_upscaled": [float(c) for c in [sq_cx_upscaled - sq_side_upscaled/2, sq_cy_upscaled - sq_side_upscaled/2, 
                                                 sq_cx_upscaled + sq_side_upscaled/2, sq_cy_upscaled + sq_side_upscaled/2]]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)

    service = CaptchaChallengeService(
        redis_client=mock_redis_client,
        model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )

    # Клик далеко от квадрата (координаты не отмасштабированные)
    click_x = (sq_cx_upscaled + sq_side_upscaled + 20) // upscale_factor # Правее и дальше
    click_y = sq_cy_upscaled // upscale_factor

    is_valid = await service.verify_solution(captcha_id, click_x, click_y)

    assert is_valid is False, "Верификация должна быть неуспешной при клике мимо квадрата"
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")

@pytest.mark.asyncio
async def test_create_challenge_with_rectangle_shape(mock_redis_client):
    """
    Тестирует создание CAPTCHA, когда в модели доступен только прямоугольник.
    """
    model_name_to_test = "base_model"
    expected_shape_type = "rectangle"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[2] # Пример цвета

    # Мокируем random.sample, чтобы image_generator выбрал "rectangle" и предсказуемый цвет
    mock_sample_side_effects = [
        [expected_shape_type],  # Для выбора типа фигуры
        [selected_color]        # Для выбора цвета
    ]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client,
            model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types

        captcha_id, image_object, prompt_text = await service.create_challenge()
    
        assert isinstance(captcha_id, str)
        assert isinstance(image_object, Image.Image)
        assert image_object.width == DEFAULT_CAPTCHA_WIDTH
        assert image_object.height == DEFAULT_CAPTCHA_HEIGHT # Добавил проверку высоты
        assert prompt_text.lower().count(expected_shape_type) > 0

        # Проверяем данные, сохраненные в Redis
        mock_redis_client.set.assert_called_once()
        
        # Правильно получаем аргументы вызова mock'а
        call_args_tuple = mock_redis_client.set.call_args.args
        call_kwargs_dict = mock_redis_client.set.call_args.kwargs

        assert len(call_args_tuple) == 2, "Ожидалось 2 позиционных аргумента для redis.set"
        # redis_key_actual = call_args_tuple[0] # Можно добавить проверку ключа, если нужно
        redis_data_json_str = call_args_tuple[1]

        assert "ex" in call_kwargs_dict, "Аргумент 'ex' (TTL) должен быть передан в redis.set"
        # assert call_kwargs_dict["ex"] == service.captcha_ttl # Можно добавить проверку TTL

        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "width" in shape_detail_dict["params_for_storage"]
        assert "height" in shape_detail_dict["params_for_storage"]


@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_rectangle(mock_redis_client):
    """
    Проверяет успешную верификацию при правильном клике на прямоугольник.
    """
    model_name = "base_model"
    shape_type = "rectangle"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    rect_cx_upscaled = 180 * upscale_factor
    rect_cy_upscaled = 130 * upscale_factor
    rect_w_upscaled = 60 * upscale_factor
    rect_h_upscaled = 30 * upscale_factor
    rect_rotation_rad = 0.0 # Без поворота для простоты клика в центр
    selected_color = AVAILABLE_COLORS_GENERAL[3]

    # Клик точно в центр прямоугольника
    click_x = rect_cx_upscaled // upscale_factor
    click_y = rect_cy_upscaled // upscale_factor

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": rect_cx_upscaled, "cy": rect_cy_upscaled,
                "width": rect_w_upscaled, "height": rect_h_upscaled,
                "rotation_rad": rect_rotation_rad,
                # 'vertices' здесь не обязательны для теста, т.к. verify_solution их не использует
                # напрямую для __init__, а __init__ их пересчитает.
            },
            "bbox_upscaled": [ # Примерный bbox
                float(rect_cx_upscaled - rect_w_upscaled/2), float(rect_cy_upscaled - rect_h_upscaled/2),
                float(rect_cx_upscaled + rect_w_upscaled/2), float(rect_cy_upscaled + rect_h_upscaled/2)
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)

    service = CaptchaChallengeService(
        redis_client=mock_redis_client,
        model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр прямоугольника"

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_rectangle(mock_redis_client): # Название было test_verify_solution_correct_click_on_square, исправляем
    """
    Проверяет успешную верификацию при правильном клике на прямоугольник.
    """
    model_name = "base_model"
    shape_type = "rectangle"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    # Параметры для нашего прямоугольника (уже отмасштабированные)
    rect_cx_upscaled = 180 * upscale_factor
    rect_cy_upscaled = 130 * upscale_factor
    rect_w_upscaled = 70 * upscale_factor # Ширина
    rect_h_upscaled = 40 * upscale_factor # Высота
    rect_rotation_rad = 0.0 # Без поворота для простоты клика в центр
    selected_color = AVAILABLE_COLORS_GENERAL[4]

    # Клик точно в центр прямоугольника
    click_x = rect_cx_upscaled // upscale_factor
    click_y = rect_cy_upscaled // upscale_factor

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [
            {
                "shape_type": shape_type,
                "color_name_or_rgb": selected_color,
                "params_for_storage": {
                    "cx": rect_cx_upscaled, "cy": rect_cy_upscaled,
                    "width": rect_w_upscaled, "height": rect_h_upscaled,
                    "rotation_rad": rect_rotation_rad,
                    # 'vertices' будут рассчитаны в __init__ RectangleShape при воссоздании,
                    # но для теста можно их не добавлять в mock, если __init__ их пересчитывает.
                    # В params_for_storage они сохраняются методом get_draw_details.
                },
                "bbox_upscaled": [ # Примерный bbox для axis-aligned
                    float(rect_cx_upscaled - rect_w_upscaled / 2),
                    float(rect_cy_upscaled - rect_h_upscaled / 2),
                    float(rect_cx_upscaled + rect_w_upscaled / 2),
                    float(rect_cy_upscaled + rect_h_upscaled / 2)
                ]
            }
        ]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)

    service = CaptchaChallengeService(
        redis_client=mock_redis_client,
        model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр прямоугольника"
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")


@pytest.mark.asyncio
async def test_verify_solution_incorrect_click_miss_rectangle(mock_redis_client):
    """
    Проверяет неудачную верификацию при клике мимо прямоугольника.
    """
    model_name = "base_model"
    shape_type = "rectangle"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    rect_cx_upscaled = 180 * upscale_factor
    rect_cy_upscaled = 130 * upscale_factor
    rect_w_upscaled = 70 * upscale_factor
    rect_h_upscaled = 40 * upscale_factor
    rect_rotation_rad = 0.0

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": "green",
            "params_for_storage": {
                "cx": rect_cx_upscaled, "cy": rect_cy_upscaled,
                "width": rect_w_upscaled, "height": rect_h_upscaled,
                "rotation_rad": rect_rotation_rad
            },
            "bbox_upscaled": [
                float(rect_cx_upscaled - rect_w_upscaled / 2), float(rect_cy_upscaled - rect_h_upscaled / 2),
                float(rect_cx_upscaled + rect_w_upscaled / 2), float(rect_cy_upscaled + rect_h_upscaled / 2)
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)

    service = CaptchaChallengeService(
        redis_client=mock_redis_client,
        model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )

    # Клик далеко от прямоугольника
    click_x = (rect_cx_upscaled + rect_w_upscaled + 20) // upscale_factor
    click_y = rect_cy_upscaled // upscale_factor

    is_valid = await service.verify_solution(captcha_id, click_x, click_y)

    assert is_valid is False, "Верификация должна быть неуспешной при клике мимо прямоугольника"
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")

# tests/test_challenge_service.py
# ... (импорты и фикстура mock_redis_client как ранее) ...

@pytest.mark.asyncio
async def test_create_challenge_with_equilateral_triangle(mock_redis_client):
    """
    Тестирует создание CAPTCHA, когда доступен равносторонний треугольник.
    """
    model_name_to_test = "base_model"
    expected_shape_type = "equilateral_triangle"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[5] # Пример цвета

    # Мокируем random.sample
    mock_sample_side_effects = [
        [expected_shape_type],  # Для выбора типа фигуры
        [selected_color]        # Для выбора цвета
    ]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects) as mock_rand_sample: # Добавил as mock_rand_sample для возможной проверки вызовов
        service = CaptchaChallengeService(
            redis_client=mock_redis_client,
            model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types

        captcha_id, image_object, prompt_text = await service.create_challenge()

        assert isinstance(captcha_id, str)
        assert isinstance(image_object, Image.Image)
        assert prompt_text.lower().count(expected_shape_type.replace("_", " ")) > 0 # Проверяем, что в подсказке есть название фигуры

        # Проверяем вызовы random.sample (опционально, но полезно для отладки мока)
        assert mock_rand_sample.call_count == 2
        mock_rand_sample.call_args_list[0].assert_called_with(service.current_model_shape_types, num_shapes_to_generate)
        mock_rand_sample.call_args_list[1].assert_called_with(service.current_model_colors, num_shapes_to_generate)

        # Проверяем данные, сохраненные в Redis
        mock_redis_client.set.assert_called_once()
        
        call_args_tuple = mock_redis_client.set.call_args.args
        call_kwargs_dict = mock_redis_client.set.call_args.kwargs

        assert len(call_args_tuple) == 2, "Ожидалось 2 позиционных аргумента для redis.set"
        redis_key_actual = call_args_tuple[0]
        redis_data_json_str = call_args_tuple[1]

        assert redis_key_actual == f"{service.redis_key_prefix}{captcha_id}"
        assert "ex" in call_kwargs_dict, "Аргумент 'ex' (TTL) должен быть передан в redis.set"
        assert call_kwargs_dict["ex"] == service.captcha_ttl

        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "side_length" in shape_detail_dict["params_for_storage"] # Проверяем специфичный параметр для треугольника

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_equilateral_triangle(mock_redis_client):
    """
    Проверяет успешную верификацию при правильном клике на равносторонний треугольник.
    """
    model_name = "base_model"
    shape_type = "equilateral_triangle"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    tri_cx_upscaled = 200 * upscale_factor
    tri_cy_upscaled = 180 * upscale_factor
    tri_side_length_upscaled = 50 * upscale_factor
    tri_rotation_rad = 0.0 # Без поворота для простоты клика в центр
    selected_color = AVAILABLE_COLORS_GENERAL[6]

    click_x = tri_cx_upscaled // upscale_factor
    click_y = tri_cy_upscaled // upscale_factor # Клик в центр (для равностороннего треугольника это внутри)

    # Рассчитаем примерный bbox для мока (точный будет внутри get_draw_details)
    # Высота равностороннего треугольника h = side * sqrt(3)/2
    # Радиус описанной окружности R = side / sqrt(3)
    # Вершины для треугольника с центром в (0,0) и вершиной сверху: (0, -R), (R*cos(210deg), R*sin(210deg)), (R*cos(330deg), R*sin(330deg))
    # или (0, -R), (-side/2, R/2), (side/2, R/2)
    # Примерный bbox: cx +/- R, cy +/- R
    radius_circumscribed = tri_side_length_upscaled / math.sqrt(3)

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": tri_cx_upscaled, "cy": tri_cy_upscaled,
                "side_length": tri_side_length_upscaled,
                "rotation_rad": tri_rotation_rad
            },
            "bbox_upscaled": [ # Примерный bbox
                float(tri_cx_upscaled - radius_circumscribed), float(tri_cy_upscaled - radius_circumscribed),
                float(tri_cx_upscaled + radius_circumscribed), float(tri_cy_upscaled + radius_circumscribed)
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)

    service = CaptchaChallengeService(
        redis_client=mock_redis_client,
        model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр равностороннего треугольника"


@pytest.mark.asyncio
async def test_create_challenge_with_pentagon(mock_redis_client):
    model_name_to_test = "base_model"
    expected_shape_type = "pentagon"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[7]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge() # image_object не проверяем детально
        assert prompt_text.lower().count(expected_shape_type) > 0
        mock_redis_client.set.assert_called_once()
        
        # Правильно получаем аргументы вызова mock'а
        call_args_tuple = mock_redis_client.set.call_args.args
        call_kwargs_dict = mock_redis_client.set.call_args.kwargs

        assert len(call_args_tuple) == 2, "Ожидалось 2 позиционных аргумента для redis.set"
        redis_key_actual = call_args_tuple[0]
        redis_data_json_str = call_args_tuple[1]

        assert "ex" in call_kwargs_dict, "Аргумент 'ex' (TTL) должен быть передан в redis.set"
        redis_ttl_actual = call_kwargs_dict["ex"]
        
        # Теперь можно проверять значения redis_key_actual, redis_ttl_actual и redis_data_json_str
        assert redis_key_actual == f"{service.redis_key_prefix}{captcha_id}"
        assert redis_ttl_actual == service.captcha_ttl

        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "radius" in shape_detail_dict["params_for_storage"]

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_pentagon(mock_redis_client):
    model_name = "base_model"
    shape_type = "pentagon"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    # Параметры для пентагона (отмасштабированные)
    item_cx_upscaled = 220 * upscale_factor
    item_cy_upscaled = 160 * upscale_factor
    item_radius_upscaled = 45 * upscale_factor # Радиус описанной окружности
    item_rotation_rad = 0.1
    selected_color = AVAILABLE_COLORS_GENERAL[8]

    click_x = item_cx_upscaled // upscale_factor # Клик в центр
    click_y = item_cy_upscaled // upscale_factor

    # Примерный bbox для мока (центр +/- радиус)
    radius_for_bbox = float(item_radius_upscaled) 
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "radius": item_radius_upscaled, "rotation_rad": item_rotation_rad
            },
            "bbox_upscaled": [
                item_cx_upscaled - radius_for_bbox, item_cy_upscaled - radius_for_bbox,
                item_cx_upscaled + radius_for_bbox, item_cy_upscaled + radius_for_bbox
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр пентагона"

@pytest.mark.asyncio
async def test_create_challenge_with_star5(mock_redis_client):
    model_name_to_test = "base_model"
    expected_shape_type = "star5"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[9]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type.replace("5","")) > 0 # "star"

        mock_redis_client.set.assert_called_once()
        
        # Правильно получаем аргументы вызова mock'а
        call_args_tuple = mock_redis_client.set.call_args.args
        call_kwargs_dict = mock_redis_client.set.call_args.kwargs

        assert len(call_args_tuple) == 2, "Ожидалось 2 позиционных аргумента для redis.set"
        redis_key_actual = call_args_tuple[0] # Первый позиционный аргумент - ключ
        redis_data_json_str = call_args_tuple[1] # Второй позиционный аргумент - данные JSON

        assert "ex" in call_kwargs_dict, "Аргумент 'ex' (TTL) должен быть передан в redis.set"
        redis_ttl_actual = call_kwargs_dict["ex"]
        
        # Теперь можно проверять значения redis_key_actual, redis_ttl_actual и redis_data_json_str
        assert redis_key_actual == f"{service.redis_key_prefix}{captcha_id}"
        assert redis_ttl_actual == service.captcha_ttl

        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "outer_radius" in shape_detail_dict["params_for_storage"]
        assert "inner_radius" in shape_detail_dict["params_for_storage"]

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_star5(mock_redis_client):
    model_name = "base_model"
    shape_type = "star5"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_outer_r_upscaled = 50 * upscale_factor
    item_inner_r_upscaled = 20 * upscale_factor
    item_rotation_rad = 0.0 # Для простоты клика в центр
    selected_color = AVAILABLE_COLORS_GENERAL[10]

    click_x = item_cx_upscaled // upscale_factor
    click_y = item_cy_upscaled // upscale_factor # Клик в центр (внутри звезды)

    # Примерный bbox (центр +/- внешний радиус)
    outer_r_bbox = float(item_outer_r_upscaled)
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "outer_radius": item_outer_r_upscaled, "inner_radius": item_inner_r_upscaled,
                "rotation_rad": item_rotation_rad
            },
            "bbox_upscaled": [
                item_cx_upscaled - outer_r_bbox, item_cy_upscaled - outer_r_bbox,
                item_cx_upscaled + outer_r_bbox, item_cy_upscaled + outer_r_bbox
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр звезды"


@pytest.mark.asyncio
async def test_create_challenge_with_trapezoid(mock_redis_client):
    model_name_to_test = "base_model"
    expected_shape_type = "trapezoid"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[13]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type) > 0

        # ... (исправленная проверка вызова mock_redis_client.set)
        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        # ... (конец исправленной проверки)

        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "height" in shape_detail_dict["params_for_storage"]
        assert "bottom_width" in shape_detail_dict["params_for_storage"]
        assert "top_width" in shape_detail_dict["params_for_storage"]

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_trapezoid(mock_redis_client):
    model_name = "base_model"
    shape_type = "trapezoid"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_h_upscaled = 50 * upscale_factor
    item_bw_upscaled = 70 * upscale_factor
    item_tw_upscaled = 40 * upscale_factor
    item_rotation_rad = 0.0
    selected_color = AVAILABLE_COLORS_GENERAL[14]

    click_x = item_cx_upscaled // upscale_factor
    click_y = item_cy_upscaled // upscale_factor

    half_h = item_h_upscaled / 2.0; half_bw = item_bw_upscaled / 2.0; half_tw = item_tw_upscaled / 2.0
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "height": item_h_upscaled, "bottom_width": item_bw_upscaled, "top_width": item_tw_upscaled,
                "rotation_rad": item_rotation_rad
            },
            "bbox_upscaled": [ # Примерный bbox
                item_cx_upscaled - half_bw, item_cy_upscaled - half_h,
                item_cx_upscaled + half_bw, item_cy_upscaled + half_h
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр трапеции"

@pytest.mark.asyncio
async def test_create_challenge_with_rhombus(mock_redis_client):
    model_name_to_test = "base_model"
    expected_shape_type = "rhombus"
    num_shapes_to_generate = 1
    # Используем другой индекс, чтобы цвет отличался от предыдущих тестов
    selected_color = AVAILABLE_COLORS_GENERAL[11 % len(AVAILABLE_COLORS_GENERAL)] 

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects) as mock_rand_sample:
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, image_object, prompt_text = await service.create_challenge()

        assert isinstance(captcha_id, str)
        assert isinstance(image_object, Image.Image)
        assert prompt_text.lower().count(expected_shape_type) > 0

        # Проверка вызовов random.sample
        assert mock_rand_sample.call_count == 2
        
        # Проверка данных, сохраненных в Redis
        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        call_kwargs_dict = mock_redis_client.set.call_args.kwargs
        assert len(call_args_tuple) == 2
        redis_key_actual = call_args_tuple[0]
        redis_data_json_str = call_args_tuple[1]
        assert redis_key_actual == f"{service.redis_key_prefix}{captcha_id}"
        assert "ex" in call_kwargs_dict and call_kwargs_dict["ex"] == service.captcha_ttl

        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "d1" in shape_detail_dict["params_for_storage"]
        assert "d2" in shape_detail_dict["params_for_storage"]

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_rhombus(mock_redis_client):
    model_name = "base_model"
    shape_type = "rhombus"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 150 * upscale_factor
    item_cy_upscaled = 170 * upscale_factor
    item_d1_upscaled = 70 * upscale_factor # Диагональ 1 (например, горизонтальная до поворота)
    item_d2_upscaled = 50 * upscale_factor # Диагональ 2 (например, вертикальная до поворота)
    item_rotation_rad = 0.0 # Без поворота для простоты клика в центр
    selected_color = AVAILABLE_COLORS_GENERAL[12 % len(AVAILABLE_COLORS_GENERAL)]

    # Клик точно в центр ромба
    click_x = item_cx_upscaled // upscale_factor
    click_y = item_cy_upscaled // upscale_factor
    
    print(f"DEBUG [Test Rhombus Verify HIT]: Click (orig): ({click_x}, {click_y}), Upscaled click: ({click_x * upscale_factor}, {click_y * upscale_factor})")
    print(f"DEBUG [Test Rhombus Verify HIT]: Rhombus params for storage: cx={item_cx_upscaled}, cy={item_cy_upscaled}, d1={item_d1_upscaled}, d2={item_d2_upscaled}, rot={item_rotation_rad}")

    # Bbox для ромба: cx +/- d1/2 (если d1 горизонтальная), cy +/- d2/2 (если d2 вертикальная) - при rotation=0
    bbox_calc = [
        float(item_cx_upscaled - item_d1_upscaled / 2), float(item_cy_upscaled - item_d2_upscaled / 2),
        float(item_cx_upscaled + item_d1_upscaled / 2), float(item_cy_upscaled + item_d2_upscaled / 2)
    ]

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "d1": item_d1_upscaled, "d2": item_d2_upscaled,
                "rotation_rad": item_rotation_rad
                # 'vertices' будут добавлены реальным get_draw_details, но для __init__ они не нужны
            },
            "bbox_upscaled": bbox_calc 
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр ромба"
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")

@pytest.mark.asyncio
async def test_verify_solution_incorrect_click_miss_rhombus(mock_redis_client):
    model_name = "base_model"
    shape_type = "rhombus"
    # ... (аналогично test_verify_solution_incorrect_click_miss_rectangle,
    #      но с параметрами ромба и кликом заведомо мимо)
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR
    item_cx_upscaled = 150 * upscale_factor
    item_cy_upscaled = 170 * upscale_factor
    item_d1_upscaled = 70 * upscale_factor 
    item_d2_upscaled = 50 * upscale_factor 
    item_rotation_rad = 0.0
    selected_color = "blue"

    # Клик далеко от ромба
    click_x = (item_cx_upscaled + item_d1_upscaled + 20) // upscale_factor # Правее и дальше
    click_y = item_cy_upscaled // upscale_factor

    print(f"DEBUG [Test Rhombus Verify MISS]: Click (orig): ({click_x}, {click_y}), Upscaled click: ({click_x * upscale_factor}, {click_y * upscale_factor})")
    print(f"DEBUG [Test Rhombus Verify MISS]: Rhombus params for storage: cx={item_cx_upscaled}, cy={item_cy_upscaled}, d1={item_d1_upscaled}, d2={item_d2_upscaled}, rot={item_rotation_rad}")

    bbox_calc = [
        float(item_cx_upscaled - item_d1_upscaled / 2), float(item_cy_upscaled - item_d2_upscaled / 2),
        float(item_cx_upscaled + item_d1_upscaled / 2), float(item_cy_upscaled + item_d2_upscaled / 2)
    ]
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "d1": item_d1_upscaled, "d2": item_d2_upscaled,
                "rotation_rad": item_rotation_rad
            }, "bbox_upscaled": bbox_calc
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is False, "Верификация должна быть неуспешной при клике мимо ромба"


# --- Тесты для Cross ---

@pytest.mark.asyncio
async def test_create_challenge_with_cross(mock_redis_client):
    model_name_to_test = "base_model"
    expected_shape_type = "cross"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[13 % len(AVAILABLE_COLORS_GENERAL)]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects) as mock_rand_sample:
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, image_object, prompt_text = await service.create_challenge()

        assert isinstance(captcha_id, str)
        assert isinstance(image_object, Image.Image)
        assert prompt_text.lower().count(expected_shape_type) > 0

        assert mock_rand_sample.call_count == 2
        
        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        call_kwargs_dict = mock_redis_client.set.call_args.kwargs
        assert len(call_args_tuple) == 2
        redis_key_actual = call_args_tuple[0]
        redis_data_json_str = call_args_tuple[1]
        assert redis_key_actual == f"{service.redis_key_prefix}{captcha_id}"
        assert "ex" in call_kwargs_dict and call_kwargs_dict["ex"] == service.captcha_ttl

        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        # Исправленные ассерты для креста
        assert "size" in shape_detail_dict["params_for_storage"], \
            "params_for_storage для креста должен содержать 'size'"
        assert "thickness" in shape_detail_dict["params_for_storage"], \
            "params_for_storage для креста должен содержать 'thickness'"


@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_cross(mock_redis_client):
    model_name = "base_model"
    shape_type = "cross"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 210 * upscale_factor
    item_cy_upscaled = 140 * upscale_factor
    item_size_upscaled = 60 * upscale_factor # Общий размах "рук"
    item_thickness_upscaled = 20 * upscale_factor # Толщина "рук"
    item_rotation_rad = 0.0 
    selected_color = AVAILABLE_COLORS_GENERAL[14 % len(AVAILABLE_COLORS_GENERAL)]

    # Клик точно в центр креста
    click_x = item_cx_upscaled // upscale_factor
    click_y = item_cy_upscaled // upscale_factor

    print(f"DEBUG [Test Cross Verify HIT]: Click (orig): ({click_x}, {click_y}), Upscaled click: ({click_x * upscale_factor}, {click_y * upscale_factor})")
    print(f"DEBUG [Test Cross Verify HIT]: Cross params for storage: cx={item_cx_upscaled}, cy={item_cy_upscaled}, size={item_size_upscaled}, thickness={item_thickness_upscaled}, rot={item_rotation_rad}")
    
    # Bbox для креста: cx +/- size/2, cy +/- size/2 (приблизительно)
    half_size = float(item_size_upscaled / 2)
    bbox_calc = [
        item_cx_upscaled - half_size, item_cy_upscaled - half_size,
        item_cx_upscaled + half_size, item_cy_upscaled + half_size
    ]

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "size": item_size_upscaled, "thickness": item_thickness_upscaled,
                "rotation_rad": item_rotation_rad
            }, "bbox_upscaled": bbox_calc
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр креста" # Исправленное сообщение
    mock_redis_client.get.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")
    mock_redis_client.delete.assert_called_once_with(f"{service.redis_key_prefix}{captcha_id}")


@pytest.mark.asyncio
async def test_verify_solution_incorrect_click_miss_cross(mock_redis_client):
    model_name = "base_model"
    shape_type = "cross"
    # ... (аналогично test_verify_solution_incorrect_click_miss_rhombus,
    #      но с параметрами креста и кликом заведомо мимо)
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR
    item_cx_upscaled = 210 * upscale_factor
    item_cy_upscaled = 140 * upscale_factor
    item_size_upscaled = 60 * upscale_factor 
    item_thickness_upscaled = 20 * upscale_factor 
    item_rotation_rad = 0.0
    selected_color = "green"

    # Клик далеко от креста
    click_x = (item_cx_upscaled + item_size_upscaled + 20) // upscale_factor # Правее и дальше
    click_y = item_cy_upscaled // upscale_factor

    print(f"DEBUG [Test Cross Verify MISS]: Click (orig): ({click_x}, {click_y}), Upscaled click: ({click_x * upscale_factor}, {click_y * upscale_factor})")
    print(f"DEBUG [Test Cross Verify MISS]: Cross params for storage: cx={item_cx_upscaled}, cy={item_cy_upscaled}, size={item_size_upscaled}, thickness={item_thickness_upscaled}, rot={item_rotation_rad}")

    half_size = float(item_size_upscaled / 2)
    bbox_calc = [
        item_cx_upscaled - half_size, item_cy_upscaled - half_size,
        item_cx_upscaled + half_size, item_cy_upscaled + half_size
    ]
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "size": item_size_upscaled, "thickness": item_thickness_upscaled,
                "rotation_rad": item_rotation_rad
            }, "bbox_upscaled": bbox_calc
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is False, "Верификация должна быть неуспешной при клике мимо креста"

# ======= 3D =======

@pytest.mark.asyncio
async def test_create_challenge_with_sphere(mock_redis_client):
    model_name_to_test = "td_model" # Используем 3D модель
    expected_shape_type = "sphere"
    num_shapes_to_generate = 1
    # Цвета для td_model могут быть те же (AVAILABLE_COLORS_GENERAL), если не переопределены
    selected_color = AVAILABLE_COLORS_GENERAL[0] 

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        # Убедимся, что сервис знает о таком типе в td_model
        assert expected_shape_type in service.current_model_shape_types, \
            f"'{expected_shape_type}' должен быть в current_model_shape_types для модели '{model_name_to_test}'"

        captcha_id, image_object, prompt_text = await service.create_challenge()

        assert isinstance(captcha_id, str)
        assert isinstance(image_object, Image.Image)
        assert prompt_text.lower().count(expected_shape_type) > 0 # "сферу"

        # ... (проверка вызова mock_redis_client.set и содержимого stored_data)
        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "radius" in shape_detail_dict["params_for_storage"] # Как у круга

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_sphere(mock_redis_client):
    model_name = "td_model" # Используем 3D модель
    shape_type = "sphere"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_r_upscaled = 40 * upscale_factor
    selected_color = AVAILABLE_COLORS_GENERAL[1]

    click_x = item_cx_upscaled // upscale_factor # Клик в центр
    click_y = item_cy_upscaled // upscale_factor

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {"cx": item_cx_upscaled, "cy": item_cy_upscaled, "r": item_r_upscaled},
            "bbox_upscaled": [float(c) for c in [item_cx_upscaled - item_r_upscaled, item_cy_upscaled - item_r_upscaled, 
                                                 item_cx_upscaled + item_r_upscaled, item_cy_upscaled + item_r_upscaled]]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр сферы"

@pytest.mark.asyncio
async def test_create_challenge_with_cube(mock_redis_client):
    model_name_to_test = "td_model" # Используем 3D модель
    expected_shape_type = "cube"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[1] 

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, image_object, prompt_text = await service.create_challenge()

        assert isinstance(captcha_id, str)
        assert isinstance(image_object, Image.Image)
        assert prompt_text.lower().count(expected_shape_type) > 0

        mock_redis_client.set.assert_called_once()
        # ... (проверка вызова mock_redis_client.set и содержимого stored_data)
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "side" in shape_detail_dict["params_for_storage"]
        assert "depth_factor" in shape_detail_dict["params_for_storage"]

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_cube_face(mock_redis_client):
    model_name = "td_model"
    shape_type = "cube"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_side_upscaled = 50 * upscale_factor
    item_depth_factor = 0.5
    item_rotation_rad = 0.0 # Для простоты клика в центр передней грани
    selected_color = AVAILABLE_COLORS_GENERAL[2]

    # Клик в центр передней грани (при rotation_rad = 0.0)
    click_x = item_cx_upscaled // upscale_factor
    click_y = item_cy_upscaled // upscale_factor 

    # Примерный bbox (центр +/- (side/2 + side*depth_factor*~0.7))
    # Точный bbox будет сложнее из-за перспективы, но для мока это не так важно
    approx_extent = float(item_side_upscaled / 2 + item_side_upscaled * item_depth_factor * 0.707) # 0.707 ~ cos(pi/4)
    
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "side": item_side_upscaled, "depth_factor": item_depth_factor,
                "rotation_rad": item_rotation_rad
                # Факторы яркости можно опустить, если __init__ CubeShape имеет для них defaults
            },
            "bbox_upscaled": [
                item_cx_upscaled - approx_extent, item_cy_upscaled - approx_extent,
                item_cx_upscaled + approx_extent, item_cy_upscaled + approx_extent
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр передней грани куба"

@pytest.mark.asyncio
async def test_create_challenge_with_cylinder(mock_redis_client):
    model_name_to_test = "td_model"
    expected_shape_type = "cylinder"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[3]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type) > 0

        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "radius" in shape_detail_dict["params_for_storage"]
        assert "height" in shape_detail_dict["params_for_storage"]
        assert "perspective_factor_ellipse" in shape_detail_dict["params_for_storage"]

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_cylinder_top(mock_redis_client):
    model_name = "td_model"
    shape_type = "cylinder"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    # Параметры для цилиндра
    item_cx_top_upscaled = 200 * upscale_factor # cx_upscaled для CylinderShape __init__
    item_cy_top_upscaled = 100 * upscale_factor # cy_upscaled для CylinderShape __init__
    item_radius_upscaled = 40 * upscale_factor
    item_height_upscaled = 80 * upscale_factor
    item_perspective_factor = 0.4
    selected_color = AVAILABLE_COLORS_GENERAL[4]

    # Клик в центр верхнего эллипса
    click_x = item_cx_top_upscaled // upscale_factor
    click_y = item_cy_top_upscaled // upscale_factor 

    ellipse_ry_upscaled = max(1, int(item_radius_upscaled * item_perspective_factor))
    # bbox_upscaled: [cx - rx, cy_top - ry, cx + rx, cy_bottom + ry]
    bbox_calc = [
        float(item_cx_top_upscaled - item_radius_upscaled),
        float(item_cy_top_upscaled - ellipse_ry_upscaled),
        float(item_cx_top_upscaled + item_radius_upscaled),
        float(item_cy_top_upscaled + item_height_upscaled + ellipse_ry_upscaled)
    ]
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": { # Эти параметры ожидает __init__ CylinderShape (cx_top это cx_upscaled)
                "cx_top": item_cx_top_upscaled, "cy_top": item_cy_top_upscaled, 
                "radius": item_radius_upscaled, "height": item_height_upscaled,
                "perspective_factor_ellipse": item_perspective_factor
            },
            "bbox_upscaled": bbox_calc
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр верхнего эллипса цилиндра"

@pytest.mark.asyncio
async def test_create_challenge_with_cone(mock_redis_client):
    model_name_to_test = "td_model"
    expected_shape_type = "cone"
    # ... (остальная часть теста аналогична test_create_challenge_with_cube)
    # Проверяемые ключи в params_for_storage: "base_radius", "height", "perspective_factor_base"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[5]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type) > 0

        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "base_radius" in shape_detail_dict["params_for_storage"]
        assert "height" in shape_detail_dict["params_for_storage"]
        assert "perspective_factor_base" in shape_detail_dict["params_for_storage"]


@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_cone_base(mock_redis_client):
    model_name = "td_model"
    shape_type = "cone"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_base_upscaled = 200 * upscale_factor
    item_cy_base_upscaled = 220 * upscale_factor # Центр основания смещен вниз
    item_base_radius_upscaled = 40 * upscale_factor
    item_height_upscaled = 70 * upscale_factor # Апекс будет в cy_base - height
    item_perspective_factor = 0.4
    selected_color = AVAILABLE_COLORS_GENERAL[6]

    # Клик в центр основания конуса
    click_x = item_cx_base_upscaled // upscale_factor
    click_y = item_cy_base_upscaled // upscale_factor

    apex_y = item_cy_base_upscaled - item_height_upscaled
    ellipse_ry = max(1, int(item_base_radius_upscaled * item_perspective_factor))
    bbox_calc = [
        float(item_cx_base_upscaled - item_base_radius_upscaled), float(apex_y),
        float(item_cx_base_upscaled + item_base_radius_upscaled), float(item_cy_base_upscaled + ellipse_ry)
    ]
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx_base": item_cx_base_upscaled, "cy_base": item_cy_base_upscaled,
                "base_radius": item_base_radius_upscaled, "height": item_height_upscaled,
                "perspective_factor_base": item_perspective_factor
            },
            "bbox_upscaled": bbox_calc
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр основания конуса"

@pytest.mark.asyncio
async def test_create_challenge_with_pyramid(mock_redis_client):
    model_name_to_test = "td_model"
    expected_shape_type = "pyramid"
    # ... (остальная часть теста аналогична test_create_challenge_with_cube/cone)
    # Проверяемые ключи в params_for_storage: "base_side", "height", "depth_factor_base"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[7 % len(AVAILABLE_COLORS_GENERAL)]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type) > 0

        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "base_side" in shape_detail_dict["params_for_storage"]
        assert "height" in shape_detail_dict["params_for_storage"]
        assert "depth_factor_base" in shape_detail_dict["params_for_storage"]


@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_pyramid_face(mock_redis_client):
    model_name = "td_model"
    shape_type = "pyramid"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_base_upscaled = 200 * upscale_factor # Центр основания
    item_cy_base_upscaled = 200 * upscale_factor
    item_base_side_upscaled = 60 * upscale_factor
    item_height_upscaled = 70 * upscale_factor
    item_depth_factor_base = 0.5
    item_rotation_rad = 0.0 # Без поворота для простоты клика
    selected_color = AVAILABLE_COLORS_GENERAL[8 % len(AVAILABLE_COLORS_GENERAL)]

    # Клик примерно в центр одной из видимых боковых граней или основания
    # Для простоты теста, кликнем в центр основания (cx_base, cy_base)
    # Если основание рисуется и кликабельно, это должно сработать.
    click_x = item_cx_base_upscaled // upscale_factor
    click_y = item_cy_base_upscaled // upscale_factor 
    
    # Примерный bbox
    # Апекс: (item_cx_base_upscaled, item_cy_base_upscaled - item_height_upscaled)
    # Основание: вокруг (item_cx_base_upscaled, item_cy_base_upscaled) с размером item_base_side_upscaled
    apex_y = item_cy_base_upscaled - item_height_upscaled
    half_side_base = item_base_side_upscaled / 2
    bbox_calc = [
        float(item_cx_base_upscaled - half_side_base), float(apex_y),
        float(item_cx_base_upscaled + half_side_base), float(item_cy_base_upscaled + half_side_base * item_depth_factor_base) # Учитываем перспективу основания
    ]

    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx_base": item_cx_base_upscaled, "cy_base": item_cy_base_upscaled,
                "base_side": item_base_side_upscaled, "height": item_height_upscaled,
                "depth_factor_base": item_depth_factor_base,
                "rotation_rad": item_rotation_rad
            },
            "bbox_upscaled": bbox_calc
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике на видимую часть пирамиды"

@pytest.mark.asyncio
async def test_create_challenge_with_cuboid(mock_redis_client):
    model_name_to_test = "td_model"
    expected_shape_type = "cuboid"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[0]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type) > 0

        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "width" in shape_detail_dict["params_for_storage"]
        assert "height" in shape_detail_dict["params_for_storage"]
        assert "depth" in shape_detail_dict["params_for_storage"]

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_cuboid_face(mock_redis_client):
    model_name = "td_model"
    shape_type = "cuboid"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_w_upscaled = 60 * upscale_factor
    item_h_upscaled = 40 * upscale_factor
    item_d_upscaled = 30 * upscale_factor
    item_depth_factor_visual = 0.5
    item_rotation_rad = 0.0 
    selected_color = AVAILABLE_COLORS_GENERAL[1]

    click_x = item_cx_upscaled // upscale_factor # Клик в центр передней грани
    click_y = item_cy_upscaled // upscale_factor 

    approx_extent_w = float(item_w_upscaled / 2 + item_d_upscaled * item_depth_factor_visual * 0.707)
    approx_extent_h = float(item_h_upscaled / 2 + item_d_upscaled * item_depth_factor_visual * 0.707)
    
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "width": item_w_upscaled, "height": item_h_upscaled, "depth": item_d_upscaled,
                "depth_factor_visual": item_depth_factor_visual,
                "rotation_rad": item_rotation_rad
            },
            "bbox_upscaled": [
                item_cx_upscaled - approx_extent_w, item_cy_upscaled - approx_extent_h,
                item_cx_upscaled + approx_extent_w, item_cy_upscaled + approx_extent_h
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр передней грани кубоида"

@pytest.mark.asyncio
async def test_create_challenge_with_octahedron(mock_redis_client):
    model_name_to_test = "td_model"
    expected_shape_type = "octahedron"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[2 % len(AVAILABLE_COLORS_GENERAL)] # Пример

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type) > 0

        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "size" in shape_detail_dict["params_for_storage"]
        # Можно также проверить наличие tilt_angle_rad, perspective_factor_z, если они всегда сохраняются


@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_octahedron_face(mock_redis_client):
    model_name = "td_model"
    shape_type = "octahedron"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_size_upscaled = 50 * upscale_factor
    item_rotation_rad = 0.0 
    item_tilt_angle_rad = 0.0 # Без наклона для простоты клика
    item_perspective_factor_z = 0.5
    selected_color = AVAILABLE_COLORS_GENERAL[3 % len(AVAILABLE_COLORS_GENERAL)]

    # Клик примерно в центр фигуры. Точное местоположение грани зависит от проекции.
    # Для простоты теста, кликнем в cx, cy, что должно попасть на какую-либо из передних граней.
    click_x = item_cx_upscaled // upscale_factor 
    click_y = item_cy_upscaled // upscale_factor 
    
    # Примерный bbox
    # Для октаэдра bbox зависит от size и углов. 
    # Возьмем максимальный размах по всем осям.
    max_extent = float(item_size_upscaled * (1 + item_perspective_factor_z)) # Грубая оценка
    
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "size": item_size_upscaled,
                "rotation_rad": item_rotation_rad,
                "tilt_angle_rad": item_tilt_angle_rad,
                "perspective_factor_z": item_perspective_factor_z
                # brightness_factors можно опустить, если __init__ имеет для них default
            },
            "bbox_upscaled": [ # Очень грубый bbox для теста
                item_cx_upscaled - max_extent, item_cy_upscaled - max_extent,
                item_cx_upscaled + max_extent, item_cy_upscaled + max_extent
            ]
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике на видимую часть октаэдра"

@pytest.mark.asyncio
async def test_create_challenge_with_torus(mock_redis_client):
    model_name_to_test = "td_model"
    expected_shape_type = "torus"
    num_shapes_to_generate = 1
    # Используем цвет, который является кортежем, для воспроизведения ошибки
    # AVAILABLE_COLORS_GENERAL[4] это (128, 0, 128)
    selected_color = AVAILABLE_COLORS_GENERAL[4 % len(AVAILABLE_COLORS_GENERAL)] 

    mock_sample_side_effects = [
        [expected_shape_type],  # Для выбора типа фигуры
        [selected_color]        # Для выбора цвета
    ]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects) as mock_rand_sample:
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, 
            model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types

        captcha_id, image_object, prompt_text = await service.create_challenge()

        assert isinstance(captcha_id, str)
        assert len(captcha_id) == 32
        assert isinstance(image_object, Image.Image)
        assert image_object.width == DEFAULT_CAPTCHA_WIDTH
        assert image_object.height == DEFAULT_CAPTCHA_HEIGHT
        assert image_object.mode == "RGB"
        
        assert isinstance(prompt_text, str)
        assert expected_shape_type in prompt_text.lower()

        assert mock_rand_sample.call_count == 2
        mock_rand_sample.call_args_list[0].assert_called_with(service.current_model_shape_types, num_shapes_to_generate)
        mock_rand_sample.call_args_list[1].assert_called_with(service.current_model_colors, num_shapes_to_generate)

        mock_redis_client.set.assert_called_once()
        
        call_args_tuple = mock_redis_client.set.call_args.args
        call_kwargs_dict = mock_redis_client.set.call_args.kwargs
        redis_key_actual = call_args_tuple[0]
        redis_data_json_str = call_args_tuple[1]
        assert redis_key_actual == f"{service.redis_key_prefix}{captcha_id}"
        assert "ex" in call_kwargs_dict and call_kwargs_dict["ex"] == service.captcha_ttl

        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        
        all_drawn_shapes = stored_data["all_drawn_shapes"]
        assert isinstance(all_drawn_shapes, list)
        assert len(all_drawn_shapes) == num_shapes_to_generate
        
        shape_detail_dict = all_drawn_shapes[0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        
        # ИСПРАВЛЕННАЯ ПРОВЕРКА ЦВЕТА:
        expected_color_in_storage = list(selected_color) if isinstance(selected_color, tuple) else selected_color
        assert shape_detail_dict["color_name_or_rgb"] == expected_color_in_storage, \
            f"Сохраненный цвет {shape_detail_dict['color_name_or_rgb']} не совпадает с ожидаемым {expected_color_in_storage}"
        
        params_stored = shape_detail_dict["params_for_storage"]
        assert "outer_radius" in params_stored
        assert "tube_radius" in params_stored
        
#        assert "outer_rx" in params_stored
#        assert "outer_ry" in params_stored
#        assert "inner_rx" in params_stored
#        assert "inner_ry" in params_stored
        
#        assert params_stored["outer_rx"] == params_stored["outer_radius"]
#        assert params_stored["outer_ry"] == params_stored["outer_radius"]
#        if params_stored["inner_rx"] > 0 :
#            expected_inner_radius = params_stored["outer_radius"] - params_stored["tube_radius"]
#            assert params_stored["inner_rx"] == expected_inner_radius
#            assert params_stored["inner_ry"] == expected_inner_radius

        assert "highlight_factor" in params_stored
        assert "shadow_factor" in params_stored
        assert "bbox_upscaled" in shape_detail_dict

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_torus_body(mock_redis_client):
    model_name = "td_model"
    shape_type = "torus"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_outer_radius_upscaled = 60 * upscale_factor
    item_tube_radius_upscaled = 20 * upscale_factor 
    # item_perspective_factor больше не нужен
    selected_color = "magenta"

    # Рассчитываем параметры окружностей для клика и bbox
    outer_r = item_outer_radius_upscaled
    hole_r = item_outer_radius_upscaled - item_tube_radius_upscaled
    inner_r = hole_r if hole_r > 0 else 0

    # Клик на тело тора
    click_target_radius_on_axis = hole_r + item_tube_radius_upscaled / 2 
    click_x_offset = int(click_target_radius_on_axis) 
    
    click_x_final_upscaled = item_cx_upscaled + click_x_offset
    click_y_final_upscaled = item_cy_upscaled 

    click_x_orig = click_x_final_upscaled // upscale_factor
    click_y_orig = click_y_final_upscaled // upscale_factor
    
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": { 
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "outer_radius": item_outer_radius_upscaled, 
                "tube_radius": item_tube_radius_upscaled,
                # "perspective_factor": item_perspective_factor, # УДАЛЕНО
                # Сохраняем rx/ry, которые теперь равны радиусам
                "outer_rx": outer_r, "outer_ry": outer_r,
                "inner_rx": inner_r, "inner_ry": inner_r 
                # Факторы яркости можно добавить, если они важны для __init__
            },
            "bbox_upscaled": [ # По внешнему кругу
                float(item_cx_upscaled - outer_r), float(item_cy_upscaled - outer_r),
                float(item_cx_upscaled + outer_r), float(item_cy_upscaled + outer_r)
            ]
        }]
    }
    # ... (остальная часть теста с mock_redis_client.get и service.verify_solution)
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x_orig, click_y_orig)
    assert is_valid is True, "Верификация должна быть успешной при клике на тело тора (круговая проекция)"


@pytest.mark.asyncio
async def test_create_challenge_with_cross_3d(mock_redis_client):
    model_name_to_test = "td_model"
    expected_shape_type = "cross_3d"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[5 % len(AVAILABLE_COLORS_GENERAL)]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type.replace("_", " ")) > 0

        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "arm_length" in shape_detail_dict["params_for_storage"]
        assert "arm_thickness" in shape_detail_dict["params_for_storage"]
        assert "depth_factor" in shape_detail_dict["params_for_storage"]

@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_cross_3d_face(mock_redis_client):
    model_name = "td_model"
    shape_type = "cross_3d"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_arm_length_upscaled = 60 * upscale_factor
    item_arm_thickness_upscaled = 20 * upscale_factor
    item_depth_factor = 0.3
    item_rotation_rad = 0.0 
    selected_color = AVAILABLE_COLORS_GENERAL[6 % len(AVAILABLE_COLORS_GENERAL)]

    # Клик в центр креста (должен попасть на переднюю грань)
    click_x = item_cx_upscaled // upscale_factor
    click_y = item_cy_upscaled // upscale_factor 
    
    half_len = item_arm_length_upscaled / 2.0
    # Примерный bbox
    bbox_calc = [
        float(item_cx_upscaled - half_len), float(item_cy_upscaled - half_len),
        float(item_cx_upscaled + half_len), float(item_cy_upscaled + half_len)
    ]
    
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "arm_length": item_arm_length_upscaled, 
                "arm_thickness": item_arm_thickness_upscaled,
                "depth_factor": item_depth_factor,
                "rotation_rad": item_rotation_rad
            },
            "bbox_upscaled": bbox_calc
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр передней грани 3D-креста"

@pytest.mark.asyncio
async def test_create_challenge_with_star5_3d(mock_redis_client):
    model_name_to_test = "td_model"
    expected_shape_type = "star5_3d"
    num_shapes_to_generate = 1
    selected_color = AVAILABLE_COLORS_GENERAL[0]

    mock_sample_side_effects = [[expected_shape_type], [selected_color]]
    with mock.patch('shape_captcha_lib.image_generator.random.sample', side_effect=mock_sample_side_effects):
        service = CaptchaChallengeService(
            redis_client=mock_redis_client, model_name=model_name_to_test,
            num_shapes_on_image=num_shapes_to_generate
        )
        assert expected_shape_type in service.current_model_shape_types
        captcha_id, _, prompt_text = await service.create_challenge()
        assert prompt_text.lower().count(expected_shape_type.replace("_", " ")) > 0

        mock_redis_client.set.assert_called_once()
        call_args_tuple = mock_redis_client.set.call_args.args
        redis_data_json_str = call_args_tuple[1]
        stored_data = json.loads(redis_data_json_str)
        assert stored_data["target_shape_type"] == expected_shape_type
        shape_detail_dict = stored_data["all_drawn_shapes"][0]
        assert shape_detail_dict["shape_type"] == expected_shape_type
        assert "outer_radius" in shape_detail_dict["params_for_storage"]
        assert "inner_radius" in shape_detail_dict["params_for_storage"]
        assert "depth_factor" in shape_detail_dict["params_for_storage"]


@pytest.mark.asyncio
async def test_verify_solution_correct_click_on_star5_3d_face(mock_redis_client):
    model_name = "td_model"
    shape_type = "star5_3d"
    captcha_id = uuid.uuid4().hex
    upscale_factor = DEFAULT_UPSCALE_FACTOR

    item_cx_upscaled = 200 * upscale_factor
    item_cy_upscaled = 150 * upscale_factor
    item_outer_radius_upscaled = 60 * upscale_factor
    item_inner_radius_upscaled = 30 * upscale_factor # inner < outer
    item_depth_factor = 0.2
    item_rotation_rad = 0.0 
    selected_color = AVAILABLE_COLORS_GENERAL[1]

    # Клик в центр звезды (должен попасть на переднюю грань)
    click_x = item_cx_upscaled // upscale_factor
    click_y = item_cy_upscaled // upscale_factor 
    
    # Примерный bbox
    bbox_calc = [
        float(item_cx_upscaled - item_outer_radius_upscaled), 
        float(item_cy_upscaled - item_outer_radius_upscaled),
        float(item_cx_upscaled + item_outer_radius_upscaled), 
        float(item_cy_upscaled + item_outer_radius_upscaled)
    ]
    
    stored_challenge_data = {
        "target_shape_type": shape_type,
        "all_drawn_shapes": [{
            "shape_type": shape_type, "color_name_or_rgb": selected_color,
            "params_for_storage": {
                "cx": item_cx_upscaled, "cy": item_cy_upscaled,
                "outer_radius": item_outer_radius_upscaled, 
                "inner_radius": item_inner_radius_upscaled,
                "depth_factor": item_depth_factor,
                "rotation_rad": item_rotation_rad
            },
            "bbox_upscaled": bbox_calc
        }]
    }
    mock_redis_client.get.return_value = json.dumps(stored_challenge_data)
    service = CaptchaChallengeService(
        redis_client=mock_redis_client, model_name=model_name,
        captcha_upscale_factor=upscale_factor
    )
    is_valid = await service.verify_solution(captcha_id, click_x, click_y)
    assert is_valid is True, "Верификация должна быть успешной при клике в центр передней грани 3D-звезды"

