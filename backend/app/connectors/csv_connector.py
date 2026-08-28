from typing import Dict, List
import pandas as pd
from app.connectors.base import BaseConnector

class CSVConnector(BaseConnector):
    platform = "csv"
    display_name = "CSV Upload"
    description = "Upload data via CSV file"
    icon = "file-text"
    required_fields = [{"name": "file_path", "label": "File Path", "type": "text"}]

    def test_connection(self, credentials: Dict) -> bool:
        try:
            pd.read_csv(credentials.get("file_path"), nrows=1)
            return True
        except Exception:
            return False

    def fetch_schema(self, credentials: Dict) -> List[str]:
        df = pd.read_csv(credentials.get("file_path"), nrows=1)
        return df.columns.tolist()

    def fetch_data(self, credentials: Dict, mapping_config: Dict) -> pd.DataFrame:
        return pd.read_csv(credentials.get("file_path"))
