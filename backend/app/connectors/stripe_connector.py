from typing import Dict, List
import pandas as pd
from app.connectors.base import BaseConnector

class StripeConnector(BaseConnector):
    platform = "stripe"
    display_name = "Stripe"
    description = "Connect your Stripe account to sync payment data."
    icon = "credit-card"
    required_fields = [
        {"name": "api_key", "label": "Secret API Key", "type": "password"}
    ]

    def test_connection(self, credentials: Dict) -> bool:
        return bool(credentials.get("api_key"))

    def fetch_schema(self, credentials: Dict) -> List[str]:
        return ["created", "amount", "currency", "status", "customer_email"]

    def fetch_data(self, credentials: Dict, mapping_config: Dict) -> pd.DataFrame:
        return pd.DataFrame()
