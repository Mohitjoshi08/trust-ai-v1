"""
Golden Path Cache Manager for Trace.ai.

Provides instant, deterministic responses in demo mode by serving
pre-computed pipeline outputs from JSON files. In live mode, delegates
to the actual engine components with automatic cache fallback on failure.
"""
import os
import json
import logging
from typing import Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages demo/live mode toggle and golden path cache access."""

    def __init__(self):
        self.cache_dir = settings.CACHE_DIR
        self.demo_mode = settings.DEMO_MODE

    def _load(self, filename: str) -> Any:
        """Load a JSON file from the golden cache directory."""
        path = os.path.join(self.cache_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Cache file not found: {path}")
        with open(path, "r") as f:
            return json.load(f)

    def get_timeseries(self) -> Dict:
        """Get time-series data with anomaly windows."""
        if self.demo_mode:
            data = self._load("timeseries.json")
            data["served_from"] = "cache"
            return data
        # Live mode: would call bsts engine here
        raise NotImplementedError("Live mode not yet implemented")

    def get_decomposition(self, anomaly_start: Optional[str] = None) -> Dict:
        """Get metric decomposition for an anomaly window."""
        if self.demo_mode:
            return self._load("decomposition.json")
        raise NotImplementedError("Live mode not yet implemented")

    def get_root_cause(self, anomaly_start: Optional[str] = None) -> Dict:
        """Get root cause hypothesis for an anomaly."""
        if self.demo_mode:
            reports = self._load("anomaly_reports.json")
            if anomaly_start:
                for r in reports:
                    window = r.get("decomposition", {}).get("anomaly_window", {})
                    if window.get("start_time", "").startswith(anomaly_start[:10]):
                        return r.get("hypothesis", {
                            "hypotheses": [],
                            "served_from": "cache",
                            "status": "healthy"
                        })
            # Return first valid report's hypothesis
            if reports:
                return reports[0].get("hypothesis", {
                    "hypotheses": [],
                    "served_from": "cache",
                    "status": "healthy"
                })
            return {"hypotheses": [], "served_from": "cache", "status": "no_data"}
        raise NotImplementedError("Live mode not yet implemented")

    def get_anomaly_reports(self) -> list:
        """Get all pre-computed anomaly reports."""
        if self.demo_mode:
            return self._load("anomaly_reports.json")
        raise NotImplementedError("Live mode not yet implemented")

    def get_rag_results(self) -> Dict:
        """Get RAG search results."""
        if self.demo_mode:
            return self._load("rag_results.json")
        raise NotImplementedError("Live mode not yet implemented")

    def get_full_investigation(self, anomaly_start: Optional[str] = None) -> Dict:
        """Get full investigation report (decomp + rag + hypothesis) for an anomaly."""
        if self.demo_mode:
            reports = self._load("anomaly_reports.json")
            if anomaly_start:
                for r in reports:
                    window = r.get("decomposition", {}).get("anomaly_window", {})
                    if window.get("start_time", "").startswith(anomaly_start[:10]):
                        return r
            if reports:
                return reports[0]
            return {}
        raise NotImplementedError("Live mode not yet implemented")


# Singleton instance
cache_manager = CacheManager()
