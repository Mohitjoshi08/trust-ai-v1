from typing import Dict, List
import pandas as pd
from app.connectors.base import BaseConnector

class ShopifyConnector(BaseConnector):
    platform = "shopify"
    display_name = "Shopify"
    description = "Connect your Shopify store to sync orders and revenue."
    icon = "shopping-bag"
    required_fields = [
        {"name": "shop_url", "label": "Shop URL", "type": "text"},
        {"name": "access_token", "label": "Admin API Access Token", "type": "password"}
    ]

    def test_connection(self, credentials: Dict) -> bool:
        # Mock connection test
        return bool(credentials.get("access_token"))

    def fetch_schema(self, credentials: Dict) -> List[str]:
        # Mock schema
        return ["created_at", "total_price", "currency", "order_number", "customer_id"]

    def fetch_data(self, credentials: Dict, mapping_config: Dict) -> pd.DataFrame:
        # Mock data fetch
        return pd.DataFrame()
