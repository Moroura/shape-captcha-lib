# tests/conftest.py
import pytest_asyncio # Для асинхронных фикстур
from unittest import mock
import redis.asyncio as redis # Для типизации мока

@pytest_asyncio.fixture
async def mock_redis_client():
    # Создаем AsyncMock, имитирующий redis.asyncio.Redis
    client = mock.AsyncMock(spec=redis.Redis) # Используем spec для большей точности мока
    # Мокируем методы, которые использует CaptchaChallengeService
    client.set = mock.AsyncMock(return_value=True)
    client.get = mock.AsyncMock(return_value=None) # По умолчанию get ничего не находит
    client.delete = mock.AsyncMock(return_value=1) # delete обычно возвращает кол-во удаленных ключей
    # Если CaptchaChallengeService вызывает client.ping() при инициализации, его тоже нужно замокать:
    # client.ping = mock.AsyncMock(return_value=True)
    return client