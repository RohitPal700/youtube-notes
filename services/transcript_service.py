import re
import os
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

WEBSHARE_USERNAME = os.getenv("WEBSHARE_USERNAME", "")
WEBSHARE_PASSWORD = os.getenv("WEBSHARE_PASSWORD", "")

_ERR_INVALID_URL = "ERROR: Invalid YouTube URL. Please check the link and try again."
_ERR_SHORT       = "ERROR: This video has no usable transcript."
_ERR_UNAVAILABLE = "ERROR: Unable to retrieve the transcript. Please try again later."


def _get_api() -> YouTubeTranscriptApi:
    """
    Returns a YouTubeTranscriptApi instance with WebshareProxyConfig when
    credentials are present. WebshareProxyConfig handles URL encoding of
    special characters internally — no manual quote() needed.
    Falls back to direct connection for local development.
    """
    if WEBSHARE_USERNAME and WEBSHARE_PASSWORD:
        proxy_config = WebshareProxyConfig(
            proxy_username=WEBSHARE_USERNAME,
            proxy_password=WEBSHARE_PASSWORD,
        )
        return YouTubeTranscriptApi(proxy_config=proxy_config)

    return YouTubeTranscriptApi()


def extract_video_id(url: str):
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be\/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_transcript(video_url: str) -> str:
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            return _ERR_INVALID_URL

        preferred_languages = ["en", "en-US", "en-GB", "hi"]
        api = _get_api()

        try:
            fetched = api.fetch(video_id, languages=preferred_languages)
        except Exception:
            # Fall back to first available language transcript
            transcript_list = api.list(video_id)
            first_transcript = next(iter(transcript_list))
            fetched = first_transcript.fetch()

        text = " ".join(snippet.text for snippet in fetched)

        if len(text.strip()) < 50:
            return _ERR_SHORT

        return text

    except Exception as e:
        # Log full error server-side only — never expose to client
        logger.error("Transcript fetch failed for %s: %s", video_url, str(e))
        return _ERR_UNAVAILABLE