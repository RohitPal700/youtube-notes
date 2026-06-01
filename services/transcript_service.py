import re
import requests
import yt_dlp


def extract_video_id(url):
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)

    if match:
        return match.group(1)

    return None


def get_transcript(video_url):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

            subtitles = (
                info.get("automatic_captions")
                or info.get("subtitles")
            )

            if not subtitles:
                return "No transcript available."

            en_subs = subtitles.get("en")

            if not en_subs:
                return "English transcript not available."

            subtitle_url = en_subs[0]["url"]

            response = requests.get(subtitle_url)

            if response.status_code != 200:
                return "Failed to download transcript."

            transcript_xml = response.text

            # Remove XML tags
            clean_text = re.sub(r"<.*?>", "", transcript_xml)

            return clean_text

    except Exception as e:
        return f"Transcript Error: {str(e)}"