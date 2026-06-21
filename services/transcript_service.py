import re
import os
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
from dotenv import load_dotenv

load_dotenv()

WEBSHARE_USERNAME = os.getenv("WEBSHARE_USERNAME")
WEBSHARE_PASSWORD = os.getenv("WEBSHARE_PASSWORD")


def _get_api():
    """
    Returns a YouTubeTranscriptApi instance.
    If Webshare credentials are set in .env, uses rotating residential
    proxies to avoid YouTube's cloud-IP block. Falls back to direct
    connection if credentials are missing (useful for local dev).
    """
    if WEBSHARE_USERNAME and WEBSHARE_PASSWORD:
        proxy_config = WebshareProxyConfig(
            proxy_username=WEBSHARE_USERNAME,
            proxy_password=WEBSHARE_PASSWORD,
        )
        return YouTubeTranscriptApi(proxy_config=proxy_config)
    return YouTubeTranscriptApi()


def extract_video_id(url):

    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be\/([a-zA-Z0-9_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def get_transcript(video_url):

    try:

        video_id = extract_video_id(video_url)

        if not video_id:
            return "ERROR: Invalid YouTube URL"

        preferred_languages = ["en", "en-US", "en-GB", "hi"]

        api = _get_api()

        # youtube-transcript-api >= 1.0 uses instance method api.fetch()
        # Older versions use static YouTubeTranscriptApi.get_transcript()
        if hasattr(api, 'fetch'):
            try:
                fetched = api.fetch(video_id, languages=preferred_languages)
            except Exception:
                transcript_list = api.list(video_id)
                first_transcript = next(iter(transcript_list))
                fetched = first_transcript.fetch()
            text = " ".join(snippet.text for snippet in fetched)
        else:
            # Fallback for older library versions
            try:
                transcript = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=preferred_languages
                )
            except Exception:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                first_transcript = next(iter(transcript_list))
                transcript = first_transcript.fetch()
            text = " ".join(item["text"] for item in transcript)

        if len(text.strip()) < 50:
            return "ERROR: Transcript too short"

        return text

    except Exception as e:

        print("Transcript Error:", str(e))
        return f"ERROR: {str(e)}"