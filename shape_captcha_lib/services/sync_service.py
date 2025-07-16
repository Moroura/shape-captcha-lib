# shape_captcha_lib/services/sync_service.py
import uuid
from typing import Tuple, Optional
import logging

from PIL.Image import Image as PILImage

from ..logic_core import CaptchaLogicCore
from ..stores.abc_store import AbstractSyncCaptchaStore
# Аналогично AsyncService, определяем DEFAULT_CAPTCHA_TTL_SECONDS
try:
    from ..settings import DEFAULT_CAPTCHA_TTL_SECONDS
except ImportError:
    DEFAULT_CAPTCHA_TTL_SECONDS = 300

logger = logging.getLogger(__name__)


class SyncCaptchaChallengeService:
    def __init__(
        self,
        logic_core: CaptchaLogicCore,
        captcha_store: AbstractSyncCaptchaStore,
        captcha_ttl_seconds: int = DEFAULT_CAPTCHA_TTL_SECONDS
    ):
        if not isinstance(logic_core, CaptchaLogicCore):
            raise TypeError("logic_core must be an instance of CaptchaLogicCore")
        if not isinstance(captcha_store, AbstractSyncCaptchaStore):
            raise TypeError("captcha_store must be an instance of AbstractSyncCaptchaStore")

        self.logic_core = logic_core
        self.store = captcha_store
        self.captcha_ttl = captcha_ttl_seconds

    def create_challenge(self, language_code: Optional[str] = None) -> Tuple[str, PILImage, str]: # <--- ДОБАВЛЕН language_code
        """
        Создает новый CAPTCHA "вызов".

        Args:
            language_code (Optional[str]): Предпочитаемый код языка для подсказки.
        # ... (остальные докстринги)
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
            "target_shape_type": target_type, # target_type здесь это ключ
            "all_drawn_shapes": drawn_shapes_list
        }

        try:
            self.store.store_challenge(captcha_id, challenge_data_to_store, self.captcha_ttl)
            lang_used = language_code or (self.logic_core.default_language if self.logic_core else 'default')
            logger.info(f"SyncService: CAPTCHA challenge {captcha_id} (target: {target_type}, lang: {lang_used}) stored.")
        except Exception as e_store:
            logger.error(f"SyncService: Error saving CAPTCHA data for ID {captcha_id}: {e_store}", exc_info=True)
            raise ConnectionError(f"Could not save CAPTCHA challenge to store: {e_store}")
            
        return captcha_id, image_obj, prompt

    def verify_solution(self, captcha_id: str, click_x: int, click_y: int) -> bool:
        """
        Проверяет решение пользователя.
        """
        challenge_data: Optional[dict]
        try:
            challenge_data = self.store.retrieve_challenge(captcha_id)
        except Exception as e_retrieve:
            logger.error(f"SyncService: Error retrieving CAPTCHA data for ID {captcha_id}: {e_retrieve}", exc_info=True)
            return False

        if not challenge_data:
            logger.warning(f"SyncService: CAPTCHA ID {captcha_id} not found or expired.")
            return False
        
        try:
            self.store.delete_challenge(captcha_id)
            logger.debug(f"SyncService: CAPTCHA ID {captcha_id} deleted from store after retrieval.")
        except Exception as e_delete:
            logger.error(f"SyncService: CRITICAL - Failed to delete CAPTCHA ID {captcha_id} after retrieval: {e_delete}", exc_info=True)

        target_shape_type = challenge_data.get("target_shape_type")
        all_drawn_shapes = challenge_data.get("all_drawn_shapes")

        if not target_shape_type or not isinstance(all_drawn_shapes, list):
            logger.warning(f"SyncService: Invalid data structure retrieved for CAPTCHA {captcha_id}.")
            return False

        try:
            is_correct = self.logic_core.verify_solution(
                click_x=click_x,
                click_y=click_y,
                target_shape_type_from_challenge=target_shape_type,
                all_drawn_shapes_data=all_drawn_shapes
            )
            logger.info(f"SyncService: CAPTCHA ID {captcha_id} verification result: {is_correct}")
            return is_correct
        except Exception as e_verify:
            logger.error(f"SyncService: Error during CAPTCHA verification logic for ID {captcha_id}: {e_verify}", exc_info=True)
            return False

    def close_store(self) -> None:
        """Закрывает соединение с хранилищем, если это необходимо."""
        if hasattr(self.store, "close") and callable(self.store.close):
            self.store.close() # type: ignore # Игнорируем, т.к. callable уже проверен
            logger.info("SyncService: Captcha store closed.")