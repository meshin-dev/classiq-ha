"""FastAPI routes for submitting and querying QASM3 execution tasks.

- POST /tasks: validate QASM3, enqueue execution, return message_id.
- GET /tasks/{id}: check result or pending/not found via submitted flag.
"""

import traceback
import json
from typing import Dict

import qiskit.qasm3
from dramatiq import Message
from dramatiq.results import ResultMissing, ResultTimeout
from fastapi import APIRouter, HTTPException

from app.helpers import new_task_id
from app.logger import logger
from app.models import (
    TaskDTO,
    TaskSubmitResponse,
    TaskStatusResponse,
    HTTPError,
    RequestValidationErrorResponse,
)
from app.queue import broker, redis_client
from app.tasks import qasm3_task
from app.settings import QC_TASK_MAX_RETRIES, QC_TASK_TIME_LIMIT_MS

router = APIRouter()

_SUBMITTED_PREFIX = "task_submitted:"  # existence marker key prefix


def _submitted_key(task_id: str) -> str:
    return f"{_SUBMITTED_PREFIX}{task_id}"


@router.post(
    "/tasks",
    response_model=TaskSubmitResponse,
    responses={
        400: {"model": HTTPError, "description": "Invalid or empty QASM3"},
        422: {"model": RequestValidationErrorResponse, "description": "Validation error (missing or malformed fields)"},
    },
)
def submit_task(body: TaskDTO) -> Dict[str, str]:
    task_id = new_task_id()
    if not body.qc or not body.qc.strip():
        logger.warning(f"Task {task_id}: Empty QASM3 code")
        raise HTTPException(status_code=400, detail="QASM3 code cannot be empty")

    try:
        logger.debug(f"Task {task_id}: Quantum Circuit String: {body.qc.strip()}")
        qc = qiskit.qasm3.loads(body.qc.strip())
    except Exception:
        logger.error(f"Task {task_id}: Invalid QASM3: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail="QASM3 code is not valid")

    msg = qasm3_task.message(task_id=task_id, qasm3_str=qiskit.qasm3.dumps(qc))
    broker.enqueue(msg)
    logger.info(f"Task {task_id} submitted (msg_id={msg.message_id})")

    # Existence flag with TTL matching overall worst-case processing window.
    ttl_ms = QC_TASK_TIME_LIMIT_MS * QC_TASK_MAX_RETRIES
    redis_client.set(_submitted_key(msg.message_id), b"1", px=ttl_ms)
    return {"task_id": msg.message_id, "message": "Task submitted successfully."}


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    responses={
        200: {"description": "Task status response"},
    },
)
def task_status(task_id: str) -> Dict[str, object]:
    logger.info(f"Checking status of task {task_id}")
    try:
        message = Message(
            queue_name=qasm3_task.queue_name,
            actor_name=qasm3_task.actor_name,
            message_id=task_id,
            args=(), kwargs={}, options={},
        )
        result = message.get_result(backend=broker.get_results_backend(), block=False)
        # Normalize to dict: decode bytes -> JSON; validate final type
        if isinstance(result, (bytes, bytearray)):
            try:
                result = json.loads(result.decode("utf-8"))
            except Exception:
                logger.error(f"Task {task_id}: Result bytes not valid JSON")
                return {"status": "error", "message": "Task result format invalid."}
        if not isinstance(result, dict):
            logger.error(f"Task {task_id}: Result not a dict (type={type(result).__name__})")
            return {"status": "error", "message": "Task result format invalid."}
        logger.info(f"Task {task_id} completed")
        # Remove existence marker now that result is available.
        redis_client.delete(_submitted_key(task_id))
        return {"status": "completed", "result": result}
    except ResultMissing:
        if redis_client.get(_submitted_key(task_id)) is not None:
            return {"status": "pending", "message": "Task is still in progress."}
        return {"status": "error", "message": "Task not found."}
    except ResultTimeout:
        if redis_client.get(_submitted_key(task_id)) is not None:
            return {"status": "pending", "message": "Task is still in progress."}
        return {"status": "error", "message": "Task not found."}
    except Exception as e:
        logger.error(f"Task {task_id} status error: {e}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}
