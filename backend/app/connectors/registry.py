from typing import Type
from .base import BaseConnector
from .csv_connector import CSVConnector
from .shopify_connector import ShopifyConnector
from .google_analytics_connector import GoogleAnalyticsConnector
from .stripe_connector import StripeConnector

class ConnectorRegistry:
    _registry = {
        "csv": CSVConnector,
        "shopify": ShopifyConnector,
        "google_analytics": GoogleAnalyticsConnector,
        "stripe": StripeConnector
    }

    @classmethod
    def get_connector(cls, platform: str) -> Type[BaseConnector]:
        if platform not in cls._registry:
            raise ValueError(f"Platform {platform} is not supported.")
        return cls._registry[platform]
    
    @classmethod
    def get_all_connectors(cls) -> list:
        return [connector().get_info() for connector in cls._registry.values()]
