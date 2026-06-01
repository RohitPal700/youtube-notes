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
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                video_url,
                download=False
            )

            subtitles = (
                info.get("automatic_captions")
                or info.get("subtitles")
            )

            if not subtitles:
                return "No transcript available."

            subtitle_url = None

            # Find English subtitles
            for key in subtitles:

                if "en" in key.lower():

                    subtitle_list = subtitles[key]

                    if (
                        subtitle_list
                        and "url" in subtitle_list[0]
                    ):

                        subtitle_url = subtitle_list[0]["url"]
                        break

            if not subtitle_url:
                return "English transcript not available."

            response = requests.get(subtitle_url)

            if response.status_code != 200:
                return "Failed to download transcript."

            transcript_xml = response.text

            # Remove XML tags
            clean_text = re.sub(
                r"<.*?>",
                " ",
                transcript_xml
            )

            # Remove extra spaces
            clean_text = re.sub(
                r"\s+",
                " ",
                clean_text
            )

            # Remove very short transcript
            if len(clean_text.strip()) < 50:
                return "Transcript too short."

            return clean_text

    except Exception as e:

        return f"Transcript Error: {str(e)}"