"""Data models for the application."""

from typing import Dict, Literal, Union, Annotated

from pydantic import BaseModel, Field, ConfigDict


class TaskDTO(BaseModel):
    """Data Transfer Object for task submission."""

    qc: str  # QASM3 string

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "qc": (
                    "OPENQASM 3.0;\ninclude \"stdgates.inc\";\nbit[2] c;\nqubit[2] q;\n"
                    "h q[0];\ncx q[0], q[1];\nc[0] = measure q[0];\nc[1] = measure q[1];\n"
                )
            }
        }
    )


class TaskSubmitResponse(BaseModel):
    task_id: str
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "53382f22-b232-45be-a95d-f278e182d46a",
                "message": "Task submitted successfully.",
            }
        }
    )


class TaskCompletedResponse(BaseModel):
    status: Literal["completed"]
    result: Dict[str, int]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "completed",
                "result": {"0": 512, "1": 512},
            }
        }
    )


class TaskPendingResponse(BaseModel):
    status: Literal["pending"]
    message: str = Field(default="Task is still in progress.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "pending",
                "message": "Task is still in progress.",
            }
        }
    )


class TaskErrorResponse(BaseModel):
    status: Literal["error"]
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "error",
                "message": "Task not found.",
            }
        }
    )


class HTTPError(BaseModel):
    detail: str = Field(description="Error message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"detail": "QASM3 code is not valid"}
        }
    )


class ValidationErrorItem(BaseModel):
    loc: list[Union[str, int]]
    msg: str
    type: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "loc": ["body", "qc"],
                "msg": "Field required",
                "type": "value_error.missing",
            }
        }
    )


class RequestValidationErrorResponse(BaseModel):
    detail: list[ValidationErrorItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": [
                    {
                        "loc": ["body", "qc"],
                        "msg": "Field required",
                        "type": "value_error.missing",
                    }
                ]
            }
        }
    )


TaskStatusResponse = Annotated[
    Union[TaskCompletedResponse, TaskPendingResponse, TaskErrorResponse],
    Field(discriminator="status"),
]
