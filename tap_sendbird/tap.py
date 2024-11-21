"""SendBird tap class."""

from typing import List

from singer_sdk import Tap, Stream
from singer_sdk import typing as th  # JSON schema typing helpers

from tap_sendbird.streams import (
    UsersStream,
    GroupChannelsStream,
    MessagesStream
)

STREAM_TYPES = [
    UsersStream,
    GroupChannelsStream,
    MessagesStream
]

class TapSendBird(Tap):
    name = "tap-sendbird"
    config_jsonschema = th.PropertiesList(
        th.Property(
            "app_id",
            th.StringType,
            required=True,
            description="The App ID to authenticate against the API service"
        ),
        th.Property(
            "api_token",
            th.StringType,
            required=True,
            description="The Token to authenticate against the API service"
        ),
        th.Property(
            "start_date",
            th.DateTimeType,
            required=True,
            description="The earliest transaction date to sync"
        ),
    ).to_dict()

    def discover_streams(self) -> List[Stream]:
        """Return a list of discovered streams."""
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]
