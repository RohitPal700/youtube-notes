import os
import re
import uuid
from fpdf import FPDF

# Directory where generated PDFs are stored
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------- Palette ----------
INK = (35, 31, 27)
SOFT_INK = (110, 102, 90)
AMBER = (194, 112, 11)
TEAL = (20, 92, 84)

HIGHLIGHT_BG = (255, 221, 92)     # marker-yellow, for important inline phrases
H1_TINT_BG = (255, 240, 199)      # soft amber tint behind H1 headings
H2_TINT_BG = (240, 244, 234)      # soft neutral tint behind H2 pill

# Accent colors cycled per H2 section so the doc doesn't look monotone
SECTION_ACCENTS = [
    (194, 112, 11),    # amber
    (31, 95, 88),      # teal
    (157, 60, 90),     # plum
    (43, 92, 158),     # blue
]


def _sanitize(text):
    """
    The built-in core fonts only support latin-1. AI-generated notes
    often contain smart quotes, em-dashes, or emoji that would
    otherwise crash fpdf. Replace anything unsupported with a safe
    equivalent instead of erroring out.
    """
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u2022": "-", "\u2026": "...",
        "\u2192": "->",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


def _strip_inline_markdown(text):
    """Remove markdown bold/italic markers, keep the plain text (used for headings)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    return text.strip()


def _tokenize_inline(text):
    """
    Split a line into (word, is_important) tokens. Anything wrapped in
    **double asterisks** is treated as an important point and rendered
    with a highlighter background later.
    """
    tokens = []
    parts = re.split(r"(\*\*[^*]+?\*\*)", text)
    for part in parts:
        if not part:
            continue
        important = part.startswith("**") and part.endswith("**")
        content = part[2:-2] if important else part
        for word in content.split(" "):
            if word:
                tokens.append((word, important))
    return tokens


class NotesPDF(FPDF):
    def header(self):
        # Colored title band on every page
        self.set_fill_color(*INK)
        self.rect(0, 0, self.w, 22, "F")
        self.set_xy(12, 6)
        self.set_text_color(*AMBER)
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Study Notes", ln=0)
        self.set_y(26)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(*SOFT_INK)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _render_inline(pdf, text, font_size, base_color, indent_x, page_bottom, line_height=6.5):
    """
    Word-wraps `text` manually so that words marked with **bold** get a
    yellow highlighter rectangle drawn behind them — true inline
    "important point" highlighting, not just bold text.
    """
    right_edge = pdf.w - pdf.r_margin
    space_w = pdf.get_string_width(" ")

    pdf.set_x(indent_x)
    if pdf.get_y() == 0:
        pdf.set_y(pdf.t_margin)

    for word, important in _tokenize_inline(text):
        pdf.set_font("Arial", "B" if important else "", font_size)
        word_w = pdf.get_string_width(word)

        # Wrap to next line if this word won't fit
        if pdf.get_x() + word_w > right_edge:
            new_y = pdf.get_y() + line_height
            if new_y + line_height > page_bottom:
                pdf.add_page()
                new_y = pdf.get_y()  # reset to the fresh page's top, not the stale overflow position
            pdf.set_xy(indent_x, new_y)

        x, y = pdf.get_x(), pdf.get_y()

        if important:
            pdf.set_fill_color(*HIGHLIGHT_BG)
            pdf.rect(x - 0.5, y + 0.7, word_w + 1, line_height - 1.4, "F")
            pdf.set_text_color(*INK)
        else:
            pdf.set_text_color(*base_color)

        pdf.set_xy(x, y)
        pdf.cell(word_w, line_height, word)
        pdf.set_xy(x + word_w + space_w, y)

    pdf.ln(line_height)


def _normalize_setext_headings(text):
    """
    Safety net: if the AI ever ignores the prompt and outputs Setext-style
    headings (a title line followed by a line of ===== or -----) instead of
    '#'/'##', convert them to proper markdown headings here so they're
    parsed and styled correctly instead of being rendered as plain text.
    """
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        current = lines[i]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if current.strip() and nxt and set(nxt) <= {"="} and len(nxt) >= 3:
            out.append("# " + current.strip())
            i += 2
            continue
        if current.strip() and nxt and set(nxt) <= {"-"} and len(nxt) >= 3:
            out.append("## " + current.strip())
            i += 2
            continue
        out.append(current)
        i += 1
    return "\n".join(out)


def create_pdf(notes):
    """
    Renders AI-generated markdown-ish notes into a colorful, structured
    PDF — headings get colored highlight bands, and any **bold** phrase
    in body text or bullets is rendered with a yellow highlighter behind
    it so important points stand out. Returns the absolute path to a
    uniquely-named file so concurrent requests never collide.
    """

    notes = _sanitize(notes)
    notes = _normalize_setext_headings(notes)

    pdf = NotesPDF()
    # We handle page breaks manually inside _render_inline (word-by-word,
    # so the highlighter rectangles stay aligned with the text). fpdf's
    # own automatic page-break, if left on, can fire independently mid-word
    # and desync the cursor — causing each subsequent word to land on its
    # own page. Keep it off and do our own bottom-of-page checks instead.
    pdf.set_auto_page_break(auto=False, margin=18)
    pdf.add_page()
    pdf.set_left_margin(12)
    pdf.set_right_margin(12)
    PAGE_BOTTOM = pdf.h - 18

    accent_index = -1
    current_accent = TEAL

    for raw_line in notes.split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            pdf.ln(3)
            continue

        # H1 — "# Heading" gets a soft highlighted band behind it
        if stripped.startswith("# "):
            text = _strip_inline_markdown(stripped[2:])
            pdf.ln(2)
            pdf.set_font("Arial", "B", 17)
            text_h = 10
            if pdf.get_y() + text_h + 4 > PAGE_BOTTOM:
                pdf.add_page()
            block_w = pdf.w - pdf.l_margin - pdf.r_margin
            y = pdf.get_y()
            pdf.set_fill_color(*H1_TINT_BG)
            pdf.rect(pdf.l_margin, y, block_w, text_h, "F")
            pdf.set_xy(pdf.l_margin + 3, y)
            pdf.set_text_color(*INK)
            pdf.cell(block_w - 6, text_h, text)
            pdf.ln(text_h + 4)
            continue

        # H2 — section headings, highlighted pill with cycling accent color
        if stripped.startswith("## ") or (stripped.endswith(":") and len(stripped) < 40 and stripped[:1].isalpha() and not stripped.isupper() and stripped[0].isupper() and "**" not in stripped and not stripped.startswith("-")):
            text = _strip_inline_markdown(stripped.lstrip("#").rstrip(":").strip())
            accent_index = (accent_index + 1) % len(SECTION_ACCENTS)
            current_accent = SECTION_ACCENTS[accent_index]
            pdf.ln(3)
            pdf.set_font("Arial", "B", 13)
            text_h = 9
            if pdf.get_y() + text_h + 3 > PAGE_BOTTOM:
                pdf.add_page()
            pill_w = pdf.get_string_width(text) + 14
            max_w = pdf.w - pdf.l_margin - pdf.r_margin
            pill_w = min(pill_w, max_w)
            y = pdf.get_y()
            pdf.set_fill_color(*H2_TINT_BG)
            pdf.rect(pdf.l_margin, y, pill_w, text_h, "F")
            pdf.set_fill_color(*current_accent)
            pdf.rect(pdf.l_margin, y, 2.6, text_h, "F")
            pdf.set_xy(pdf.l_margin + 6, y)
            pdf.set_text_color(*current_accent)
            pdf.cell(pill_w - 8, text_h, text)
            pdf.ln(text_h + 3)
            continue

        # H3 — "### Heading"
        if stripped.startswith("### "):
            text = _strip_inline_markdown(stripped[4:])
            if pdf.get_y() + 7 > PAGE_BOTTOM:
                pdf.add_page()
            pdf.set_x(pdf.l_margin)
            pdf.set_text_color(*current_accent)
            pdf.set_font("Arial", "B", 11.5)
            pdf.multi_cell(0, 7, text)
            continue

        # Bullet points — "- item" or "* item" (supports inline **highlights**)
        if stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:]
            if pdf.get_y() + 6.5 > PAGE_BOTTOM:
                pdf.add_page()
            pdf.set_text_color(*current_accent)
            pdf.set_font("Arial", "B", 11)
            pdf.set_x(pdf.l_margin)
            y = pdf.get_y()
            pdf.cell(6, 6.5, "-")
            pdf.set_xy(pdf.l_margin + 6, y)
            _render_inline(pdf, text, 11, INK, pdf.l_margin + 6, PAGE_BOTTOM)
            continue

        # Numbered list — "1. item" (supports inline **highlights**)
        numbered = re.match(r"^(\d+)[\.\)]\s+(.*)", stripped)
        if numbered:
            num, text = numbered.group(1), numbered.group(2)
            if pdf.get_y() + 6.5 > PAGE_BOTTOM:
                pdf.add_page()
            pdf.set_text_color(*current_accent)
            pdf.set_font("Arial", "B", 11)
            pdf.set_x(pdf.l_margin)
            y = pdf.get_y()
            pdf.cell(8, 6.5, f"{num}.")
            pdf.set_xy(pdf.l_margin + 8, y)
            _render_inline(pdf, text, 11, INK, pdf.l_margin + 8, PAGE_BOTTOM)
            continue

        # Plain paragraph text (supports inline **highlights**)
        if pdf.get_y() + 6.5 > PAGE_BOTTOM:
            pdf.add_page()
        pdf.set_font("Arial", "", 11)
        _render_inline(pdf, stripped, 11, INK, pdf.l_margin, PAGE_BOTTOM)

    filename = f"youtube_notes_{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    pdf.output(filepath)

    return filepath