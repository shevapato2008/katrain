"""Pluggable inference backends for stone detection."""

from katrain.vision.inference.base import InferenceBackend, create_backend

__all__ = ["InferenceBackend", "create_backend"]
