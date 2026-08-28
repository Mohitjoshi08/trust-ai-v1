from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd

class BaseConnector(ABC):
    platform: str = ""
    display_name: str = ""
    description: str = ""
    icon: str = ""  # lucide icon name
    required_fields: List[Dict] = []  # [{"name": "api_key", "label": "API Key", "type": "password"}]

    @abstractmethod
    def test_connection(self, credentials: Dict) -> bool:
        """Test if the credentials are valid."""
        pass

    @abstractmethod
    def fetch_schema(self, credentials: Dict) -> List[str]:
        """Fetch column names / schema from the data source."""
        pass

    @abstractmethod
    def fetch_data(self, credentials: Dict, mapping_config: Dict) -> pd.DataFrame:
        """Pull data from the source and return a normalized DataFrame."""
        pass

    def get_info(self) -> Dict:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "required_fields": self.required_fields,
        }
