"""Scripts package exposing public entry-points for phase-1 analysis."""

from scripts.phase1_fit_all import run_batch
from scripts.phase1_fit_once import run_pipeline

"""Public entry points for the drying-kinetics toolkit."""
__all__ = ["run_pipeline", "run_batch"]

def __getattr__(name):
    if name == "run_pipeline":
        from .phase1_fit_once import run_pipeline
        return run_pipeline
    if name == "run_batch":
        from .phase1_fit_all import run_batch
        return run_batch
    raise AttributeError(name)
