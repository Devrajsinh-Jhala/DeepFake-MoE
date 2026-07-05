from redis import Redis
from rq import Worker

from .config import get_settings
from .database import init_db


def main() -> None:
    settings = get_settings()
    init_db()
    worker = Worker(["analyses"], connection=Redis.from_url(settings.redis_url))
    worker.work()


if __name__ == "__main__":
    main()
