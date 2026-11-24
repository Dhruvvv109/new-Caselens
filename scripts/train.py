"""
scripts/train.py
Generate synthetic training data and train a LightGBM regressor to predict
days_to_resolution for Indian court cases.
"""

import random
import numpy as np
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# Try importing required packages
# ─────────────────────────────────────────────
try:
    import lightgbm as lgb
except ImportError:
    print("ERROR: lightgbm not installed. Run: pip install lightgbm")
    sys.exit(1)

try:
    import joblib
except ImportError:
    print("ERROR: joblib not installed. Run: pip install joblib scikit-learn")
    sys.exit(1)

try:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error
    from sklearn.preprocessing import LabelEncoder
except ImportError:
    print("ERROR: scikit-learn not installed. Run: pip install scikit-learn")
    sys.exit(1)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

CASE_TYPES = [
    "Criminal",
    "Property/Civil",
    "Family",
    "Labour",
    "Consumer",
    "Tax",
    "Constitutional/Writ",
    "Contract",
]

# Label encoding: must match app/predict.py
CASE_TYPE_ENCODING = {
    "Property/Civil": 0,
    "Criminal": 1,
    "Family": 2,
    "Labour": 3,
    "Consumer": 4,
    "Tax": 5,
    "Constitutional/Writ": 6,
    "Contract": 7,
}

BASE_DAYS = {
    "Criminal": 365,
    "Property/Civil": 540,
    "Family": 450,
    "Labour": 480,
    "Consumer": 300,
    "Tax": 420,
    "Constitutional/Writ": 600,
    "Contract": 480,
}

NUM_SAMPLES = 2000
RANDOM_SEED = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


# ─────────────────────────────────────────────
# Generate synthetic data
# ─────────────────────────────────────────────

def generate_sample():
    case_type = random.choice(CASE_TYPES)
    case_type_encoded = CASE_TYPE_ENCODING[case_type]
    days_since_filing = random.randint(30, 1800)
    hearings_so_far = random.randint(1, 20)
    num_parties = random.randint(2, 5)
    is_appeal = random.randint(0, 1)

    # Similarity features (plausible ranges)
    top1_similarity = round(random.uniform(0.1, 0.95), 4)
    mean_top5_similarity = round(random.uniform(0.1, top1_similarity), 4)
    count_matches_above_threshold = random.randint(0, 10)
    similarity_spread = round(abs(top1_similarity - mean_top5_similarity), 4)

    # Target formula
    base = BASE_DAYS[case_type]
    base *= (1 - 0.3 * mean_top5_similarity)   # strong precedent → shorter
    base *= (1 + 0.1 * (num_parties - 2))       # more parties → longer
    base += 90 * is_appeal                       # appeals take longer
    base += 20 * hearings_so_far                 # more hearings → already long
    base += random.gauss(0, 60)                  # noise
    days_to_resolution = float(np.clip(base, 30, 1200))

    return {
        "case_type_encoded": case_type_encoded,
        "days_since_filing": days_since_filing,
        "hearings_so_far": hearings_so_far,
        "num_parties": num_parties,
        "is_appeal": is_appeal,
        "top1_similarity": top1_similarity,
        "mean_top5_similarity": mean_top5_similarity,
        "count_matches_above_threshold": count_matches_above_threshold,
        "similarity_spread": similarity_spread,
        "days_to_resolution": days_to_resolution,
    }


def main():
    print(f"Generating {NUM_SAMPLES} synthetic training samples ...")
    data = [generate_sample() for _ in range(NUM_SAMPLES)]

    FEATURE_COLS = [
        "case_type_encoded",
        "days_since_filing",
        "hearings_so_far",
        "num_parties",
        "is_appeal",
        "top1_similarity",
        "mean_top5_similarity",
        "count_matches_above_threshold",
        "similarity_spread",
    ]
    TARGET_COL = "days_to_resolution"

    X = np.array([[row[f] for f in FEATURE_COLS] for row in data])
    y = np.array([row[TARGET_COL] for row in data])

    print(f"Feature matrix shape: {X.shape}")
    print(f"Target range: [{y.min():.1f}, {y.max():.1f}], mean={y.mean():.1f}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED
    )

    print("\nTraining LightGBM regressor ...")
    model = lgb.LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=RANDOM_SEED,
        verbose=-1,
    )
    model.fit(
        X_train, y_train,
        eval_X=X_test,
        eval_y=y_test,
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False),
                   lgb.log_evaluation(period=-1)],
    )

    # Evaluate
    y_pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    # Residual std (for confidence bands in predict.py)
    residuals = y_test - y_pred
    residual_std = float(np.std(residuals))

    print("\nFeature importances (gain):")
    importances = model.feature_importances_
    for feat, imp in sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1]):
        print(f"  {feat:<40s} {imp:.1f}")

    # Save model
    model_path = MODELS_DIR / "lgbm_model.joblib"
    joblib.dump(model, str(model_path))
    print(f"\nModel saved to {model_path}")

    # Save residual std
    residual_path = MODELS_DIR / "residual_std.txt"
    with open(str(residual_path), "w") as f:
        f.write(str(residual_std))
    print(f"Residual std ({residual_std:.2f} days) saved to {residual_path}")

    print(f"\nModel trained. RMSE: {rmse:.1f} days")


if __name__ == "__main__":
    main()
