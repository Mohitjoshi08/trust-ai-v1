import csv
import random
from datetime import datetime, timedelta

def generate_data():
    filename = "complex_test_data.csv"
    regions = ["North America", "Europe", "Asia", "South America"]
    devices = ["Mobile", "Desktop", "Tablet"]
    channels = ["Organic", "Paid Search", "Social", "Direct", "Email"]
    
    start_date = datetime(2025, 1, 1)
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["date", "region", "device", "channel", "sessions", "pageviews", "revenue", "conversions", "bounce_rate"])
        
        for day in range(180): # 6 months of data
            current_date = start_date + timedelta(days=day)
            date_str = current_date.strftime("%Y-%m-%d")
            
            for region in regions:
                for device in devices:
                    for channel in channels:
                        # Base metrics
                        sessions = random.randint(100, 1000)
                        bounce_rate = round(random.uniform(0.3, 0.7), 2)
                        
                        # Apply some patterns
                        if region == "North America":
                            sessions = int(sessions * 1.5)
                        if device == "Mobile":
                            sessions = int(sessions * 1.2)
                        if channel == "Paid Search":
                            sessions = int(sessions * 1.3)
                            
                        pageviews = int(sessions * random.uniform(1.5, 4.0))
                        
                        # Conversions and Revenue
                        conversion_rate = random.uniform(0.01, 0.05)
                        
                        # Injecting Anomalies
                        # 1. Massive conversion drop in May for North America
                        if current_date.month == 5 and region == "North America":
                            conversion_rate = random.uniform(0.001, 0.005) # Severe drop
                            
                        # 2. Summer Sale spike in June
                        if current_date.month == 6:
                            sessions = int(sessions * 2.0)
                            conversion_rate = random.uniform(0.04, 0.08)
                            
                        # 3. Android/Mobile zero revenue bug in July
                        mobile_bug = False
                        if current_date.month == 7 and device == "Mobile":
                            mobile_bug = True
                            
                        conversions = int(sessions * conversion_rate)
                        
                        # AOV (Average Order Value) around $50
                        aov = random.uniform(40.0, 70.0)
                        revenue = round(conversions * aov, 2)
                        
                        if mobile_bug:
                            revenue = 0.0 # Pricing bug makes revenue 0
                            
                        writer.writerow([date_str, region, device, channel, sessions, pageviews, revenue, conversions, bounce_rate])

    print(f"Generated {filename} successfully.")

if __name__ == "__main__":
    generate_data()
