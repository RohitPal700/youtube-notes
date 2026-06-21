import re
from youtube_transcript_api import YouTubeTranscriptApi


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

        # Preferred languages, in order. If none of these are
        # available we fall back to whatever language the video
        # actually has (many videos only have auto-generated
        # transcripts in their original language, e.g. Hindi).
        preferred_languages = ["en", "en-US", "en-GB", "hi"]

        # youtube-transcript-api >= 1.0 replaced the old static
        # YouTubeTranscriptApi.get_transcript(video_id) with an
        # instance method: YouTubeTranscriptApi().fetch(video_id).
        # Support both so this works regardless of installed version.
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            try:
                transcript = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=preferred_languages
                )
            except Exception:
                # Fall back to the first available transcript,
                # whatever language it's in.
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                first_transcript = next(iter(transcript_list))
                transcript = first_transcript.fetch()
            text = " ".join(item["text"] for item in transcript)
        else:
            api = YouTubeTranscriptApi()
            try:
                fetched = api.fetch(video_id, languages=preferred_languages)
            except Exception:
                transcript_list = api.list(video_id)
                first_transcript = next(iter(transcript_list))
                fetched = first_transcript.fetch()
            text = " ".join(snippet.text for snippet in fetched)

        if len(text.strip()) < 50:
            return "ERROR: Transcript too short"

        return text

    except Exception as e:

        print("Transcript Error:", str(e))
        return f"ERROR: {str(e)}"