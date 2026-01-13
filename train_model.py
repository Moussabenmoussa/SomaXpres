# train_model.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import sys

DATA_PATH = "training_data.csv"
MODEL_OUT = "signal_model.joblib"
FEATURES = ["avg_trade","buy_ratio","whale_score","imbalance","volume_24h"]

def load_data(path=DATA_PATH):
    df = pd.read_csv(path)
    # تنظيف بسيط
    df = df.dropna(subset=FEATURES + ["label"])
    return df

def train(path=DATA_PATH, out=MODEL_OUT):
    df = load_data(path)
    X = df[FEATURES].values
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
    model.fit(X_train_s, y_train)

    preds = model.predict(X_test_s)
    probs = model.predict_proba(X_test_s)

    print("Accuracy:", accuracy_score(y_test, preds))
    print(classification_report(y_test, preds))

    # حفظ النموذج والمقياس معاً
    joblib.dump((model, scaler), out)
    print(f"Saved model to {out}")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DATA_PATH
    out = sys.argv[2] if len(sys.argv) > 2 else MODEL_OUT
    train(path, out)
