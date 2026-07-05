from fastapi import BackgroundTasks

from .config import get_settings
from .tasks import process_analysis_job


def enqueue_analysis(analysis_id: str, background_tasks: BackgroundTasks) -> str:
    settings = get_settings()
    if settings.use_rq:
        from redis import Redis
        from rq import Queue

        queue = Queue("analyses", connection=Redis.from_url(settings.redis_url))
        queue.enqueue("app.tasks.process_analysis_job", analysis_id, job_timeout=600)
        return "rq"

    background_tasks.add_task(process_analysis_job, analysis_id)
    return "background"
