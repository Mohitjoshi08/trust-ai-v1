import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def generate_dataset(filename, num_rows, anomaly_region, anomaly_direction):
    print(f"Generating {filename}...")
    
    regions = ['NA', 'EMEA', 'APAC', 'LATAM']
    devices = ['iOS', 'Android', 'Web']
    
    start_time = datetime(2025, 8, 1)
    
    # Base timestamps (every hour)
    dates = pd.date_range(start_time, periods=num_rows, freq='5min')
    
    df_list = []
    for _ in range(num_rows):
        df_list.append({
            'timestamp': np.random.choice(dates),
            'metric_name': 'revenue',
            'metric_value': max(10, np.random.normal(200, 50)),
            'region': np.random.choice(regions),
            'device': np.random.choice(devices)
        })
        
    df = pd.DataFrame(df_list).sort_values('timestamp')
    
    # Inject anomaly around Aug 15
    anomaly_mask = (df['timestamp'] >= '2025-08-15') & (df['timestamp'] <= '2025-08-17') & (df['region'] == anomaly_region)
    
    if anomaly_direction == 'spike':
        df.loc[anomaly_mask, 'metric_value'] *= 3.0
    else:
        df.loc[anomaly_mask, 'metric_value'] *= 0.2
        
    df.to_csv(filename, index=False)
    print(f"Saved to {filename}")

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    generate_dataset(os.path.join(out_dir, "dataset_A_EMEA_spike.csv"), 50000, "EMEA", "spike")
    generate_dataset(os.path.join(out_dir, "dataset_B_APAC_drop.csv"), 50000, "APAC", "drop")
