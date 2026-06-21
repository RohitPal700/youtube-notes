import re
import os
import logging
from urllib.parse import quote
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

WEBSHARE_USERNAME = os.getenv("WEBSHARE_USERNAME", "")
WEBSHARE_PASSWORD = os.getenv("WEBSHARE_PASSWORD", "")

# User-facing messages — never expose credentials or internal details
_ERR_INVALID_URL   = "ERROR: Invalid YouTube URL. Please check the link and try again."
_ERR_SHORT         = "ERROR: This video has no usable transcript."
_ERR_UNAVAILABLE   = "ERROR: Unable to retrieve the transcript. Please try again later."


def _build_proxy_url(username: str, password: str) -> str:
    """
    Build a Webshare rotating-proxy URL with properly URL-encoded credentials.
    Special characters (#, @, %, &, etc.) in the password are percent-encoded
    so they never break URL parsing.
    """
    safe_user = quote(username, safe="")
    safe_pass = quote(password, safe="")
    return f"http://{safe_user}-rotate:{safe_pass}@p.webshare.io:80/"


def _get_api() -> YouTubeTranscriptApi:
    """
    Return a YouTubeTranscriptApi instance.
    Uses Webshare rotating proxies when credentials are present in the
    environment — required on cloud hosts where YouTube blocks the server IP.
    Falls back to a direct connection for local development.
    """
    if WEBSHARE_USERNAME and WEBSHARE_PASSWORD:
        proxy_url = _build_proxy_url(WEBSHARE_USERNAME, WEBSHARE_PASSWORD)
        proxies = {"http": proxy_url, "https": proxy_url}

        # youtube-transcript-api >= 1.0 accepts a proxies dict directly
        # on the constructor; older versions do not have this parameter.
        try:
            return YouTubeTranscriptApi(proxies=proxies)
        except TypeError:
            # Older API version — no proxies kwarg; the caller will use the
            # static methods which also accept a proxies dict.
            return YouTubeTranscriptApi()

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

        # Support both youtube-transcript-api >= 1.0 (instance .fetch())
        # and older versions (static .get_transcript()).
        if hasattr(api, "fetch"):
            try:
                fetched = api.fetch(video_id, languages=preferred_languages)
            except Exception:
                transcript_list = api.list(video_id)
                first_transcript = next(iter(transcript_list))
                fetched = first_transcript.fetch()
            text = " ".join(snippet.text for snippet in fetched)

        else:
            # Older library — pass proxies via requests_kwargs if available
            proxy_kwargs = {}
            if WEBSHARE_USERNAME and WEBSHARE_PASSWORD:
                proxy_url = _build_proxy_url(WEBSHARE_USERNAME, WEBSHARE_PASSWORD)
                proxy_kwargs = {"proxies": {"http": proxy_url, "https": proxy_url}}

            try:
                transcript = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=preferred_languages, **proxy_kwargs
                )
            except Exception:
                transcript_list = YouTubeTranscriptApi.list_transcripts(
                    video_id, **proxy_kwargs
                )
                first_transcript = next(iter(transcript_list))
                transcript = first_transcript.fetch()
            text = " ".join(item["text"] for item in transcript)

        if len(text.strip()) < 50:
            return _ERR_SHORT

        return text

    except Exception as e:
        # Log full details server-side only — never send to the client
        logger.error("Transcript fetch failed for %s: %s", video_url, str(e))
        return _ERR_UNAVAILABLE