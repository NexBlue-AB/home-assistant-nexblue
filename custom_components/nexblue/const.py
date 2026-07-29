"""Constants for the NexBlue integration."""

from datetime import timedelta

DOMAIN = "nexblue"
CONF_USERNAME = "username"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_API_BASE_URL = "api_base_url"
PLATFORMS = ["sensor", "switch"]
PRODUCTION_API_URL = "https://api.nexblue.com/third_party"
DEFAULT_API_URL = PRODUCTION_API_URL
UPDATE_INTERVAL = timedelta(minutes=1)
