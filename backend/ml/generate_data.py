import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
N = 20000

def sample_row():
    age = int(rng.choice(
        [rng.integers(0, 12), rng.integers(12, 65), rng.integers(65, 95)],
        p=[0.20, 0.55, 0.25]))
    band = 0 if age < 12 else (2 if age >= 65 else 1)
    # latent true acuity 0..1 drives both the vitals and the label
    acuity = float(np.clip(rng.beta(2, 5) + (0.08 if band == 2 else 0), 0, 1))
    hr = int(np.clip(rng.normal(90 + 60 * acuity + (25 if band == 0 else 0), 12), 40, 210))
    spo2 = int(np.clip(rng.normal(98 - 9 * acuity, 1.6), 82, 100))
    temp = float(np.clip(rng.normal(36.8 + 2.2 * acuity * rng.random(), 0.4), 34.5, 41.5))
    bp = int(np.clip(rng.normal(120 - 32 * acuity + rng.normal(0, 14), 10), 60, 210))
    pain = int(np.clip(rng.normal(2 + 7 * acuity - (1.5 if band == 2 else 0), 2), 0, 10))
    symptom_w = float(np.clip(rng.normal(38 * acuity, 9), 0, 60))
    ambulance = int(rng.random() < 0.10 + 0.40 * acuity)
    appear = int(np.clip(rng.poisson(2.4 * acuity), 0, 4))
    label = 2 if acuity > 0.62 else (1 if acuity > 0.33 else 0)  # 0=lower 1=urgent 2=emergency
    return dict(age=age, band=band, hr=hr, spo2=spo2, temp=temp, bp_sys=bp, pain=pain,
                symptom_weight=symptom_w, ambulance=ambulance,
                appearance_flags=appear, label=label)

df = pd.DataFrame([sample_row() for _ in range(N)])
df.to_csv("ml/synthetic_ed.csv", index=False)
print(f"wrote ml/synthetic_ed.csv  ({len(df)} rows)")
print(df["label"].value_counts().rename({0: "lower", 1: "urgent", 2: "emergency"}))
