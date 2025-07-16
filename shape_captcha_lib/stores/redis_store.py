# shape_captcha_lib/stores/redis_store.py
import json
from typing import Dict, Any, Optional

# Клиенты Redis
import redis # Для синхронной версии
import redis.asyncio as redis_async # Для асинхронной версии

from .abc_store import AbstractSyncCaptchaStore, AbstractAsyncCaptchaStore

import logging
logger = logging.getLogger(__name__)

DEFAULT_REDIS_KEY_PREFIX = "captcha_challenge:"


class SyncRedisStore(AbstractSyncCaptchaStore):
    """
    Синхронное хранилище состояний CAPTCHA в Redis.
    Использует встроенный TTL Redis.
    """
    def __init__(self, redis_client: redis.Redis, key_prefix: str = DEFAULT_REDIS_KEY_PREFIX):
        if not isinstance(redis_client, redis.Redis):
            raise TypeError("redis_client must be an instance of redis.Redis for SyncRedisStore.")
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        logger.info(f"SyncRedisStore initialized with key prefix: '{key_prefix}'")

    def _get_redis_key(self, challenge_id: str) -> str:
        return f"{self.key_prefix}{challenge_id}"

    def store_challenge(self, challenge_id: str, data: Dict[str, Any], ttl_seconds: int) -> None:
        redis_key = self._get_redis_key(challenge_id)
        try:
            json_data = json.dumps(data)
            self.redis_client.set(redis_key, json_data, ex=ttl_seconds)
            logger.debug(f"SyncRedisStore: Stored challenge_id: {challenge_id} (key: {redis_key}) with TTL: {ttl_seconds}s")
        except redis.RedisError as e:
            logger.error(f"SyncRedisStore: Failed to store challenge {challenge_id} in Redis: {e}")
            raise ConnectionError(f"Failed to store CAPTCHA data in Redis: {e}")
        except json.JSONEncodeError as e_json:
            logger.error(f"SyncRedisStore: Failed to serialize data for challenge {challenge_id}: {e_json}")
            raise TypeError(f"Data for CAPTCHA challenge {challenge_id} is not JSON serializable.")

    def retrieve_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        redis_key = self._get_redis_key(challenge_id)
        try:
            stored_data_json = self.redis_client.get(redis_key)
            if stored_data_json:
                logger.debug(f"SyncRedisStore: Retrieved raw data for key: {redis_key}")
                # stored_data_json может быть bytes или str в зависимости от клиента Redis (decode_responses)
                # json.loads корректно обработает и то, и другое.
                return json.loads(stored_data_json)
            logger.debug(f"SyncRedisStore: No data found for key: {redis_key}")
            return None
        except redis.RedisError as e:
            logger.error(f"SyncRedisStore: Failed to retrieve challenge {challenge_id} from Redis: {e}")
            return None 
        except json.JSONDecodeError as e_json:
            logger.warning(f"SyncRedisStore: JSON decode error for challenge {challenge_id}. Key: {redis_key}. Error: {e_json}")
            return None

    def delete_challenge(self, challenge_id: str) -> None:
        redis_key = self._get_redis_key(challenge_id)
        try:
            deleted_count = self.redis_client.delete(redis_key)
            if deleted_count > 0:
                logger.debug(f"SyncRedisStore: Deleted challenge_id: {challenge_id} (key: {redis_key})")
            else:
                logger.debug(f"SyncRedisStore: Attempted to delete non-existent key: {redis_key}")
        except redis.RedisError as e:
            logger.error(f"SyncRedisStore: Failed to delete challenge {challenge_id} from Redis: {e}")

    def close(self) -> None:
        """
        Закрытие соединения Redis обычно управляется извне кодом, который создал и передал redis_client.
        Этот метод предоставляется для соответствия интерфейсу AbstractSyncCaptchaStore.
        Если предполагается, что этот класс должен управлять жизненным циклом соединения,
        здесь должна быть логика его закрытия (например, self.redis_client.close()),
        но это нетипично, если клиент инжектируется.
        """
        logger.debug("SyncRedisStore: Close called. Client connection is typically managed externally.")
        pass


