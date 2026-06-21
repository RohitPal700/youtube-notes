import os
import logging
from flask import Flask, render_template, request, send_file
from services.transcript_service import get_transcript
from services.ai_service import generate_notes
from services.pdf_service import create_pdf

# Configure logging once at app startup — all modules inherit this config.
# In production, change level to WARNING and point to a file or log aggregator.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# Generic message shown when an unexpected exception escapes all service layers.
_ERR_GENERIC = "Unable to process the video. Please try again later."


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():

    youtube_url = request.form.get("youtube_url", "").strip()

    if not youtube_url:
        return render_template("index.html", error="Please enter a YouTube URL.")

    pdf_path = None

    try:
        transcript = get_transcript(youtube_url)

        if transcript.startswith("ERROR"):
            # Service already returned a safe, user-friendly message
            return render_template("index.html", error=transcript[7:].strip())

        notes = generate_notes(transcript)

        if notes.startswith("ERROR"):
            return render_template("index.html", error=notes[7:].strip())

        pdf_path = create_pdf(notes)

        response = send_file(
            pdf_path,
            as_attachment=True,
            download_name="youtube_notes.pdf",
        )

        @response.call_on_close
        def _cleanup():
            try:
                if pdf_path and os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except OSError:
                pass

        return response

    except Exception as e:
        # Log full details server-side; show only a generic message to user.
        logger.error("Unhandled exception in /generate: %s", str(e), exc_info=True)

        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass

        return render_template("index.html", error=_ERR_GENERIC)


if __name__ == "__main__":
    app.run(debug=DEBUG, host="0.0.0.0", port=5000)