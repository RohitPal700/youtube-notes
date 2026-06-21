import os
from flask import Flask, render_template, request, send_file
from services.transcript_service import get_transcript
from services.ai_service import generate_notes
from services.pdf_service import create_pdf

app = Flask(__name__)

# Toggle via environment variable instead of hardcoding True.
# Defaults to False so it's never accidentally left on in production.
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():

    youtube_url = request.form.get("youtube_url", "").strip()

    if not youtube_url:
        return render_template(
            "index.html",
            error="Please enter a YouTube URL."
        )

    pdf_path = None

    try:

        transcript = get_transcript(youtube_url)

        if transcript.startswith("ERROR"):
            return render_template(
                "index.html",
                error=transcript
            )

        notes = generate_notes(transcript)

        if notes.startswith("ERROR"):
            return render_template(
                "index.html",
                error=notes
            )

        pdf_path = create_pdf(notes)

        response = send_file(
            pdf_path,
            as_attachment=True,
            download_name="youtube_notes.pdf"
        )

        # Clean up the generated file once it has been streamed to
        # the client, so /generated doesn't grow unbounded over time.
        @response.call_on_close
        def _cleanup():
            try:
                if pdf_path and os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except OSError:
                pass

        return response

    except Exception as e:

        # Best-effort cleanup if something failed after the PDF was written.
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass

        return render_template(
            "index.html",
            error=f"Error: {str(e)}"
        )


if __name__ == "__main__":
    app.run(
        debug=DEBUG,
        host="0.0.0.0",
        port=5000
    )