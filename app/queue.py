"""Dramatiq broker and results backend configuration.

Redis is created with decode_responses=False for raw bytes; Dramatiq handles
result decoding internally.
"""

import dramatiq
import redis
from dramatiq.brokers.redis import RedisBroker
from dramatiq.results import Results
from dramatiq.results.backends import RedisBackend

from app.settings import REDIS_RESULT_TTL, REDIS_URL

# Connection pool: bytes responses (no implicit decoding)
pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=False)
redis_client = redis.Redis(connection_pool=pool)

broker = RedisBroker(connection_pool=pool)
result_backend = RedisBackend(connection_pool=pool)

# TTL for stored results (ms); 0 => keep indefinitely.
result_ttl_ms = REDIS_RESULT_TTL * 1000 if REDIS_RESULT_TTL > 0 else 0
broker.add_middleware(
    Results(
        backend=result_backend,
        store_results=True,
        result_ttl=result_ttl_ms,
    )
)

# Global broker registration
dramatiq.set_broker(broker)
