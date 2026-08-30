"""
Generate a ~2MB sample dataset for Trace.ai demo.
Creates a ZIP file containing metrics.csv and logs.json.
"""
import csv
import json
import random
import zipfile
import os
import uuid
from datetime import datetime, timedelta

random.seed(42)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(OUTPUT_DIR, "sample_10mb_dataset.zip")

# ── Configuration ─────────────────────────────────────────────────
START_DATE = datetime(2025, 1, 1)
NUM_DAYS = 90  # Reduced to 90 days to avoid ChromaDB safety filters and size issues
REGIONS = ["North America", "Europe"]
DEVICES = ["iOS", "Android"]
CHANNELS = ["Organic", "Paid Search"]
PRODUCTS = ["Pro Plan", "Basic Plan"]

# Anomaly windows (deliberate drops — these are big enough for BSTS to detect)
ANOMALY_WINDOWS = [
    {"start": 30, "end": 35, "region": "North America", "drop": 0.65, "cause": "Competitor mega-sale"},
    {"start": 50, "end": 55, "region": "Europe", "device": "iOS", "drop": 0.70, "cause": "iOS push notification bug"},
    {"start": 70, "end": 75, "device": "Android", "drop": 0.60, "cause": "Stripe SDK broke Android checkout"},
]

LOG_SOURCES = ["deploy-bot", "sentry-alerts", "pagerduty", "datadog-monitor", "cloudwatch"]
LOG_TEMPLATES = [
    "Config change: {param} updated from {old} to {new} in production",
    "Payment processing latency increased to {ms}ms in {region}",
    "A/B test '{test}' started — {pct}% traffic redirected",
    "Database migration completed: {table} schema updated",
    "Rate limiter triggered: {ip} blocked after {req} requests",
]

def is_in_anomaly(day_offset, region=None, device=None, channel=None):
    for aw in ANOMALY_WINDOWS:
        if aw["start"] <= day_offset <= aw["end"]:
            if "region" in aw and region and region != aw["region"]:
                continue
            if "device" in aw and device and device != aw["device"]:
                continue
            if "channel" in aw and channel and channel != aw["channel"]:
                continue
            return aw["drop"]
    return 0.0

def generate_metrics_csv(filepath):
    print("Generating metrics.csv...")
    rows = []
    
    for day in range(NUM_DAYS):
        dt = START_DATE + timedelta(days=day)
        timestamp = dt.strftime("%Y-%m-%dT00:00:00")
        
        for region in REGIONS:
            for device in DEVICES:
                for channel in CHANNELS:
                    for product in PRODUCTS:
                        base = 150 + 50 * random.random()
                        dow = dt.weekday()
                        if dow >= 5: base *= 0.7
                        base *= 1.0 + 0.1 * (dt.month % 3)
                        
                        region_mult = {"North America": 1.5, "Europe": 1.2}
                        base *= region_mult.get(region, 1.0)
                        
                        device_mult = {"iOS": 1.1, "Android": 0.9}
                        base *= device_mult.get(device, 1.0)
                        
                        drop = is_in_anomaly(day, region, device, channel)
                        if drop > 0:
                            base *= (1.0 - drop)
                        
                        revenue = max(0, base + random.gauss(0, base * 0.08))
                        conversions = max(0, int(revenue / (15 + random.random() * 10)))
                        sessions = max(conversions, int(conversions * (3 + random.random() * 5)))
                        
                        rows.append({
                            "timestamp": timestamp,
                            "region": region,
                            "device": device,
                            "channel": channel,
                            "product": product,
                            "revenue": round(revenue, 2),
                            "conversions": conversions,
                            "sessions": sessions
                        })
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "region", "device", "channel", "product", "revenue", "conversions", "sessions"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)

def generate_logs_json(filepath):
    print("Generating logs.json...")
    logs = []
    
    for day in range(NUM_DAYS):
        dt = START_DATE + timedelta(days=day)
        
        # Check if today is the START of an anomaly (deploy evidence)
        for aw in ANOMALY_WINDOWS:
            if day == aw["start"]:
                # Insert a deploy log slightly before the anomaly
                logs.append({
                    "id": str(uuid.uuid4()),
                    "timestamp": (dt.replace(hour=0, minute=1) - timedelta(days=1)).isoformat() + "Z",
                    "source": "deploy-bot",
                    "text_content": f"Deployment v4.5.1 rolled out to production — includes PR for {aw['cause']}"
                })
            
            if aw["start"] <= day <= aw["end"]:
                # Insert explicit error logs during the anomaly window
                logs.append({
                    "id": str(uuid.uuid4()),
                    "timestamp": dt.replace(hour=random.randint(2,10), minute=random.randint(0,59)).isoformat() + "Z",
                    "source": "sentry-alerts",
                    "text_content": f"CRITICAL: Unhandled exception detected related to {aw['cause']}! Error rate spiked by 500%."
                })
        
        # Normal daily noise logs
        for _ in range(random.randint(1, 3)):
            ts = dt.replace(hour=random.randint(0, 23), minute=random.randint(0, 59))
            template = random.choice(LOG_TEMPLATES)
            text = template.format(
                region=random.choice(REGIONS),
                param=random.choice(["max_retry_count", "cache_ttl"]),
                old=random.randint(1, 10),
                new=random.randint(1, 10),
                ms=random.randint(200, 1000),
                test="new-checkout-v2",
                pct=random.randint(5, 50),
                table="users",
                ip=f"192.168.1.{random.randint(1,255)}",
                req=random.randint(100, 1000),
            )
            logs.append({
                "id": str(uuid.uuid4()),
                "timestamp": ts.isoformat() + "Z",
                "source": random.choice(LOG_SOURCES),
                "text_content": text,
            })
    
    logs.sort(key=lambda x: x["timestamp"])
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)
    return len(logs)

def main():
    metrics_path = os.path.join(OUTPUT_DIR, "metrics.csv")
    logs_path = os.path.join(OUTPUT_DIR, "logs.json")
    
    generate_metrics_csv(metrics_path)
    generate_logs_json(logs_path)
    
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(metrics_path, "metrics.csv")
        zf.write(logs_path, "logs.json")
    
    os.remove(metrics_path)
    os.remove(logs_path)
    print("Dataset generated with EXPLICIT evidence logs!")

if __name__ == "__main__":
    main()
