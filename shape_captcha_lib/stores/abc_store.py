# shape_captcha_lib/stores/abc_store.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class AbstractAsyncCaptchaStore(ABC):
    """
    Абстрактный базовый класс для асинхронного хранилища состояний CAPTCHA.
    """

    @abstractmethod
    async def store_challenge(self, challenge_id: str, data: Dict[str, Any], ttl_seconds: int) -> None:
        """
        Сохраняет данные вызова CAPTCHA.

        Args:
            challenge_id: Уникальный идентификатор вызова.
            data: Данные для сохранения (сериализуемый словарь).
            ttl_seconds: Время жизни записи в секундах.
        """
        pass

    @abstractmethod
    async def retrieve_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        """
        Извлекает данные вызова CAPTCHA.

        Args:
            challenge_id: Уникальный идентификатор вызова.

        Returns:
            Словарь с данными вызова или None, если не найден или истек.
        """
        pass

    @abstractmethod
    async def delete_challenge(self, challenge_id: str) -> None:
        """
        Удаляет данные вызова CAPTCHA.

        Args:
            challenge_id: Уникальный идентификатор вызова.
        """
        pass

    async def close(self) -> None:
        """
        Опциональный метод для закрытия соединений или освобождения ресурсов.
        Реализации хранилищ могут его переопределить при необходимости.
        """
        pass


class AbstractSyncCaptchaStore(ABC):
    """
    Абстрактный базовый класс для синхронного хранилища состояний CAPTCHA.
    """

    @abstractmethod
    def store_challenge(self, challenge_id: str, data: Dict[str, Any], ttl_seconds: int) -> None:
        """
        Сохраняет данные вызова CAPTCHA.

        Args:
            challenge_id: Уникальный идентификатор вызова.
            data: Данные для сохранения (сериализуемый словарь).
            ttl_seconds: Время жизни записи в секундах.
        """
        pass

    @abstractmethod
    def retrieve_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        """
        Извлекает данные вызова CAPTCHA.

        Args:
            challenge_id: Уникальный идентификатор вызова.

        Returns:
            Словарь с данными вызова или None, если не найден или истек.
        """
        pass

    @abstractmethod
    def delete_challenge(self, challenge_id: str) -> None:
        """
        Удаляет данные вызова CAPTCHA.

        Args:
            challenge_id: Уникальный идентификатор вызова.
        """
        pass

    def close(self) -> None:
        """
        Опциональный метод для закрытия соединений или освобождения ресурсов.
        Реализации хранилищ могут его переопределить при необходимости.
        """
        pass