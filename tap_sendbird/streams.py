"""Stream type classes for tap-sendbird."""
from __future__ import annotations

import os
import json

from typing import Any, Optional, Iterable

import requests
from singer_sdk.helpers.jsonpath import extract_jsonpath

from tap_sendbird.client import SendBirdStream


def convert_ts_to_milliseconds(ts:int)-> str:
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


class UsersStream(SendBirdStream):
    name = "users"
    path = "/users"
    primary_keys = ["user_id"]
    records_jsonpath = "$.users[*]"
    schema_filepath = f"{os.path.dirname(os.path.abspath(__file__))}/schemas/users.json"

    def post_process(self, row: dict, context: dict | None = None) -> dict | None:
        """As needed, append or transform raw data to match expected structure.

        Optional. This method gives developers an opportunity to "clean up" the results
        prior to returning records to the downstream tap - for instance: cleaning,
        renaming, or appending properties to the raw record result returned from the
        API.

        Developers may also return `None` from this method to filter out
        invalid or not-applicable records from the stream.

        Args:
            row: Individual record in the stream.
            context: Stream partition or context dictionary.

        Returns:
            The resulting record dict, or `None` if the record should be excluded.
        """

        return convert_metadata_to_json_string(row)    

class GroupChannelsStream(SendBirdStream):
    name = "group_channels"
    path = "/group_channels"
    primary_keys = ["channel_url"]
    records_jsonpath = "$.channels[*]"
    schema_filepath = f"{os.path.dirname(os.path.abspath(__file__))}/schemas/group_channels.json"

    def get_child_context(self, record: dict, context: Optional[dict]) -> dict:
        """Return a context dictionary for child streams."""
        return {
            "channel_type": "group_channel",
            "channel_url": record["channel_url"],
            "last_message_ts": str((record.get("last_message", {"created_at" : -1}) or {"created_at" : -1}).get("created_at"))
        }
    
    def get_url_params(
        self, context: dict, next_page_token=None
    ) -> dict[str, Any]:
        
        url_params: dict[str, Any] = super().get_url_params(context=context, 
                                                            next_page_token=next_page_token)
        url_params["show_member"] = True

        return url_params
    
    def post_process(self, row: dict, context: dict | None = None) -> dict | None:
        """As needed, append or transform raw data to match expected structure.

        Optional. This method gives developers an opportunity to "clean up" the results
        prior to returning records to the downstream tap - for instance: cleaning,
        renaming, or appending properties to the raw record result returned from the
        API.

        Developers may also return `None` from this method to filter out
        invalid or not-applicable records from the stream.

        Args:
            row: Individual record in the stream.
            context: Stream partition or context dictionary.

        Returns:
            The resulting record dict, or `None` if the record should be excluded.
        """

        return convert_metadata_to_json_string(row)

class MessagesStream(SendBirdStream):
    name = "messages"
    path = "/messages"
    parent_stream_type = GroupChannelsStream
    ignore_parent_replication_keys = True
    path = "/{channel_type}s/{channel_url}/messages"
    primary_keys = ["message_id"]
    records_jsonpath = "$.messages[*]"
    replication_key = "created_at"
    schema_filepath = f"{os.path.dirname(os.path.abspath(__file__))}/schemas/messages.json"

    max_records_per_page_limit = 200

    def __init__(self, tap, name=None, schema=None, path=None):
        super().__init__(tap, name, schema, path)
        self.query_stream = True

    def get_records(self, context: dict | None) -> Iterable[dict[str, Any]]:
        """Return a generator of record-type dictionary objects.

        Each record emitted should be a dictionary of property names to their values.

        Args:
            context: Stream partition or context dictionary.

        Yields:
            One item per (possibly processed) record in the API.
        """
        if self.query_stream:
            for record in super().get_records(context):
                yield record
        else:
            self.logger.info("Skipping channel sync. Latest message in channel is older than current sync bookmark ".format(context))

    def get_url_params(
        self, context: dict, next_page_token=None
    ) -> dict[str, Any]:
        
        """Return URL params that go with the request."""
        if not next_page_token:
            next_page_token = convert_ts_to_milliseconds(self.get_starting_replication_key_value(context))
            
            if context["last_message_ts"] != "-1" and next_page_token > context["last_message_ts"]:
                self.query_stream = False

        next_page_token = convert_ts_to_milliseconds(next_page_token)
        self.logger.info("Next Page Token: {}".format(next_page_token))

        url_params: dict[str, Any] = {
            "prev_limit": 0,
            "next_limit": self.max_records_per_page_limit,
            "message_ts": next_page_token
        }

        return url_params
    
    def get_next_page_token(
        self, response: requests.Response, previous_token: Optional[Any]
    ) -> Optional[Any]:
        """Return a token for identifying next page or None if no more pages."""
        # sort messages in ascending order
        all_messages = list(extract_jsonpath(
            self.records_jsonpath, response.json()
        ))
        
        if len(all_messages) != self.max_records_per_page_limit:
            return None  
        
        # convert to milliseconds
        message_ts = all_messages[-1]["created_at"]
        return message_ts
    
    @property
    def state_partitioning_keys(self) -> list[str] | None:
        """Get state partition keys.

        If not set, a default partitioning will be inherited from the stream's context.
        If an empty list is set (`[]`), state will be held in one bookmark per stream.

        Returns:
            Partition keys for the stream state bookmarks.
        """
        # there could be unlimited number of group channels which would explode the state
        # hence partitioning gets disabled by returning an empty list
        return []
