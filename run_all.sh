#!/usr/bin/env bash
# CHANGE: Phase 2 orchestrator script
set -euo pipefail

CONFIG_PATH="${PHASE2_CONFIG:-}"  # CHANGE: Optional config override
COMMON_ARGS=()
if [[ -n "${CONFIG_PATH}" ]]; then
  COMMON_ARGS+=("--config" "${CONFIG_PATH}")  # CHANGE: Propagate config
fi

python scripts/phase2A_prepare_dataset.py "${COMMON_ARGS[@]}"
python scripts/phase2B_fit_param_models.py "${COMMON_ARGS[@]}"
python scripts/phase2C_predict_params.py "${COMMON_ARGS[@]}"
python scripts/phase2D_reconstruct_mr.py "${COMMON_ARGS[@]}"
