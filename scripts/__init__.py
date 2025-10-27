"""Command-line entry points for the drying kinetics toolkit."""

try:  # pragma: no cover - defensive import for interactive execution
    from .phase1_fit_once import run_pipeline
    from .phase1_fit_all import run_batch
except ImportError:  # executed when package context is missing (e.g., VS Code cell)
    from scripts.phase1_fit_once import run_pipeline  # type: ignore
    from scripts.phase1_fit_all import run_batch  # type: ignore

__all__ = ["run_pipeline", "run_batch"]
