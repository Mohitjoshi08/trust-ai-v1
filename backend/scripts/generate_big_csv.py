import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def generate_large_csv(filename, num_rows=1000000):
    print(f"Generating {num_rows} rows of data...")
    
    # Pre-define arrays for faster generation
    regions = ['NA', 'EMEA', 'APAC', 'LATAM']
    devices = ['iOS', 'Android', 'Web', 'DesktopApp']
    metric_names = ['revenue', 'signups', 'active_users']
    
    # We will generate in chunks to avoid memory issues if num_rows is huge
    chunk_size = 500000
    rows_generated = 0
    
    start_time = datetime(2023, 1, 1)
    
    # Open file and write header
    with open(filename, 'w') as f:
        f.write("timestamp,metric_name,metric_value,region,device\n")
    
    while rows_generated < num_rows:
        current_chunk_size = min(chunk_size, num_rows - rows_generated)
        
        # Generate random time increments (1 to 5 minutes apart)
        time_increments = np.random.randint(1, 6, size=current_chunk_size)
        time_offsets = np.cumsum(time_increments)
        
        # Calculate timestamps for this chunk
        chunk_start = start_time + timedelta(minutes=int(rows_generated))
        timestamps = [chunk_start + timedelta(minutes=int(offset)) for offset in time_offsets]
        
        metrics = np.random.choice(metric_names, size=current_chunk_size)
        regs = np.random.choice(regions, size=current_chunk_size)
        devs = np.random.choice(devices, size=current_chunk_size)
        
        # Base values with some noise
        base_values = np.random.normal(200, 50, size=current_chunk_size)
        base_values = np.clip(base_values, 10, None)
        
        df = pd.DataFrame({
            'timestamp': [t.isoformat() + "Z" for t in timestamps],
            'metric_name': metrics,
            'metric_value': np.round(base_values, 2),
            'region': regs,
            'device': devs
        })
        
        df.to_csv(filename, mode='a', header=False, index=False)
        
        rows_generated += current_chunk_size
        print(f"Generated {rows_generated} / {num_rows} rows...")
        
    print(f"Done! Dataset saved to {filename}")

if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "big_synthetic_metrics.csv")
    generate_large_csv(out_path, num_rows=2000000) # 2 million rows ~ 100MB