class AsyncRedisStore(AbstractAsyncCaptchaStore):
    """
    Асинхронное хранилище состояний CAPTCHA в Redis.
    """
    def __init__(self, redis_client: redis_async.Redis, key_prefix: str = DEFAULT_REDIS_KEY_PREFIX):
        if not isinstance(redis_client, redis_async.Redis):
            raise TypeError("redis_client must be an instance of redis.asyncio.Redis for AsyncRedisStore.")
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        logger.info(f"AsyncRedisStore initialized with key prefix: '{key_prefix}'")

    def _get_redis_key(self, challenge_id: str) -> str:
        return f"{self.key_prefix}{challenge_id}"

    async def store_challenge(self, challenge_id: str, data: Dict[str, Any], ttl_seconds: int) -> None:
        redis_key = self._get_redis_key(challenge_id)
        try:
            json_data = json.dumps(data)
            await self.redis_client.set(redis_key, json_data, ex=ttl_seconds)
            logger.debug(f"AsyncRedisStore: Stored challenge_id: {challenge_id} (key: {redis_key}) with TTL: {ttl_seconds}s")
        except redis.RedisError as e:
            logger.error(f"AsyncRedisStore: Failed to store challenge {challenge_id} in Redis: {e}")
            raise ConnectionError(f"Failed to store CAPTCHA data in Redis: {e}")
        except json.JSONEncodeError as e_json:
            logger.error(f"AsyncRedisStore: Failed to serialize data for challenge {challenge_id}: {e_json}")
            raise TypeError(f"Data for CAPTCHA challenge {challenge_id} is not JSON serializable.")

    async def retrieve_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        redis_key = self._get_redis_key(challenge_id)
        try:
            stored_data_json = await self.redis_client.get(redis_key)
            if stored_data_json:
                logger.debug(f"AsyncRedisStore: Retrieved raw data for key: {redis_key}")
                return json.loads(stored_data_json) # json.loads может принимать bytes
            logger.debug(f"AsyncRedisStore: No data found for key: {redis_key}")
            return None
        except redis.RedisError as e:
            logger.error(f"AsyncRedisStore: Failed to retrieve challenge {challenge_id} from Redis: {e}")
            return None
        except json.JSONDecodeError as e_json:
            logger.warning(f"AsyncRedisStore: JSON decode error for challenge {challenge_id}. Key: {redis_key}. Error: {e_json}")
            return None

    async def delete_challenge(self, challenge_id: str) -> None:
        redis_key = self._get_redis_key(challenge_id)
        try:
            deleted_count = await self.redis_client.delete(redis_key)
            if deleted_count > 0: # type: ignore # delete returns int
                logger.debug(f"AsyncRedisStore: Deleted challenge_id: {challenge_id} (key: {redis_key})")
            else:
                logger.debug(f"AsyncRedisStore: Attempted to delete non-existent key: {redis_key}")
        except redis.RedisError as e:
            logger.error(f"AsyncRedisStore: Failed to delete challenge {challenge_id} from Redis: {e}")

    async def close(self) -> None:
        """
        Закрытие соединения Redis обычно управляется извне кодом, который создал и передал redis_client.
        Этот метод предоставляется для соответствия интерфейсу AbstractAsyncCaptchaStore.
        
        Если клиент redis-py (redis.asyncio.Redis) был создан с пулом соединений,
        то client.close() просто возвращает соединение в пул.
        Для закрытия самого пула используется pool.disconnect() или pool.aclose() в новых версиях.
        Поскольку здесь мы получаем уже созданный клиент, мы не управляем его пулом напрямую.
        """
        logger.debug("AsyncRedisStore: Close called. Client connection is typically managed externally.")
        # Если бы требовалось явное закрытие соединения, которое было установлено этим экземпляром:
        # if hasattr(self.redis_client, "close") and callable(self.redis_client.close):
        #     try:
        #         if asyncio.iscoroutinefunction(self.redis_client.close):
        #             await self.redis_client.close()
        #             if hasattr(self.redis_client, "wait_closed") and \
        #                asyncio.iscoroutinefunction(self.redis_client.wait_closed):
        #                 await self.redis_client.wait_closed() # Для redis-py >= 4.0
        #         else:
        #             self.redis_client.close() # Для очень старых версий или кастомных клиентов
        #         logger.info("AsyncRedisStore: Redis client close method was called.")
        #     except Exception as e:
        #         logger.error(f"AsyncRedisStore: Error during explicit client close: {e}")
        pass