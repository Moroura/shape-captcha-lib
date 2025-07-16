# shape_captcha_lib/services/async_service.py
import uuid
from typing import Tuple, Optional
import logging

from PIL.Image import Image as PILImage

from ..logic_core import CaptchaLogicCore
from ..stores.abc_store import AbstractAsyncCaptchaStore
# Предполагается, что DEFAULT_CAPTCHA_TTL_SECONDS определена где-то,
# например, в settings.py или будет передана явно.
# Если нет settings.py, можно определить здесь:
# DEFAULT_CAPTCHA_TTL_SECONDS = 300

try:
    from ..settings import DEFAULT_CAPTCHA_TTL_SECONDS
except ImportError:
    DEFAULT_CAPTCHA_TTL_SECONDS = 300  # Значение по умолчанию, если settings.py нет

logger = logging.getLogger(__name__)


class AsyncCaptchaChallengeService:
    def __init__(
        self,
        logic_core: CaptchaLogicCore,
        captcha_store: AbstractAsyncCaptchaStore,
        captcha_ttl_seconds: int = DEFAULT_CAPTCHA_TTL_SECONDS
    ):
        if not isinstance(logic_core, CaptchaLogicCore):
            raise TypeError("logic_core must be an instance of CaptchaLogicCore")
        if not isinstance(captcha_store, AbstractAsyncCaptchaStore):
            raise TypeError("captcha_store must be an instance of AbstractAsyncCaptchaStore")

        self.logic_core = logic_core
        self.store = captcha_store
        self.captcha_ttl = captcha_ttl_seconds

    async def create_challenge(self, language_code: Optional[str] = None) -> Tuple[str, PILImage, str]: 
        """
        Создает новый CAPTCHA "вызов".

        Returns:
            Кортеж (captcha_id, image_object, prompt_text).
        Raises:
            ValueError: Если не удалось сгенерировать CAPTCHA.
            ConnectionError: Если есть проблемы с сохранением в хранилище.
        """
        try:
            # language_code передается в logic_core
            image_obj, drawn_shapes_list, target_type, prompt = self.logic_core.generate_challenge_data(
                language_code=language_code
            )
        except Exception as e:
            logger.error(f"Error generating CAPTCHA data via logic_core: {e}", exc_info=True)
            raise ValueError(f"Failed to generate CAPTCHA challenge: {e}")

        captcha_id = uuid.uuid4().hex
        challenge_data_to_store = {
            "target_shape_type": target_type, # target_type здесь это ключ для перевода, а не переведенное имя
            "all_drawn_shapes": drawn_shapes_list
        }

        try:
            await self.store.store_challenge(captcha_id, challenge_data_to_store, self.captcha_ttl)
            # Добавим язык в лог для отладки
            lang_used = language_code or (self.logic_core.default_language if self.logic_core else 'default')
            logger.info(f"AsyncService: CAPTCHA challenge {captcha_id} (target: {target_type}, lang: {lang_used}) stored.")
        except Exception as e_store:
            logger.error(f"AsyncService: Error saving CAPTCHA data for ID {captcha_id}: {e_store}", exc_info=True)
            raise ConnectionError(f"Could not save CAPTCHA challenge to store: {e_store}")

        return captcha_id, image_obj, prompt

    async def verify_solution(self, captcha_id: str, click_x: int, click_y: int) -> bool:
        """
        Проверяет решение пользователя.
        """
        challenge_data: Optional[dict]
        try:
            challenge_data = await self.store.retrieve_challenge(captcha_id)
        except Exception as e_retrieve:
            logger.error(f"AsyncService: Error retrieving CAPTCHA data for ID {captcha_id}: {e_retrieve}", exc_info=True)
            return False

        if not challenge_data:
            logger.warning(f"AsyncService: CAPTCHA ID {captcha_id} not found or expired.")
            return False

        try:
            await self.store.delete_challenge(captcha_id)
            logger.debug(f"AsyncService: CAPTCHA ID {captcha_id} deleted from store after retrieval.")
        except Exception as e_delete:
            logger.error(f"AsyncService: CRITICAL - Failed to delete CAPTCHA ID {captcha_id} after retrieval: {e_delete}", exc_info=True)

        target_shape_type = challenge_data.get("target_shape_type")
        all_drawn_shapes = challenge_data.get("all_drawn_shapes")

        if not target_shape_type or not isinstance(all_drawn_shapes, list):
            logger.warning(f"AsyncService: Invalid data structure retrieved for CAPTCHA {captcha_id}.")
            return False

        try:
            is_correct = self.logic_core.verify_solution(
                click_x=click_x,
                click_y=click_y,
                target_shape_type_from_challenge=target_shape_type,
                all_drawn_shapes_data=all_drawn_shapes
            )
            logger.info(f"AsyncService: CAPTCHA ID {captcha_id} verification result: {is_correct}")
            return is_correct
        except Exception as e_verify:
            logger.error(f"AsyncService: Error during CAPTCHA verification logic for ID {captcha_id}: {e_verify}", exc_info=True)
            return False

    async def close_store(self) -> None:
        """Закрывает соединение с хранилищем, если это необходимо."""
        if hasattr(self.store, "close") and callable(self.store.close):
            await self.store.close()
            logger.info("AsyncService: Captcha store closed.")