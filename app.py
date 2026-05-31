from flask import Flask, render_template, request, send_file
from dotenv import load_dotenv

from services.transcript_service import extract_video_id, get_transcript
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
        video_id = extract_video_id(youtube_url)

        transcript = get_transcript(video_id)

        notes = generate_notes(transcript)

        pdf_path = create_pdf(notes)

        return send_file(pdf_path, as_attachment=True)

    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )