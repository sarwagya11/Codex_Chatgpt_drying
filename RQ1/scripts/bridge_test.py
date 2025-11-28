from pathlib import Path
import sys
import numpy as np
import pandas as pd

# bridge_test.py is at: <repo>/RQ1/scripts/bridge_test.py
_PROJECT_ROOT = Path(__file__).resolve().parents[2]      # -> <repo> Codex_Chatgpt_drying
_RQ1_SRC = _PROJECT_ROOT / "RQ1" / "src"

# Make sure repo root is visible so 'scripts.*' can be imported from pickles
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Make sure rq1 package is visible
if str(_RQ1_SRC) not in sys.path:
    sys.path.insert(0, str(_RQ1_SRC))

from rq1.phase2_bridge import (
    predict_midilli_params_for_operating_point,
    evaluate_piecewise_midilli_MR,
    evaluate_piecewise_midilli_Xdb,
)

def main() -> None:
    T_C = 50.0
    v_ms = 1.10
    thickness_mm = 6.0
    RH_mid_pct = 35.0
    t_split_min = 390.65  # plug real value later

    models_root = _PROJECT_ROOT / "outputs" / "phase2" / "models"

    params = predict_midilli_params_for_operating_point(
        T_C=T_C,
        v_ms=v_ms,
        thickness_mm=thickness_mm,
        RH_mid_pct=RH_mid_pct,
        t_split_min=t_split_min,
        models_root=models_root,  # <--- override here
    )

    print("MidilliParams:", params)

    t_s = np.arange(0.0, 700.0 * 60.0 + 1.0, 60.0)
    MR = evaluate_piecewise_midilli_MR(t_s, params, mr_floor=0.0)

    X0_db = 2.50
    X_eq_db = 0.05
    X_db = evaluate_piecewise_midilli_Xdb(t_s, params, X0_db=X0_db, X_eq_db=X_eq_db)

    out = Path("RQ1/data/phase1_runs/test_phase2_bridge.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "time_s": t_s,
            "time_min": t_s / 60.0,
            "MR_bridge": MR,
            "X_db_bridge": X_db,
        }
    ).to_csv(out, index=False)
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
