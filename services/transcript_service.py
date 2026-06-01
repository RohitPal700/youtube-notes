import yt_dlp

def get_transcript(video_url):
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "quiet": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

        subtitles = info.get("automatic_captions") or info.get("subtitles")

        if not subtitles:
            return "No transcript available"

        en_subs = subtitles.get("en")

        if not en_subs:
            return "English transcript not available"

        return en_subs[0]["url"]