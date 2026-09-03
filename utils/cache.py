import fnmatch
import json
import os
import pickle
import typing as t
from collections import namedtuple

from diskcache import Cache as DiskCache

from config import BASE_PATH

TaskResult = namedtuple('TaskResult', ['success', 'data'])


class TaskCache:
    """任务结果缓存，始终使用本地磁盘文件（diskcache）。"""

    _cache = DiskCache(os.path.join(BASE_PATH, 'locals', 'task.db'))

    @classmethod
    def set_result(cls, id: str, value: t.Any, success=True):
        cls._cache.set(f'result-{id}', value=TaskResult(success, value), expire=3600)

    @classmethod
    def get_result(cls, id: str) -> TaskResult | None:
        return t.cast(TaskResult | None, cls._cache.get(f'result-{id}'))


# === 统一缓存接口（配置了 redis 则使用 redis，否则使用 diskcache） ===

# 缓存配置文件，主进程启动时由 init_cache 写入，
# 子进程（spawn）重新导入本模块时读取该文件以确定后端。
_CACHE_CONF_PATH = os.path.join(BASE_PATH, 'locals', 'cache.json')


def _load_cache_conf() -> dict[str, t.Any]:
    try:
        with open(_CACHE_CONF_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


class Cache:
    """对外统一缓存接口，提供 redis 常用方法。"""

    def get(self, key: str) -> t.Any:
        raise NotImplementedError

    def set(self, key: str, value: t.Any, expire: int | None = None) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def expire(self, key: str, ttl: int) -> None:
        raise NotImplementedError

    def keys(self, pattern: str = '*') -> list[str]:
        raise NotImplementedError

    def incr(self, key: str, amount: int = 1) -> int:
        raise NotImplementedError

    def hset(self, key: str, field: str, value: t.Any) -> None:
        raise NotImplementedError

    def hget(self, key: str, field: str) -> t.Any:
        raise NotImplementedError

    def hgetall(self, key: str) -> dict[str, t.Any]:
        raise NotImplementedError

    def hdel(self, key: str, *fields: str) -> None:
        raise NotImplementedError


class _RedisCache(Cache):
    def __init__(self, host: str, port: int = 6379, password: str = '', db: int = 0):
        import redis
        self._client = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            decode_responses=False,
        )

    def get(self, key: str) -> t.Any:
        raw = self._client.get(key)
        return None if raw is None else pickle.loads(t.cast(bytes, raw))

    def set(self, key: str, value: t.Any, expire: int | None = None) -> None:
        self._client.set(key, pickle.dumps(value), ex=expire)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def expire(self, key: str, ttl: int) -> None:
        self._client.expire(key, ttl)

    def keys(self, pattern: str = '*') -> list[str]:
        raw = self._client.keys(pattern)
        return [k.decode('utf-8') if isinstance(k, bytes) else k for k in raw]

    def incr(self, key: str, amount: int = 1) -> int:
        return int(self._client.incrby(key, amount))

    def hset(self, key: str, field: str, value: t.Any) -> None:
        self._client.hset(key, field, pickle.dumps(value))

    def hget(self, key: str, field: str) -> t.Any:
        raw = self._client.hget(key, field)
        return None if raw is None else pickle.loads(t.cast(bytes, raw))

    def hgetall(self, key: str) -> dict[str, t.Any]:
        raw = self._client.hgetall(key)
        result: dict[str, t.Any] = {}
        for k, v in raw.items():
            fk = k.decode('utf-8') if isinstance(k, bytes) else k
            result[fk] = pickle.loads(t.cast(bytes, v))
        return result

    def hdel(self, key: str, *fields: str) -> None:
        if fields:
            self._client.hdel(key, *fields)


class _DiskCache(Cache):
    def __init__(self):
        self._client = DiskCache(os.path.join(BASE_PATH, 'locals', 'cache.db'))

    def get(self, key: str) -> t.Any:
        return self._client.get(key)

    def set(self, key: str, value: t.Any, expire: int | None = None) -> None:
        self._client.set(key, value, expire=expire)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def exists(self, key: str) -> bool:
        return key in self._client

    def expire(self, key: str, ttl: int) -> None:
        self._client.touch(key, expire=ttl)

    def keys(self, pattern: str = '*') -> list[str]:
        return [str(k) for k in self._client.iterkeys() if fnmatch.fnmatch(str(k), pattern)]

    def incr(self, key: str, amount: int = 1) -> int:
        val = int(t.cast(t.Any, self._client.get(key)) or 0) + amount
        self._client.set(key, val)
        return val

    def hset(self, key: str, field: str, value: t.Any) -> None:
        mapping = t.cast(dict, self._client.get(key)) or {}
        mapping[field] = value
        self._client.set(key, mapping)

    def hget(self, key: str, field: str) -> t.Any:
        mapping = t.cast(dict, self._client.get(key)) or {}
        return mapping.get(field)

    def hgetall(self, key: str) -> dict[str, t.Any]:
        return dict(t.cast(dict, self._client.get(key)) or {})

    def hdel(self, key: str, *fields: str) -> None:
        mapping = t.cast(dict, self._client.get(key)) or {}
        for f in fields:
            mapping.pop(f, None)
        self._client.set(key, mapping)


_cache: Cache | None = None
_cache_initialized = False


def get_cache() -> Cache:
    """返回统一缓存接口实例；配置了 redis 使用 redis，否则使用 diskcache。"""
    global _cache, _cache_initialized
    if not _cache_initialized:
        conf = _load_cache_conf()
        host = str(conf.get('host') or '').strip()
        if host:
            _cache = _RedisCache(
                host=host,
                port=int(conf.get('port') or 6379),
                password=str(conf.get('password') or ''),
                db=int(conf.get('db') or 0),
            )
        else:
            _cache = _DiskCache()
        _cache_initialized = True
    return t.cast(Cache, _cache)


def init_cache(host: str = '', port: int = 6379, password: str = '', db: int = 0):
    """主进程启动时调用，将缓存配置写入本地文件供主/子进程读取。

    host 为空时使用 diskcache 方案，否则使用 redis 方案。
    """
    global _cache, _cache_initialized
    os.makedirs(os.path.dirname(_CACHE_CONF_PATH), exist_ok=True)
    conf = {
        'host': (host or '').strip(),
        'port': int(port or 6379),
        'password': password or '',
        'db': int(db or 0),
    }
    with open(_CACHE_CONF_PATH, 'w', encoding='utf-8') as f:
        json.dump(conf, f)
    _cache = None
    _cache_initialized = False