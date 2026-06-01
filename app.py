from flask import Flask, render_template, request, send_file
from dotenv import load_dotenv
import os

from services.transcript_service import (
    extract_video_id,
    get_transcript
)

from services.ai_service import generate_notes
from services.pdf_service import create_pdf

load_dotenv()

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():

    youtube_url = request.form['youtube_url']

    try:
        # Extract Video ID
        video_id = extract_video_id(youtube_url)

        if not video_id:
            return render_template(
                'index.html',
                error="Invalid YouTube URL."
            )

        # Get Transcript
        transcript = get_transcript(youtube_url)

        # Handle Transcript Errors
        if (
            "Error" in transcript
            or "No transcript" in transcript
            or "not available" in transcript
            or "Failed" in transcript
        ):
            return render_template(
                'index.html',
                error=transcript
            )

        # Generate AI Notes
        notes = generate_notes(transcript)

        # Create PDF
        pdf_path = create_pdf(notes)

        return send_file(
            pdf_path,
            as_attachment=True
        )

    except Exception as e:
        return render_template(
            'index.html',
            error=f"Error: {str(e)}"
        )


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )