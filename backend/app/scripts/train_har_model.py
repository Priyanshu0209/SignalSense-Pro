import os
import random
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

def generate_synthetic_data(num_samples_per_class=1000):
    classes = ["Still", "Standing", "Sitting", "Walking", "Running", "Falling"]
    data = []
    
    for cls in classes:
        for _ in range(num_samples_per_class):
            row = {}
            
            # Base RSSI
            if cls == "Still": base_rssi = random.uniform(-55, -45)
            elif cls == "Sitting": base_rssi = random.uniform(-65, -55)
            elif cls == "Standing": base_rssi = random.uniform(-60, -50)
            elif cls == "Walking": base_rssi = random.uniform(-75, -60)
            elif cls == "Running": base_rssi = random.uniform(-85, -70)
            elif cls == "Falling": base_rssi = random.uniform(-90, -75)
            else: base_rssi = -60
            
            row["RSSI"] = base_rssi
            
            # Subcarriers (64 amplitudes, 64 phases)
            for i in range(64):
                if cls == "Still":
                    amp = random.uniform(10, 15)
                elif cls == "Sitting":
                    amp = random.uniform(12, 18)
                elif cls == "Standing":
                    amp = random.uniform(15, 22)
                elif cls == "Walking":
                    amp = random.uniform(20, 50) + np.sin(i / 10.0) * 10
                elif cls == "Running":
                    amp = random.uniform(30, 90) + np.sin(i / 5.0) * 20
                elif cls == "Falling":
                    amp = random.uniform(0, 120) if i % 5 == 0 else random.uniform(10, 20)
                else:
                    amp = random.uniform(10, 20)
                
                # Add thermal noise
                amp += random.uniform(-2, 2)
                row[f"Amp_{i}"] = max(0, amp)
                row[f"Phase_{i}"] = random.uniform(-np.pi, np.pi)
                
            row["label"] = cls
            data.append(row)
            
    return pd.DataFrame(data)

def main():
    print("Generating synthetic CSI Dataset for HAR...")
    df = generate_synthetic_data(1200)
    
    # Verify Columns (1 RSSI + 64 Amp + 64 Phase + 1 Label = 130)
    print(f"Dataset Shape: {df.shape}")
    
    X = df.drop(columns=["label"])
    y = df["label"]
    
    # Feature ordering strictly matching MotionActivityEngine
    feature_cols = ["RSSI"] + [f"Amp_{i}" for i in range(64)] + [f"Phase_{i}" for i in range(64)]
    X = X[feature_cols]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Lightweight Random Forest Classifier...")
    model = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    
    print("Evaluating Model...")
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Model Accuracy: {acc * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    if acc < 0.90:
        print("Warning: Accuracy is below 90%. Model might not be reliable enough.")
        
    # Save the model exactly where MotionActivityEngine expects it
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "gait3d")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "csi_har_model.joblib")
    
    joblib.dump(model, out_path)
    print(f"\nSuccess! ML HAR Model exported to {out_path}")

if __name__ == "__main__":
    main()
