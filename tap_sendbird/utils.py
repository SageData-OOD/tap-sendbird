"""Utility functions"""
from __future__ import annotations

def convert_ts_to_milliseconds_string(ts:int)-> str:
     """Convert an epoch timestamp to milliseconds format(if needed)"""
     ts = str(ts)
     assert len(ts) <= 13
     return ts + (13 - len(ts)) * "0"

def convert_metadata_to_json_string(data: dict | list) -> dict | list:
    """
    Recursively converts all dictionary properties named 'metadata' into JSON strings.
    
    Args:
        data (dict, list): The input dictionary or list.
    
    Returns:
        dict or list: The transformed data with 'metadata' fields as JSON strings.
    """
    if isinstance(data, dict):
        # Iterate through dictionary keys
        for key, value in data.items():
            if key == "metadata" and isinstance(value, (dict, list)):
                # Convert "metadata" property to JSON string
                data[key] = json.dumps(value)
            else:
                # Recursively process nested dictionaries or lists
                data[key] = convert_metadata_to_json_string(value)
    elif isinstance(data, list):
        # Iterate through list items
        for i in range(len(data)):
            data[i] = convert_metadata_to_json_string(data[i])
    
    return data