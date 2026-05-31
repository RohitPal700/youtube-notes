from fpdf import FPDF


def create_pdf(notes, filename="youtube_notes.pdf"):

    pdf = FPDF()

    pdf.add_page()

    # Unicode font
    pdf.add_font(
        "DejaVu",
        "",
        "assets/fonts/DejaVuSans.ttf"
    )

    pdf.set_font("DejaVu", size=14)

    # Auto page break
    pdf.set_auto_page_break(auto=True, margin=15)

    # UTF-8 safe text
    pdf.multi_cell(0, 10, txt=notes)

    pdf.output(filename)

    return filename