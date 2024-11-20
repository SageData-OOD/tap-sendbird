"""REST client handling, including SendBirdStream base class."""

import backoff
import requests
from typing import Callable, Iterable, Any

from singer_sdk.exceptions import FatalAPIError, RetriableAPIError
from singer_sdk.helpers.jsonpath import extract_jsonpath
from singer_sdk.streams import RESTStream
from singer_sdk.authenticators import APIKeyAuthenticator



class SendBirdStream(RESTStream):
    """SendBird stream class."""
    url_base = f"https://api-PLACEHOLDER.sendbird.com/v3"
    records_jsonpath = "$[*]"  # Or override `parse_response`.
    next_page_token_jsonpath = "$.next"  # Or override `get_next_page_token`.

    def __init__(self, tap, name=None, schema=None, path=None):
        super().__init__(tap, name, schema, path)
        self.url_base = f"https://api-{self.config['app_id']}.sendbird.com/v3"

    @property
    def authenticator(self):
        return APIKeyAuthenticator(
            stream=self,
            value=self.config["api_token"],
            key="Api-Token"
        )
    
    # @property
    # def http_headers(self) -> dict:
    #     """Return the http headers needed."""
    #     headers = {}
    #     if "user_agent" in self.config:
    #         headers["User-Agent"] = self.config.get("user_agent")
    #     return headers

    def get_url_params(
        self, context: dict, next_page_token
    ) -> dict[str, Any]:
        
        url_params: dict[str, Any] = {
            "limit": 100
        }

        if self.replication_key:
            url_params[self.replication_key] = self.get_starting_timestamp(context)

        if next_page_token is not None:
            url_params["token"] = next_page_token

        return url_params


    def parse_response(self, response: requests.Response) -> Iterable[dict]:
        """Parse the response and return an iterator of result rows."""
        yield from extract_jsonpath(self.records_jsonpath, input=response.json())

    def validate_response(self, response: requests.Response) -> None:
        if response.status_code == 429:
            msg = (
                f"{response.status_code} Server Error: "
                f"{response.reason} for path: {self.path}"
            )
            raise RetriableAPIError(msg)
        elif 400 <= response.status_code < 500:
            msg = (
                f"{response.status_code} Client Error: "
                f"{response.reason} for path: {self.path}"
            )
            raise FatalAPIError(msg)

        elif 500 <= response.status_code < 600:
            msg = (
                f"{response.status_code} Server Error: "
                f"{response.reason} for path: {self.path}"
            )
            raise RetriableAPIError(msg)

    def request_decorator(self, func: Callable) -> Callable:
        decorator: Callable = backoff.on_exception(
            backoff.expo,
            (RetriableAPIError,),
            max_tries=10,
            factor=4,
        )(func)
        return decorator
