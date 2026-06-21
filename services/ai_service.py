import re
import logging
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-2.5-flash"  # swap to "gemini-2.5-pro" for higher quality

CHUNK_SIZE = 30000   # ~7-8K tokens per chunk, well within Gemini's 1M context
MAX_CHUNKS = 12      # covers ~3-4 hour videos

# User-facing messages — no internal details exposed
_ERR_SHORT        = "ERROR: This video's transcript is too short to generate notes."
_ERR_EMPTY        = "ERROR: Unable to generate notes. Please try again later."
_ERR_RATE_LIMIT   = "ERROR: The service is temporarily busy. Please try again in a few minutes."
_ERR_AI_GENERIC   = "ERROR: Unable to process the video. Please try again later."

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
    """Split on whitespace near chunk_size so we never cut a word in half."""
    chunks = []
    start = 0
    length = len(transcript)

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            space = transcript.rfind(" ", start, end)
            if space > start:
                end = space
        chunks.append(transcript[start:end].strip())
        start = end

    return [c for c in chunks if c]


def _call_gemini(prompt: str, max_output_tokens: int) -> tuple[str, str]:
    """Single Gemini call. Returns (text, finish_reason)."""
    model = genai.GenerativeModel(MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=max_output_tokens,
        ),
    )
    finish = response.candidates[0].finish_reason.name
    finish_reason = "length" if finish == "MAX_TOKENS" else "stop"
    return response.text or "", finish_reason


def _summarize_chunk(chunk_text, part_number, total_parts) -> str:
    prompt = f"""
You are taking detailed raw notes on PART {part_number} of {total_parts} of a longer
YouTube video transcript. Do NOT write an introduction, conclusion, or key takeaways —
just capture everything important in this part as clear bullet points in order.
Keep names, numbers, and definitions accurate. Remove filler words. Simple language.

Transcript part {part_number}/{total_parts}:
{chunk_text}
"""
    text, _ = _call_gemini(prompt, max_output_tokens=2500)
    return text


def _synthesize_final_notes(raw_notes_combined) -> tuple[str, str]:
    prompt = f"""
You are an expert note-taking assistant. Below are raw notes covering an ENTIRE YouTube
video, collected part by part. Turn them into a single, well-organized study notes
document that covers everything from start to finish — do not drop any part.

{FORMAT_RULES}

Content requirements:
- One clear "# " title for the whole video
- Group related points under sensible "## " section headings
- Bullet lists for details
- A single "## Key Takeaways" section at the end
- Simple, beginner-friendly language
- Output in English

Raw notes from all parts:
{raw_notes_combined}
"""
    return _call_gemini(prompt, max_output_tokens=8192)


def _notes_for_single_chunk(transcript) -> tuple[str, str]:
    prompt = f"""
You are an expert note-taking assistant.
Convert the following YouTube transcript into structured study notes from beginning to end.

{FORMAT_RULES}

Content requirements:
- Clear section headings for every distinct topic
- Bullet lists for details
- A "## Key Takeaways" section with the most important conclusions
- Simple, beginner-friendly language
- Remove filler words
- Output in English

Transcript:
{transcript}
"""
    return _call_gemini(prompt, max_output_tokens=8192)


def generate_notes(transcript: str) -> str:
    try:
        if not transcript or len(transcript.strip()) < 50:
            return _ERR_SHORT

        transcript = transcript.strip()
        chunks = _split_into_chunks(transcript)

        was_capped = len(chunks) > MAX_CHUNKS
        if was_capped:
            chunks = chunks[:MAX_CHUNKS]

        if len(chunks) <= 1:
            notes, finish_reason = _notes_for_single_chunk(transcript[:CHUNK_SIZE])
        else:
            total = len(chunks)
            raw_parts = []
            for i, chunk in enumerate(chunks, start=1):
                part_notes = _summarize_chunk(chunk, i, total)
                raw_parts.append(f"--- Part {i} ---\n{part_notes}")
            combined_raw = "\n\n".join(raw_parts)
            notes, finish_reason = _synthesize_final_notes(combined_raw)

        if not notes or not notes.strip():
            logger.error("Gemini returned empty response")
            return _ERR_EMPTY

        if finish_reason == "length":
            notes += (
                "\n\n## Note\n"
                "- **These notes were cut off** because the video is extremely long. "
                "Consider trying a shorter video."
            )
        elif was_capped:
            notes += (
                "\n\n## Note\n"
                "- **This video is very long**, so notes cover "
                f"the first {MAX_CHUNKS} sections of the transcript only."
            )

        return notes

    except ResourceExhausted as e:
        logger.warning("Gemini rate limit hit: %s", str(e))
        return _ERR_RATE_LIMIT

    except GoogleAPIError as e:
        logger.error("Gemini API error: %s", str(e))
        return _ERR_AI_GENERIC

    except Exception as e:
        logger.error("Unexpected error in generate_notes: %s", str(e))
        return _ERR_AI_GENERIC