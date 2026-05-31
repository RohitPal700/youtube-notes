from groq import Groq
import os
from dotenv import load_dotenv
import re

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# Split transcript into chunks
def chunk_text(text, chunk_size=4000):

    chunks = []

    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i + chunk_size])

    return chunks


# Clean transcript
def clean_text(text):

    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text)

    # Remove weird unicode chars
    text = text.encode("utf-8", "ignore").decode("utf-8")

    return text


def generate_notes(transcript):

    # Clean transcript first
    transcript = clean_text(transcript)

    chunks = chunk_text(transcript)

    all_notes = []

    for chunk in chunks:

        prompt = f"""
You are a smart study notes generator.

Create clean, easy-to-read study notes from this transcript.

Rules:
- Use headings
- Use bullet points
- Keep notes short
- Remove unnecessary talking
- Keep important concepts only
- If transcript language is Hindi, generate notes in English

Transcript:
{chunk}
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=700
        )

        notes = response.choices[0].message.content

        # UTF-8 safe
        notes = notes.encode(
            "utf-8",
            "ignore"
        ).decode("utf-8")

        all_notes.append(notes)

    final_notes_text = "\n\n".join(all_notes)

    final_prompt = f"""
Create final structured study notes from these sections.

Rules:
- Proper headings
- Bullet points
- Clean formatting
- Easy for revision
- Remove repetition

Notes:
{final_notes_text}
"""

    final_response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "user",
                "content": final_prompt
            }
        ],
        temperature=0.3,
        max_tokens=1500
    )

    final_notes = final_response.choices[0].message.content

    final_notes = final_notes.encode(
        "utf-8",
        "ignore"
    ).decode("utf-8")

    return final_notes