"""Stream type classes for tap-sendbird."""
from __future__ import annotations

import datetime
from urllib.parse import urlparse
from urllib.parse import parse_qs
from typing import Any, Dict, Iterable, Optional

import requests
from singer_sdk import typing as th  # JSON Schema typing helpers
from singer_sdk.exceptions import FatalAPIError, RetriableAPIError
from singer_sdk.helpers.jsonpath import extract_jsonpath

from tap_sendbird.client import SendBirdStream


def convert_ts_to_milliseconds(ts:int)-> str:
     assert len(ts) <= 13
     return ts + (13 - len(ts)) * "0"

class UsersStream(SendBirdStream):
    name = "users"
    path = "/users"
    primary_keys = ["user_id"]
    records_jsonpath = "$.users[*]"
    schema_filepath = "tap_sendbird/schemas/users.json"

class GroupChannelsStream(SendBirdStream):
    name = "group_channels"
    path = "/group_channels"
    primary_keys = ["channel_url"]
    records_jsonpath = "$.channels[*]"
    schema_filepath = "tap_sendbird/schemas/group_channels.json"

    def get_child_context(self, record: dict, context: Optional[dict]) -> dict:
        """Return a context dictionary for child streams."""
        return {
            "channel_type": "group_channel",
            "channel_url": record["channel_url"],
            "last_message_ts": str((record.get("last_message", {}) or {}).get("created_at", 0))
        }
    
    def get_url_params(
        self, context: dict, next_page_token=None
    ) -> dict[str, Any]:
        
        url_params: dict[str, Any] = super().get_url_params(context=context, 
                                                            next_page_token=next_page_token)
        url_params["show_member"] = True

        return url_params

    # def _write_starting_replication_value(self, context: dict | None) -> None:
    #     pass

    # def _increment_stream_state(
    #     self, latest_record: dict[str, Any], *, context: dict | None = None
    # ) -> None:
    #     pass

class MessagesStream(SendBirdStream):
    name = "messages"
    path = "/messages"
    parent_stream_type = GroupChannelsStream
    ignore_parent_replication_keys = True
    path = "/{channel_type}s/{channel_url}/messages"
    primary_keys = ["message_id"]
    records_jsonpath = "$.messages[*]"
    replication_key = "created_at"
    schema_filepath = "tap_sendbird/schemas/messages.json"

    max_records_per_page_limit = 200

    def __init__(self, tap, name=None, schema=None, path=None):
        super().__init__(tap, name, schema, path)
        self.query_stream = True

    # def get_records(self, context: dict | None) -> Iterable[dict[str, Any]]:
    #     """Return a generator of record-type dictionary objects.

    #     Each record emitted should be a dictionary of property names to their values.

    #     Args:
    #         context: Stream partition or context dictionary.

    #     Yields:
    #         One item per (possibly processed) record in the API.
    #     """
    #     if self.query_stream:
    #         for record in super().get_records(context):
    #             yield record
    #     else:
    #         self.logger.info("Skipping channel sync due to ".format(context))

    def get_url_params(
        self, context: dict, next_page_token=None
    ) -> dict[str, Any]:
        
        """Return URL params that go with the request."""
        if not next_page_token:
            next_page_token = convert_ts_to_milliseconds(self.get_starting_replication_key_value(context))
            
            if next_page_token > context["last_message_ts"]:
                self.query_stream = False

        next_page_token = convert_ts_to_milliseconds(next_page_token)
        self.logger.info("NEXT PAGE TOKEN: {}".format(next_page_token))

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
    
    # def _write_replication_key_signpost(
    #     self,
    #     context: dict | None,
    #     value: datetime.datetime | str | int | float,
    # ) -> None:
    #     pass

    # def _write_starting_replication_value(self, context: dict | None) -> None:
    #     pass

    # def _increment_stream_state(
    #     self, latest_record: dict[str, Any], *, context: dict | None = None
    # ) -> None:
    #     pass

    @property
    def state_partitioning_keys(self) -> list[str] | None:
        """Get state partition keys.

        If not set, a default partitioning will be inherited from the stream's context.
        If an empty list is set (`[]`), state will be held in one bookmark per stream.

        Returns:
            Partition keys for the stream state bookmarks.
        """
        return []