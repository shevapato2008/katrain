"""Dedicated admin training API; reads never launch a worker."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from katrain.web.admin.session import get_current_admin
from katrain.web.admin.vision_training import VisionTrainingError

router = APIRouter(dependencies=[Depends(get_current_admin)])
Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")]


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: Annotated[bool, Field(strict=True)] = False


class StartIn(ConfirmIn):
    request_id: Annotated[str, Field(strict=True, min_length=36, max_length=36)]
    dataset_id: Annotated[str, Field(strict=True, pattern=r"^dataset-[0-9a-f]{64}$")]
    dataset_manifest_sha256: Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
    weights_id: Identifier
    augmentation: Literal["stones-standard", "led-safe"]
    gpu_id: Annotated[str, Field(strict=True, pattern=r"^[0-9]{1,2}$")]
    epochs: Annotated[int, Field(strict=True, ge=1, le=300)]
    batch: Annotated[int, Field(strict=True)]
    imgsz: Annotated[int, Field(strict=True)]
    seed: Annotated[int, Field(strict=True, ge=0, le=2147483647)]

    @field_validator("batch", "imgsz")
    @classmethod
    def fixed_options(cls, value: int, info: ValidationInfo) -> int:
        if value not in ({"batch": (4, 8), "imgsz": (640, 960)}[info.field_name]):
            raise ValueError("Parameter must use a fixed allowed value")
        return value


def _call(request, operation, *args, **kwargs):
    try:
        return getattr(request.app.state.vision_training, operation)(*args, **kwargs)
    except VisionTrainingError as exc:
        raise HTTPException(exc.status_code, detail=str(exc), headers={"Cache-Control": "no-store"}) from exc


def _parameters(parameters):
    return {
        key: parameters[key]
        for key in ("epochs", "batch", "imgsz", "seed", "device", "amp", "plots", "workers")
        if key in parameters
    }


def _run(run):
    spec = run["spec"]
    public = {
        key: run.get(key)
        for key in (
            "id",
            "state",
            "created_at",
            "started_at",
            "ended_at",
            "observed_at",
            "epoch",
            "total_epochs",
            "metrics",
            "log_tail",
            "error",
            "model_id",
        )
    }
    public.update(
        {
            key: spec[key]
            for key in ("dataset_id", "dataset_manifest_sha256", "weights_id", "augmentation", "mode", "class_names")
        }
    )
    public["parameters"] = _parameters(spec["parameters"])
    return public


@router.get("/status")
def status(request: Request):
    return _call(request, "status")


@router.get("/datasets")
def datasets(request: Request):
    return _call(request, "list_datasets")


@router.get("/presets")
def presets(request: Request):
    return _call(request, "presets")


@router.get("/runs")
def runs(request: Request):
    return [_run(run) for run in _call(request, "list_runs")]


@router.get("/runs/{run_id}")
def run(run_id: str, request: Request):
    return _run(_call(request, "get_run", run_id))


@router.get("/models")
def models(request: Request):
    return [{**model, "parameters": _parameters(model["parameters"])} for model in _call(request, "list_models")]


@router.post("/runs")
def start(body: StartIn, request: Request):
    return _run(_call(request, "start", body.model_dump(exclude={"confirmed"}), confirmed=body.confirmed))


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, body: ConfirmIn, request: Request):
    return _run(_call(request, "cancel", run_id, confirmed=body.confirmed))
