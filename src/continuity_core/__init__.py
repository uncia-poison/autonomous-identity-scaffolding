"""Continuity Core v0.1 compatibility layer."""

from .compiler import build_identity_bundle, compile_profile
from .drift import evaluate_drift
from .ingest import load_transcript

__all__ = ["build_identity_bundle", "compile_profile", "evaluate_drift", "load_transcript"]
__version__ = "0.1.0"
