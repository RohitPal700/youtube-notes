import re
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError
from dotenv import load_dotenv
import os

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-2.5-flash"   # free-tier friendly; swap to "gemini-2.5-pro" for better quality

# Each chunk stays well under Gemini 2.5 Flash's 1M token context window.
# 30000 chars ~ 7-8K tokens, very safe per call.
CHUNK_SIZE = 30000

# Gemini 2.5 Flash has a generous free-tier quota, so we can safely handle
# longer videos. 12 chunks covers roughly a 3-4 hour video.
MAX_CHUNKS = 12

FORMAT_RULES = """
Format the output using EXACTLY this markdown style (this is required, not optional,
because the output is rendered into a styled PDF):
- Use "# " for the single main title at the top.
- Use "## " for each section heading (e.g. "## Key Points", "## Key Takeaways").
- Do NOT use Setext-style headings (no lines made of ===== or ----- underneath a title).
- Use "- " for bullet points and "1. " for numbered lists.
- Wrap genuinely important words or phrases in **double asterisks** so they stand out —
  use this for key terms, numbers, names, and conclusions, but don't overdo it
  (roughly 1-3 highlighted phrases per bullet/paragraph, not entire sentences).
"""


def _split_into_chunks(transcript, chunk_size=CHUNK_SIZE):
    """Split on whitespace near chunk_size so we don't cut a word in half."""
    chunks = []
    start = 0
    length = len(transcript)

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            # back up to the nearest space so we don't split mid-word
            space = transcript.rfind(" ", start, end)
            if space > start:
                end = space
        chunks.append(transcript[start:end].strip())
        start = end

    return [c for c in chunks if c]


def _summarize_chunk(chunk_text, part_number, total_parts):
    """Turn one transcript chunk into raw bullet notes (no final formatting yet)."""
    prompt = f"""
You are taking detailed raw notes on PART {part_number} of {total_parts} of a longer
YouTube video transcript. This is only one part of the full video, so do NOT write an
introduction, conclusion, or "key takeaways" section here — just capture everything
important that happens in this part as clear bullet points, in the order it's discussed.
Keep names, numbers, and definitions accurate. Remove filler words. Simple language.

Transcript part {part_number}/{total_parts}:
{chunk_text}
"""
    model = genai.GenerativeModel(MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.3, max_output_tokens=2500),
    )
    return response.text or ""


def _synthesize_final_notes(raw_notes_combined):
    """Turn the combined raw bullet notes from all parts into one polished document."""
    prompt = f"""
You are an expert note-taking assistant. Below are raw notes covering an ENTIRE YouTube
video, collected part by part. Turn them into a single, well-organized study notes
document that covers everything from start to finish — do not drop any part.

{FORMAT_RULES}

Content requirements:
- One clear "# " title for the whole video
- Group related points under sensible "## " section headings (merge near-duplicate
  points from adjacent parts instead of repeating them)
- Bullet lists for details
- A single "## Key Takeaways" section at the end summarizing the most important
  conclusions from the WHOLE video
- Simple, beginner-friendly language
- Output in English

Raw notes from all parts:
{raw_notes_combined}
"""
    model = genai.GenerativeModel(MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.3, max_output_tokens=8192),
    )
    finish_reason = "stop" if response.candidates[0].finish_reason.name != "MAX_TOKENS" else "length"
    return response.text or "", finish_reason


def _notes_for_single_chunk(transcript):
    """Fast path: short transcripts that fit in one call, formatted directly."""
    prompt = f"""
You are an expert note-taking assistant.

Convert the following YouTube transcript into structured study notes covering it from
beginning to end.

{FORMAT_RULES}

Content requirements:
- Clear section headings for every distinct topic covered in the transcript
- Bullet lists for details
- A "## Key Takeaways" section with the most important conclusions
- Simple, beginner-friendly language
- Remove filler words
- Output in English

Transcript:
{transcript}
"""
    model = genai.GenerativeModel(MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.3, max_output_tokens=8192),
    )
    finish_reason = "stop" if response.candidates[0].finish_reason.name != "MAX_TOKENS" else "length"
    return response.text or "", finish_reason


def _friendly_rate_limit_message(error):
    """
    Gemini's 429 error — surface a clean message so the user knows what to do.
    """
    return (
        "ERROR: The AI service has hit its quota limit. "
        "Please try again in a few minutes, or try a shorter video in the meantime."
    )


def generate_notes(transcript):

    try:

        if not transcript or len(transcript.strip()) < 50:
            return "ERROR: Transcript is too short."

        transcript = transcript.strip()
        chunks = _split_into_chunks(transcript)

        was_capped = len(chunks) > MAX_CHUNKS
        if was_capped:
            chunks = chunks[:MAX_CHUNKS]

        # Short video: a single call is faster and just as accurate.
        if len(chunks) <= 1:
            notes, finish_reason = _notes_for_single_chunk(transcript[:CHUNK_SIZE])
        else:
            # Long video: summarize each part, then merge everything into
            # one cohesive, fully-covered document.
            total = len(chunks)
            raw_parts = []
            for i, chunk in enumerate(chunks, start=1):
                part_notes = _summarize_chunk(chunk, i, total)
                raw_parts.append(f"--- Part {i} ---\n{part_notes}")

            combined_raw = "\n\n".join(raw_parts)
            notes, finish_reason = _synthesize_final_notes(combined_raw)

        if not notes or not notes.strip():
            return "ERROR: AI returned an empty response."

        # Let the user know if anything still had to be left out, instead
        # of silently handing back incomplete notes.
        if finish_reason == "length":
            notes += (
                "\n\n## Note\n"
                "- **These notes were cut off** because the video is extremely long. "
                "Consider asking for the video in shorter parts."
            )
        elif was_capped:
            notes += (
                "\n\n## Note\n"
                "- **This video is extremely long**, so notes were generated for "
                f"the first {MAX_CHUNKS} sections of the transcript only."
            )

        return notes

    except ResourceExhausted as e:

        return _friendly_rate_limit_message(e)

    except GoogleAPIError as e:

        return f"ERROR: AI service error. Please try again shortly. ({type(e).__name__})"

    except Exception as e:

        return f"ERROR: AI Error: {str(e)}"