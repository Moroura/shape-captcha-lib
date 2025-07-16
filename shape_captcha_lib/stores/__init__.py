# shape_captcha_lib/stores/__init__.py
from .abc_store import AbstractAsyncCaptchaStore, AbstractSyncCaptchaStore
from .memory_store import SyncInMemoryStore, AsyncInMemoryStore
# Дальше будут добавлены JsonFileStore и RedisStore

__all__ = [
    "AbstractAsyncCaptchaStore",
    "AbstractSyncCaptchaStore",
    "SyncInMemoryStore",
    "AsyncInMemoryStore",
    # "SyncJsonFileStore",        # Будет добавлено
    # "AsyncJsonFileStore",       # Будет добавлено
    # "SyncRedisStore",           # Будет добавлено
    # "AsyncRedisStore",          # Будет добавлено
]