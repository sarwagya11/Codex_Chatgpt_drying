"""Utilities for Phase-1 drying kinetics analysis."""

try:  # pragma: no cover - defensive import for interactive execution
    from .fitters_phase1 import fit_variant
    from .models_phase1 import MODEL_PARAM_NAMES
    from .preprocess_phase1 import preprocess_dataset
except ImportError:  # executed when package context is missing (e.g., VS Code cell)
    from kinetics.fitters_phase1 import fit_variant  # type: ignore
    from kinetics.models_phase1 import MODEL_PARAM_NAMES  # type: ignore
    from kinetics.preprocess_phase1 import preprocess_dataset  # type: ignore

__all__ = [
    "fit_variant",
    "MODEL_PARAM_NAMES",
    "preprocess_dataset",
]
