from typing import Dict, List
import pandas as pd
from app.connectors.base import BaseConnector

class GoogleAnalyticsConnector(BaseConnector):
    platform = "google_analytics"
    display_name = "Google Analytics 4"
    description = "Sync web traffic and engagement metrics."
    icon = "bar-chart-2"
    required_fields = [
        {"name": "property_id", "label": "Property ID", "type": "text"},
        {"name": "service_account_json", "label": "Service Account JSON", "type": "textarea"}
    ]

    def test_connection(self, credentials: Dict) -> bool:
        return bool(credentials.get("property_id"))

    def fetch_schema(self, credentials: Dict) -> List[str]:
        return ["date", "sessions", "pageviews", "bounce_rate", "source"]

    def fetch_data(self, credentials: Dict, mapping_config: Dict) -> pd.DataFrame:
        return pd.DataFrame()
