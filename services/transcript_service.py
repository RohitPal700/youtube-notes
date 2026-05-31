from youtube_transcript_api import YouTubeTranscriptApi
import re

def extract_video_id(url):

    pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"

    match = re.search(pattern, url)

    if match:
        return match.group(1)

    raise Exception("Invalid YouTube URL")


def get_transcript(video_id):

    api = YouTubeTranscriptApi()

    transcript = api.fetch(video_id, languages=['en-IN', 'en', 'hi'])

    full_text = ""

    for entry in transcript:
        full_text += entry.text + " "

    return full_text