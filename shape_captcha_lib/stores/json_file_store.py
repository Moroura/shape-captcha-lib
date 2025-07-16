# shape_captcha_lib/stores/json_file_store.py
import json
import time
import os
import random
from pathlib import Path
from typing import Dict, Any, Optional, Union # Добавил Union

# Для асинхронной версии
import aiofiles
import asyncio

from .abc_store import AbstractSyncCaptchaStore, AbstractAsyncCaptchaStore

import logging
logger = logging.getLogger(__name__)

DEFAULT_STORE_DIR = "captcha_store_data"


class SyncJsonFileStore(AbstractSyncCaptchaStore):
    """
    Синхронное хранилище состояний CAPTCHA в JSON-файлах.
    Управляет TTL через временные метки в файлах.
    """
    def __init__(self, store_directory: Union[str, Path] = DEFAULT_STORE_DIR):
        self.store_path = Path(store_directory)
        try:
            self.store_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"SyncJsonFileStore: Using store directory: {self.store_path.resolve()}")
        except OSError as e:
            logger.error(f"SyncJsonFileStore: Failed to create CAPTCHA store directory {self.store_path}: {e}")
            raise
        self._file_extension = ".json"

    def _get_file_path(self, challenge_id: str) -> Path:
        return self.store_path / f"{challenge_id}{self._file_extension}"

    def _cleanup_one_expired_file(self) -> None:
        """Удаляет один случайный истекший файл. Вызывается с некоторой вероятностью."""
        try:
            # Получаем список всех .json файлов в директории
            # os.listdir() может быть более эффективным для большого кол-ва файлов, чем glob
            file_names = [f for f in os.listdir(self.store_path) if f.endswith(self._file_extension)]
            if not file_names:
                return
            
            random_file_name = random.choice(file_names)
            random_file_path = self.store_path / random_file_name
            
            try:
                with open(random_file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                
                expiration_time = content.get("expiration_timestamp_monotonic")
                if expiration_time and time.monotonic() >= expiration_time:
                    logger.debug(f"SyncJsonFileStore: Cleaning up expired file {random_file_path}")
                    os.remove(random_file_path)
            except FileNotFoundError:
                logger.debug(f"SyncJsonFileStore: File {random_file_path} not found during cleanup (possibly already deleted).")
            except (json.JSONDecodeError, KeyError) as e_parse:
                logger.warning(f"SyncJsonFileStore: Error parsing or missing key in {random_file_path} during cleanup: {e_parse}. Deleting file.")
                try:
                    os.remove(random_file_path) # Удаляем поврежденный/невалидный файл
                except OSError as e_rm:
                    logger.warning(f"SyncJsonFileStore: Failed to remove problematic file {random_file_path} during cleanup: {e_rm}")
            except OSError as e_os:
                 logger.warning(f"SyncJsonFileStore: OS error during cleanup of {random_file_path}: {e_os}")
            except Exception as e:
                 logger.warning(f"SyncJsonFileStore: Unexpected error during cleanup of {random_file_path}: {e}")

        except Exception as e: # Ошибки листинга директории и т.п.
            logger.warning(f"SyncJsonFileStore: General error during cleanup attempt: {e}")

    def store_challenge(self, challenge_id: str, data: Dict[str, Any], ttl_seconds: int) -> None:
        if random.random() < 0.05: # Вероятность очистки 5%
            self._cleanup_one_expired_file()

        file_path = self._get_file_path(challenge_id)
        expiration_time = time.monotonic() + ttl_seconds
        content_to_store = {
            "challenge_data": data,
            "expiration_timestamp_monotonic": expiration_time
        }
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(content_to_store, f, ensure_ascii=False, indent=None)
            logger.debug(f"SyncJsonFileStore: Stored challenge_id: {challenge_id} at {file_path}")
        except IOError as e:
            logger.error(f"SyncJsonFileStore: Failed to write to {file_path}: {e}")
            raise ConnectionError(f"Failed to write CAPTCHA data to file store: {e}")

    def retrieve_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        file_path = self._get_file_path(challenge_id)
        if not file_path.exists():
            logger.debug(f"SyncJsonFileStore: Challenge_id: {challenge_id} (file {file_path}) not found.")
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            
            expiration_time = content.get("expiration_timestamp_monotonic")
            challenge_data = content.get("challenge_data")

            if expiration_time is None or challenge_data is None:
                logger.warning(f"SyncJsonFileStore: Invalid content in {file_path}. Deleting.")
                self.delete_challenge(challenge_id)
                return None

            if time.monotonic() < expiration_time:
                logger.debug(f"SyncJsonFileStore: Retrieved challenge_id: {challenge_id} from {file_path}")
                return challenge_data
            else:
                logger.debug(f"SyncJsonFileStore: Challenge {challenge_id} expired. Deleting file {file_path}.")
                self.delete_challenge(challenge_id)
                return None
        except json.JSONDecodeError as e:
            logger.warning(f"SyncJsonFileStore: JSON decode error for {file_path}: {e}. Deleting file.")
            self.delete_challenge(challenge_id)
            return None
        except IOError as e:
            logger.error(f"SyncJsonFileStore: Failed to read from {file_path}: {e}")
            return None

    def delete_challenge(self, challenge_id: str) -> None:
        file_path = self._get_file_path(challenge_id)
        try:
            if file_path.exists():
                os.remove(file_path)
                logger.debug(f"SyncJsonFileStore: Deleted challenge_id: {challenge_id} (file {file_path})")
            else:
                logger.debug(f"SyncJsonFileStore: Attempted to delete non-existent file for challenge_id: {challenge_id} (file {file_path})")
        except OSError as e:
            logger.error(f"SyncJsonFileStore: Failed to delete {file_path}: {e}")

    def close(self) -> None:
        logger.debug("SyncJsonFileStore: Close called (no-op).")
        pass


class AsyncJsonFileStore(AbstractAsyncCaptchaStore):
    """
    Асинхронное хранилище состояний CAPTCHA в JSON-файлах.
    """
    def __init__(self, store_directory: Union[str, Path] = DEFAULT_STORE_DIR):
        self.store_path = Path(store_directory)
        if not self.store_path.exists():
            try:
                self.store_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"AsyncJsonFileStore: Using store directory: {self.store_path.resolve()}")
            except OSError as e:
                logger.error(f"AsyncJsonFileStore: Failed to create CAPTCHA store directory {self.store_path} (sync attempt): {e}")
                raise
        
        self._file_extension = ".json"
        self._lock = asyncio.Lock()

    def _get_file_path(self, challenge_id: str) -> Path:
        return self.store_path / f"{challenge_id}{self._file_extension}"

    async def _cleanup_one_expired_file_async(self) -> None:
        # Блокировка нужна для синхронизации доступа к ФС, если эта функция может вызываться конкурентно
        async with self._lock:
            try:
                # Синхронный листинг директории, т.к. aiofiles не предоставляет асинхронный listdir
                # Для очень больших директорий это может быть проблемой в асинхронном контексте.
                # В реальном приложении это лучше делать в отдельном потоке (executor).
                try:
                    file_names = await asyncio.to_thread(os.listdir, self.store_path)
                except OSError:
                    logger.warning(f"AsyncJsonFileStore: Could not list directory {self.store_path} for cleanup.")
                    return

                json_file_names = [f_name for f_name in file_names if f_name.endswith(self._file_extension)]
                if not json_file_names:
                    return
                
                random_file_name = random.choice(json_file_names)
                random_file_path = self.store_path / random_file_name
                
                try:
                    async with aiofiles.open(random_file_path, mode='r', encoding='utf-8') as f:
                        content_str = await f.read()
                    content = json.loads(content_str)
                    
                    expiration_time = content.get("expiration_timestamp_monotonic")
                    if expiration_time and time.monotonic() >= expiration_time:
                        logger.debug(f"AsyncJsonFileStore: Cleaning up expired file {random_file_path}")
                        # Используем asyncio.to_thread для синхронной операции удаления файла
                        await asyncio.to_thread(os.remove, random_file_path)
                except FileNotFoundError:
                    logger.debug(f"AsyncJsonFileStore: File {random_file_path} not found during cleanup (possibly already deleted).")
                except (json.JSONDecodeError, KeyError) as e_parse:
                    logger.warning(f"AsyncJsonFileStore: Error parsing or missing key in {random_file_path} during cleanup: {e_parse}. Deleting file.")
                    try:
                        await asyncio.to_thread(os.remove, random_file_path)
                    except OSError as e_rm:
                        logger.warning(f"AsyncJsonFileStore: Failed to remove problematic file {random_file_path} during cleanup: {e_rm}")
                except OSError as e_os:
                     logger.warning(f"AsyncJsonFileStore: OS error during cleanup of {random_file_path}: {e_os}")
                except Exception as e_clean_inner:
                     logger.warning(f"AsyncJsonFileStore: Unexpected inner error during cleanup of {random_file_path}: {e_clean_inner}")
            except Exception as e_clean_outer: # Ошибки при работе с блокировкой или внешние ошибки
                logger.warning(f"AsyncJsonFileStore: General error during cleanup attempt: {e_clean_outer}")

    async def store_challenge(self, challenge_id: str, data: Dict[str, Any], ttl_seconds: int) -> None:
        if random.random() < 0.05:
            await self._cleanup_one_expired_file_async()

        file_path = self._get_file_path(challenge_id)
        expiration_time = time.monotonic() + ttl_seconds
        content_to_store = {
            "challenge_data": data,
            "expiration_timestamp_monotonic": expiration_time
        }
        # Сериализация в JSON может быть блокирующей для очень больших данных,
        # но обычно она достаточно быстра. При необходимости можно вынести в to_thread.
        json_string = json.dumps(content_to_store, ensure_ascii=False, indent=None)

        async with self._lock:
            try:
                async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                    await f.write(json_string)
                logger.debug(f"AsyncJsonFileStore: Stored challenge_id: {challenge_id} at {file_path}")
            except IOError as e: # aiofiles может бросать стандартные IOError/OSError
                logger.error(f"AsyncJsonFileStore: Failed to write to {file_path}: {e}")
                raise ConnectionError(f"Failed to write CAPTCHA data to file store: {e}")

    async def retrieve_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        file_path = self._get_file_path(challenge_id)
        
        # Проверка существования файла асинхронно (если есть aiopathlib или подобное)
        # Для простоты и совместимости, используем блокирующий os.path.exists, но он быстрый.
        # Либо обернуть в asyncio.to_thread:
        try:
            exists = await asyncio.to_thread(file_path.exists)
            if not exists:
                logger.debug(f"AsyncJsonFileStore: Challenge_id: {challenge_id} (file {file_path}) not found.")
                return None
        except Exception as e_exists: # На случай ошибок в to_thread или file_path
            logger.error(f"AsyncJsonFileStore: Error checking existence of {file_path}: {e_exists}")
            return None # Считаем, что файл недоступен
            
        async with self._lock:
            try:
                async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                    content_str = await f.read()
                content = json.loads(content_str) # Десериализация также может быть вынесена в to_thread
                
                expiration_time = content.get("expiration_timestamp_monotonic")
                challenge_data = content.get("challenge_data")

                if expiration_time is None or challenge_data is None:
                    logger.warning(f"AsyncJsonFileStore: Invalid content in {file_path}. Deleting.")
                    try:
                        await asyncio.to_thread(os.remove, file_path)
                    except OSError: pass
                    return None

                if time.monotonic() < expiration_time:
                    logger.debug(f"AsyncJsonFileStore: Retrieved challenge_id: {challenge_id} from {file_path}")
                    return challenge_data
                else:
                    logger.debug(f"AsyncJsonFileStore: Challenge {challenge_id} expired. Deleting file {file_path}.")
                    try:
                        await asyncio.to_thread(os.remove, file_path)
                    except OSError: pass
                    return None
            except FileNotFoundError: # Файл мог быть удален между проверкой exists() и open() без блокировки на всё
                logger.debug(f"AsyncJsonFileStore: File {file_path} disappeared before reading.")
                return None
            except json.JSONDecodeError as e:
                logger.warning(f"AsyncJsonFileStore: JSON decode error for {file_path}: {e}. Deleting file.")
                try:
                    await asyncio.to_thread(os.remove, file_path)
                except OSError: pass
                return None
            except IOError as e:
                logger.error(f"AsyncJsonFileStore: Failed to read from {file_path}: {e}")
                return None

    async def delete_challenge(self, challenge_id: str) -> None:
        file_path = self._get_file_path(challenge_id)
        async with self._lock:
            try:
                exists = await asyncio.to_thread(file_path.exists)
                if exists:
                    await asyncio.to_thread(os.remove, file_path)
                    logger.debug(f"AsyncJsonFileStore: Deleted challenge_id: {challenge_id} (file {file_path})")
                else:
                    logger.debug(f"AsyncJsonFileStore: Attempted to delete non-existent file for challenge_id: {challenge_id} (file {file_path})")
            except OSError as e:
                logger.error(f"AsyncJsonFileStore: Failed to delete {file_path}: {e}")

    async def close(self) -> None:
        logger.debug("AsyncJsonFileStore: Close called (no-op).")
        pass