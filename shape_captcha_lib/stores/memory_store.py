# shape_captcha_lib/stores/memory_store.py
import time
import asyncio # Для AsyncInMemoryStore
import random # Для периодической очистки
from typing import Dict, Any, Optional, Tuple

from .abc_store import AbstractSyncCaptchaStore, AbstractAsyncCaptchaStore

import logging
logger = logging.getLogger(__name__)

class SyncInMemoryStore(AbstractSyncCaptchaStore):
    """
    Синхронное хранилище состояний CAPTCHA в памяти.
    Управляет временем жизни (TTL) записей.
    """
    def __init__(self):
        self._store: Dict[str, Tuple[Dict[str, Any], float]] = {}
        # Для SyncInMemoryStore блокировка (threading.Lock) может понадобиться,
        # если один экземпляр используется несколькими потоками.
        # Для простоты здесь не используется.

    def _cleanup_expired(self):
        """Внутренний метод для удаления истекших записей."""
        current_time = time.monotonic()
        # Чтобы избежать изменения словаря во время итерации, сначала собираем ключи
        expired_keys = [
            key for key, (_, expiration_time) in self._store.items()
            if current_time >= expiration_time
        ]
        for key in expired_keys:
            self._store.pop(key, None)
            logger.debug(f"SyncInMemoryStore: Removed expired challenge_id: {key}")

    def store_challenge(self, challenge_id: str, data: Dict[str, Any], ttl_seconds: int) -> None:
        if random.random() < 0.1: # Вероятность очистки 10% при каждой записи
             self._cleanup_expired()

        expiration_time = time.monotonic() + ttl_seconds
        self._store[challenge_id] = (data, expiration_time)
        logger.debug(f"SyncInMemoryStore: Stored challenge_id: {challenge_id}, expires at {expiration_time:.2f}")

    def retrieve_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        stored_item = self._store.get(challenge_id)
        if stored_item:
            data, expiration_time = stored_item
            if time.monotonic() < expiration_time:
                logger.debug(f"SyncInMemoryStore: Retrieved challenge_id: {challenge_id}")
                return data
            else:
                logger.debug(f"SyncInMemoryStore: Challenge_id: {challenge_id} found but expired. Deleting.")
                self._store.pop(challenge_id, None)
        else:
            logger.debug(f"SyncInMemoryStore: Challenge_id: {challenge_id} not found.")
        return None

    def delete_challenge(self, challenge_id: str) -> None:
        if self._store.pop(challenge_id, None):
            logger.debug(f"SyncInMemoryStore: Deleted challenge_id: {challenge_id}")
        else:
            logger.debug(f"SyncInMemoryStore: Attempted to delete non-existent challenge_id: {challenge_id}")

    def close(self) -> None:
        logger.debug("SyncInMemoryStore: Close called (no-op).")
        pass


class AsyncInMemoryStore(AbstractAsyncCaptchaStore):
    """
    Асинхронное хранилище состояний CAPTCHA в памяти.
    Управляет временем жизни (TTL) записей и использует asyncio.Lock.
    """
    def __init__(self):
        self._store: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._lock = asyncio.Lock()

    async def _cleanup_expired_async(self):
        """Асинхронный метод для удаления истекших записей."""
        current_time = time.monotonic()
        expired_keys = []
        # Собираем ключи под блокировкой, чтобы избежать проблем с изменением словаря во время итерации
        async with self._lock:
            for key, (_, expiration_time) in self._store.items():
                if current_time >= expiration_time:
                    expired_keys.append(key)
            for key in expired_keys:
                self._store.pop(key, None)
                logger.debug(f"AsyncInMemoryStore: Removed expired challenge_id: {key}")

    async def store_challenge(self, challenge_id: str, data: Dict[str, Any], ttl_seconds: int) -> None:
        if random.random() < 0.1: # Вероятность очистки 10%
            await self._cleanup_expired_async()
            
        expiration_time = time.monotonic() + ttl_seconds
        async with self._lock:
            self._store[challenge_id] = (data, expiration_time)
        logger.debug(f"AsyncInMemoryStore: Stored challenge_id: {challenge_id}, expires at {expiration_time:.2f}")

    async def retrieve_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            stored_item = self._store.get(challenge_id)
            if stored_item:
                data, expiration_time = stored_item
                if time.monotonic() < expiration_time:
                    logger.debug(f"AsyncInMemoryStore: Retrieved challenge_id: {challenge_id}")
                    return data
                else:
                    # Запись истекла, удаляем ее (уже под блокировкой)
                    logger.debug(f"AsyncInMemoryStore: Challenge_id: {challenge_id} found but expired. Deleting.")
                    self._store.pop(challenge_id, None)
            else:
                logger.debug(f"AsyncInMemoryStore: Challenge_id: {challenge_id} not found.")
        return None

    async def delete_challenge(self, challenge_id: str) -> None:
        async with self._lock:
            if self._store.pop(challenge_id, None):
                logger.debug(f"AsyncInMemoryStore: Deleted challenge_id: {challenge_id}")
            else:
                logger.debug(f"AsyncInMemoryStore: Attempted to delete non-existent challenge_id: {challenge_id}")

    async def close(self) -> None:
        logger.debug("AsyncInMemoryStore: Close called (no-op).")
        pass