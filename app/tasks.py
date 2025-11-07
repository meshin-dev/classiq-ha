"""Asynchronous tasks for quantum circuit execution using Dramatiq and Qiskit."""

import dramatiq
from qiskit import qasm3
from qiskit.exceptions import QiskitUserConfigError, MissingOptionalLibraryError
from qiskit_aer import AerSimulator

from app.logger import logger
from app.queue import broker, redis_client
from app.settings import (
    QC_TASK_MAX_RETRIES,
    QC_TASK_TIME_LIMIT_MS,
    QC_TASK_DEFAULT_SHOTS,
)

# Import queue configuration BEFORE defining actors
# This ensures broker middlewares are loaded (and IDE won't remove import)
logger.debug(f"Broker loaded: {broker.broker_id}")


@dramatiq.actor(
    time_limit=QC_TASK_TIME_LIMIT_MS,
    actor_name="execute_qasm3",
    max_retries=QC_TASK_MAX_RETRIES,
    throws=(QiskitUserConfigError, MissingOptionalLibraryError),
    store_results=True,
)
def qasm3_task(
    task_id: str, qasm3_str: str, shots: int = QC_TASK_DEFAULT_SHOTS
) -> dict:
    """Execute a QASM3 quantum circuit and return counts as a dict."""
    try:
        logger.info(f"Task {task_id}: Starting execution with {shots} shots")
        circuit = qasm3.loads(qasm3_str)
        logger.debug(f"Task {task_id}: QASM3 parsed successfully")

        # Execute on simulator
        simulator = AerSimulator()
        job = simulator.run(circuit, shots=shots)
        logger.debug(f"Task {task_id}: Job submitted to simulator")
        result = job.result()
        counts = result.get_counts()
        logger.info(f"Task {task_id}: Completed successfully: {counts}")

        # Remove submitted flag (id is the dramatiq message_id)
        redis_client.delete(f"task_submitted:{task_id}")

        return dict(counts)
    except Exception as e:
        logger.error(f"Task {task_id}: Failed: {e}")
        raise
