"""Renders a tailored resume into a PDF matching the layout of Sid's
original uploaded resume: name as a large header, title/contact line
underneath, then section headers (SUMMARY, EDUCATION, SKILLS, EXPERIENCE,
PROJECTS) each with bolded sub-headers and bullet lists. Single page,
same visual structure — just reordered/reworded content per posting.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

NAME_STYLE = ParagraphStyle(
    "Name", fontName="Helvetica-Bold", fontSize=18, leading=22, spaceAfter=2,
)
TITLE_STYLE = ParagraphStyle(
    "TitleLine", fontName="Helvetica", fontSize=10.5, leading=13, spaceAfter=2,
)
CONTACT_STYLE = ParagraphStyle(
    "Contact", fontName="Helvetica", fontSize=9, leading=12, spaceAfter=10,
    textColor="#444444",
)
SECTION_HEADER_STYLE = ParagraphStyle(
    "SectionHeader", fontName="Helvetica-Bold", fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=4, textColor="#1a1a1a",
)
SUBHEADER_STYLE = ParagraphStyle(
    "SubHeader", fontName="Helvetica-Bold", fontSize=9.5, leading=13, spaceBefore=4,
)
BODY_STYLE = ParagraphStyle(
    "Body", fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_LEFT,
)
BULLET_STYLE = ParagraphStyle(
    "Bullet", fontName="Helvetica", fontSize=9.5, leading=13, leftIndent=14,
    spaceAfter=2, bulletIndent=4,
)


def render_resume_pdf(resume: dict, output_path: str | Path) -> Path:
    """resume dict shape:
    {
      "name": str, "title_line": str, "contact_line": str,
      "summary": str,
      "education": [{"school": str, "detail": str, "dates": str, "notes": [str]}],
      "skills": [{"category": str, "items": str}],
      "experience": [{"role": str, "org": str, "location": str, "dates": str, "bullets": [str]}],
      "projects": [{"name": str, "link": str, "bullets": [str]}],
    }
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    story = []

    story.append(Paragraph(resume.get("name", ""), NAME_STYLE))
    if resume.get("title_line"):
        story.append(Paragraph(resume["title_line"], TITLE_STYLE))
    if resume.get("contact_line"):
        story.append(Paragraph(resume["contact_line"], CONTACT_STYLE))

    if resume.get("summary"):
        story.append(Paragraph("PROFESSIONAL SUMMARY", SECTION_HEADER_STYLE))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#cccccc"))
        story.append(Spacer(1, 4))
        story.append(Paragraph(resume["summary"], BODY_STYLE))

    if resume.get("education"):
        story.append(Paragraph("EDUCATION", SECTION_HEADER_STYLE))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#cccccc"))
        for edu in resume["education"]:
            header = f"{edu.get('school', '')}, {edu.get('detail', '')} — {edu.get('dates', '')}"
            story.append(Paragraph(header, SUBHEADER_STYLE))
            for note in edu.get("notes", []):
                story.append(Paragraph(f"• {note}", BULLET_STYLE))

    if resume.get("skills"):
        story.append(Paragraph("SKILLS", SECTION_HEADER_STYLE))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#cccccc"))
        story.append(Spacer(1, 4))
        for skill_group in resume["skills"]:
            line = f"<b>{skill_group.get('category', '')}:</b> {skill_group.get('items', '')}"
            story.append(Paragraph(line, BODY_STYLE))

    if resume.get("experience"):
        story.append(Paragraph("EXPERIENCE", SECTION_HEADER_STYLE))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#cccccc"))
        for job in resume["experience"]:
            header = f"{job.get('role', '')}, {job.get('org', '')} — {job.get('location', '')}"
            story.append(Paragraph(header, SUBHEADER_STYLE))
            if job.get("dates"):
                story.append(Paragraph(job["dates"], BODY_STYLE))
            for bullet in job.get("bullets", []):
                story.append(Paragraph(f"• {bullet}", BULLET_STYLE))

    if resume.get("projects"):
        story.append(Paragraph("PROJECTS", SECTION_HEADER_STYLE))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#cccccc"))
        for proj in resume["projects"]:
            name = proj.get("name", "")
            link = f" ({proj['link']})" if proj.get("link") else ""
            story.append(Paragraph(f"{name}{link}", SUBHEADER_STYLE))
            for bullet in proj.get("bullets", []):
                story.append(Paragraph(f"• {bullet}", BULLET_STYLE))

    doc.build(story)
    return output_path
