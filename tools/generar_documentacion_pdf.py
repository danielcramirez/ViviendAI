from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "output" / "pdf" / "VIVI_ViviendAI_Documentacion_Tecnica.pdf"
AUDIT = ROOT / "docs" / "auditoria_tecnica.md"
LOGO = ROOT / "Logov2.png"

YELLOW = colors.HexColor("#FFD000")
BLUE = colors.HexColor("#0067B1")
GRAPHITE = colors.HexColor("#575756")
BLACK = colors.HexColor("#111111")
PALE_BLUE = colors.HexColor("#EAF4FB")
PALE_YELLOW = colors.HexColor("#FFF8D6")
LIGHT = colors.HexColor("#F4F6F8")
GREEN = colors.HexColor("#198754")
ORANGE = colors.HexColor("#F59E0B")
RED = colors.HexColor("#D92D20")
WHITE = colors.white


def register_fonts() -> tuple[str, str]:
    candidates = [
        (
            Path("C:/Windows/Fonts/aptos.ttf"),
            Path("C:/Windows/Fonts/aptosbd.ttf"),
        ),
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("ViviRegular", str(regular)))
            pdfmetrics.registerFont(TTFont("ViviBold", str(bold)))
            return "ViviRegular", "ViviBold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = register_fonts()


def para(text: str, style: ParagraphStyle) -> Paragraph:
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = text.replace("&", "&amp;")
    text = text.replace("&amp;lt;", "&lt;").replace("&amp;gt;", "&gt;")
    return Paragraph(text, style)


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="VTitle",
        fontName=FONT_BOLD,
        fontSize=28,
        leading=32,
        textColor=BLACK,
        spaceAfter=10,
    )
)
styles.add(
    ParagraphStyle(
        name="VSubTitle",
        fontName=FONT,
        fontSize=13,
        leading=18,
        textColor=GRAPHITE,
    )
)
styles.add(
    ParagraphStyle(
        name="VH1",
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=BLACK,
        spaceBefore=10,
        spaceAfter=8,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="VH2",
        fontName=FONT_BOLD,
        fontSize=14,
        leading=18,
        textColor=BLUE,
        spaceBefore=9,
        spaceAfter=5,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="VBody",
        fontName=FONT,
        fontSize=9.3,
        leading=13.2,
        textColor=GRAPHITE,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="VBullet",
        parent=styles["VBody"],
        leftIndent=12,
        firstLineIndent=-7,
        bulletIndent=0,
        spaceAfter=3,
    )
)
styles.add(
    ParagraphStyle(
        name="VSmall",
        fontName=FONT,
        fontSize=7.5,
        leading=10,
        textColor=GRAPHITE,
    )
)
styles.add(
    ParagraphStyle(
        name="VCardTitle",
        fontName=FONT_BOLD,
        fontSize=10,
        leading=12,
        textColor=BLACK,
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        name="VMetric",
        fontName=FONT_BOLD,
        fontSize=22,
        leading=24,
        textColor=BLUE,
        alignment=TA_CENTER,
    )
)


class Diagram(Flowable):
    def __init__(self, kind: str, height: float = 150):
        super().__init__()
        self.kind = kind
        self.width = 170 * mm
        self.height = height

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return avail_width, self.height

    def box(self, c, x, y, w, h, title, subtitle="", fill=WHITE, stroke=BLUE):
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
        c.setFillColor(BLACK)
        c.setFont(FONT_BOLD, 8)
        c.drawCentredString(x + w / 2, y + h - 12, title)
        if subtitle:
            c.setFillColor(GRAPHITE)
            c.setFont(FONT, 6.2)
            lines = subtitle.split("|")
            for i, line in enumerate(lines[:3]):
                c.drawCentredString(x + w / 2, y + h - 24 - i * 8, line)

    def arrow(self, c, x1, y1, x2, y2, label=""):
        c.setStrokeColor(GRAPHITE)
        c.setFillColor(GRAPHITE)
        c.setLineWidth(1)
        c.line(x1, y1, x2, y2)
        ang = 4
        c.line(x2, y2, x2 - ang, y2 + ang / 2)
        c.line(x2, y2, x2 - ang, y2 - ang / 2)
        if label:
            c.setFont(FONT, 5.8)
            c.drawCentredString((x1 + x2) / 2, y1 + 4, label)

    def draw(self):
        c = self.canv
        if self.kind == "architecture":
            labels = [
                ("Meta simulado", "Campaña | anuncio | UTM", PALE_YELLOW),
                ("Streamlit", "Formulario | experiencia", WHITE),
                ("Servicios Python", "finanzas | perfil | score", PALE_BLUE),
                ("SQLite", "leads | eventos | CRM sim.", WHITE),
                ("Make + Gemini", "orquestación | conversación", PALE_YELLOW),
                ("Telegram", "memoria | diálogo", PALE_BLUE),
            ]
            gap = 5
            w = (self.width - gap * 5) / 6
            y = 62
            for i, (title, sub, fill) in enumerate(labels):
                x = i * (w + gap)
                self.box(c, x, y, w, 55, title, sub, fill)
                if i < len(labels) - 1:
                    self.arrow(c, x + w, y + 27, x + w + gap, y + 27)
            c.setFillColor(BLUE)
            c.roundRect(0, 10, self.width, 30, 6, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont(FONT_BOLD, 8)
            c.drawCentredString(
                self.width / 2,
                27,
                "Objetivo productivo: Meta API · Supabase/HANA · Salesforce API · observabilidad",
            )
        elif self.kind == "make":
            titles = ["Webhook/Telegram", "Memoria", "Gemini", "Perfil JSON", "Score Python", "Respuesta"]
            gap = 7
            w = (self.width - gap * 5) / 6
            for i, title in enumerate(titles):
                x = i * (w + gap)
                fill = PALE_YELLOW if i in (0, 2) else PALE_BLUE if i in (1, 3) else WHITE
                self.box(c, x, 70, w, 44, title, "", fill)
                if i < 5:
                    self.arrow(c, x + w, 92, x + w + gap, 92)
            c.setFont(FONT_BOLD, 7)
            c.setFillColor(GRAPHITE)
            c.drawString(0, 42, "Actual:")
            c.setFont(FONT, 7)
            c.drawString(35, 42, "conversación y memoria; el perfil/score posterior aún no se cierra en Telegram.")
            c.setFillColor(GREEN)
            c.drawString(0, 25, "Objetivo:")
            c.setFillColor(GRAPHITE)
            c.drawString(35, 25, "salida estructurada validada + scoring determinístico + persistencia permanente.")
        elif self.kind == "sequence":
            actors = ["Cliente", "Streamlit", "Backend", "Make/Gemini", "CRM"]
            xs = [self.width * i / 4 for i in range(5)]
            for x, actor in zip(xs, actors):
                c.setFillColor(BLUE if actor in ("Backend", "CRM") else YELLOW)
                c.circle(x, 125, 12, fill=1, stroke=0)
                c.setFillColor(BLACK)
                c.setFont(FONT_BOLD, 7)
                c.drawCentredString(x, 104, actor)
                c.setStrokeColor(colors.HexColor("#B8C0C8"))
                c.setDash(2, 2)
                c.line(x, 96, x, 10)
            c.setDash()
            events = [
                (0, 1, 86, "clic + formulario"),
                (1, 2, 70, "POST contextual"),
                (2, 3, 54, "mensaje + historial"),
                (3, 2, 38, "respuesta VIVI"),
                (2, 4, 22, "Ficha + score"),
            ]
            for a, b, y, label in events:
                x1, x2 = xs[a], xs[b]
                if x1 < x2:
                    self.arrow(c, x1 + 12, y, x2 - 12, y, label)
                else:
                    self.arrow(c, x1 - 12, y, x2 + 12, y, label)
        elif self.kind == "erd":
            entities = [
                ("LEAD", "lead_id PK|document_hash|status|timestamps"),
                ("ATTRIBUTION", "lead_id FK|campaign|ad|UTM|project"),
                ("SESSION", "session_id PK|lead_id FK|channel"),
                ("TURN", "turn_id PK|session_id FK|role|message"),
                ("PROFILE", "lead_id FK|profile_json|version"),
                ("SCORE", "score_id PK|lead_id FK|value|reasons"),
                ("HANDOFF", "lead_id FK|advisor|CRM status"),
                ("SEPARATION", "lead_id FK|amount|date|status"),
            ]
            positions = [
                (0, 95), (self.width * .34, 95), (self.width * .68, 95),
                (self.width * .68, 25), (0, 25), (self.width * .34, 25),
                (self.width * .17, -45), (self.width * .57, -45),
            ]
            w = self.width * .29
            for (title, sub), (x, y) in zip(entities, positions):
                self.box(c, x, y + 50, w, 52, title, sub, WHITE, BLUE)
            self.arrow(c, w, 121, self.width * .34, 121, "1:1")
            self.arrow(c, self.width * .34 + w, 121, self.width * .68, 121, "1:N")
            self.arrow(c, self.width * .68 + w / 2, 95, self.width * .68 + w / 2, 77, "1:N")
            self.arrow(c, w / 2, 95, w / 2, 77, "1:1")
            self.arrow(c, self.width * .34 + w / 2, 95, self.width * .34 + w / 2, 77, "1:N")
        elif self.kind == "uml":
            comps = [
                ("CampaignService", "build_attribution()"),
                ("FinanceService", "estimate_subsidy()|max_payment()"),
                ("ProfilingService", "build_profile()|score_profile()"),
                ("LeadService", "save_lead()|sync_crm()"),
                ("MakeService", "send_message()|retry()"),
            ]
            w = self.width * .28
            coords = [(0, 85), (self.width*.36, 85), (self.width*.72, 85),
                      (self.width*.18, 15), (self.width*.57, 15)]
            for (title, sub), (x, y) in zip(comps, coords):
                self.box(c, x, y, w, 55, title, sub, PALE_BLUE if "Service" in title else WHITE)
            self.arrow(c, w, 112, self.width*.36, 112, "atribución")
            self.arrow(c, self.width*.36+w, 112, self.width*.72, 112, "reglas")
            self.arrow(c, self.width*.72+w/2, 85, self.width*.57+w/2, 70, "persistir")
            self.arrow(c, self.width*.18+w, 42, self.width*.57, 42, "integrar")
        elif self.kind == "state":
            states = ["NUEVO", "CONTACTADO", "PERFILADO", "CITA", "SEPARADO"]
            gap = 13
            w = (self.width - gap * 4) / 5
            for i, state in enumerate(states):
                x = i * (w + gap)
                fill = YELLOW if state in ("NUEVO", "SEPARADO") else PALE_BLUE
                self.box(c, x, 75, w, 36, state, "", fill)
                if i < 4:
                    self.arrow(c, x + w, 93, x + w + gap, 93)
            self.box(c, self.width*.25, 15, self.width*.2, 34, "NUTRICIÓN", "Pertenecer", WHITE, ORANGE)
            self.box(c, self.width*.55, 15, self.width*.2, 34, "DESCARTADO", "motivo auditable", WHITE, RED)
            self.arrow(c, self.width*.5, 75, self.width*.35, 49, "no listo")
            self.arrow(c, self.width*.5, 75, self.width*.65, 49, "no viable")


class NumberedDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title="VIVI · ViviendAI — Documentación técnica integral",
            author="Proyecto VIVI · ViviendAI",
            subject="Arquitectura, modelo de datos, agentes, scoring y auditoría",
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
        )
        self.addPageTemplates(
            PageTemplate(id="main", frames=[frame], onPage=self.header_footer)
        )

    def header_footer(self, canvas, doc):
        if doc.page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(YELLOW)
        canvas.setLineWidth(2)
        canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
        canvas.setFont(FONT_BOLD, 7.5)
        canvas.setFillColor(GRAPHITE)
        canvas.drawString(18 * mm, A4[1] - 9 * mm, "VIVI · ViviendAI")
        canvas.setFont(FONT, 7)
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Página {doc.page}")
        canvas.restoreState()


def card(title: str, value: str, detail: str, accent=BLUE):
    data = [
        [para(title, styles["VCardTitle"])],
        [para(value, styles["VMetric"])],
        [para(detail, styles["VSmall"])],
    ]
    t = Table(data, colWidths=[52 * mm], rowHeights=[9 * mm, 13 * mm, 14 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 1, accent),
                ("LINEABOVE", (0, 0), (-1, 0), 4, accent),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def markdown_table(lines: list[str], start: int) -> tuple[Table, int]:
    rows = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        if not all(re.fullmatch(r"[-: ]+", c or "-") for c in cells):
            rows.append([para(c, styles["VSmall"]) for c in cells])
        i += 1
    widths = [170 * mm / max(1, len(rows[0]))] * len(rows[0])
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (-1, -1), WHITE),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table, i


def audit_story() -> list:
    lines = AUDIT.read_text(encoding="utf-8").splitlines()
    story = []
    i = 1
    diagram_after = {
        "3. Inventario técnico": "architecture",
        "4. Flujo implementado": "sequence",
        "7. Auditoría de Make y Gemini": "make",
        "8. Persistencia y modelo de datos": "erd",
        "12. Hoja de ruta priorizada": "state",
    }
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            story.append(Spacer(1, 2))
            i += 1
            continue
        if line.startswith("# "):
            i += 1
            continue
        if line.startswith("## "):
            heading = line[3:]
            story.append(PageBreak())
            story.append(para(heading, styles["VH1"]))
            story.append(HRFlowable(width="100%", thickness=2, color=YELLOW, spaceAfter=8))
            if heading in diagram_after:
                height = 185 if diagram_after[heading] == "erd" else 150
                story.append(Diagram(diagram_after[heading], height=height))
                story.append(Spacer(1, 7))
            i += 1
            continue
        if line.startswith("### "):
            story.append(para(line[4:], styles["VH2"]))
            i += 1
            continue
        if line.startswith("|"):
            table, i = markdown_table(lines, i)
            story.append(table)
            story.append(Spacer(1, 7))
            continue
        if re.match(r"^[-*] ", line):
            story.append(para("• " + line[2:], styles["VBullet"]))
            i += 1
            continue
        if re.match(r"^\d+\. ", line):
            story.append(para(line, styles["VBullet"]))
            i += 1
            continue
        if line.startswith("**") and line.endswith("**"):
            story.append(para(line, styles["VH2"]))
            i += 1
            continue
        paragraph = line
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or nxt.startswith(("#", "|", "-", "*")) or re.match(r"^\d+\. ", nxt):
                break
            paragraph += " " + nxt
            i += 1
        story.append(para(paragraph, styles["VBody"]))
    return story


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    story = []

    story.append(Spacer(1, 13 * mm))
    if LOGO.exists():
        img = Image(str(LOGO), width=58 * mm, height=19 * mm, kind="proportional")
        logo_band = Table([[img]], colWidths=[170 * mm], rowHeights=[25 * mm])
        logo_band.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BLUE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(logo_band)
    story.append(Spacer(1, 14 * mm))
    story.append(para("VIVI · ViviendAI", styles["VTitle"]))
    story.append(
        para(
            "Documentación técnica integral, auditoría, arquitectura, modelo de datos, "
            "agentes de IA y hoja de ruta",
            styles["VSubTitle"],
        )
    )
    story.append(Spacer(1, 12 * mm))
    band = Table(
        [[para("PERFILAMIENTO INTELIGENTE DE LEADS DE VIVIENDA", styles["VCardTitle"])]],
        colWidths=[170 * mm],
        rowHeights=[14 * mm],
    )
    band.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), YELLOW),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(band)
    story.append(Spacer(1, 14 * mm))
    story.append(
        para(
            "<b>Versión auditada:</b> 26 de julio de 2026<br/>"
            "<b>Estado:</b> prototipo funcional con integraciones simuladas<br/>"
            "<b>Validación:</b> código, datos, SQLite, Make, Gemini, Telegram, "
            "NotebookLM y pruebas automatizadas",
            styles["VBody"],
        )
    )
    story.append(Spacer(1, 30 * mm))
    story.append(
        para(
            "Documento de ingeniería y producto. El score es una prioridad comercial "
            "explicable; no equivale a aprobación de crédito ni asignación de subsidio.",
            styles["VSmall"],
        )
    )

    story.append(PageBreak())
    story.append(para("Tablero ejecutivo de la auditoría", styles["VH1"]))
    story.append(HRFlowable(width="100%", thickness=2, color=YELLOW, spaceAfter=10))
    cards = [
        card("Pruebas automatizadas", "20/20", "Compilación y suite unitarias correctas", GREEN),
        card("Registros históricos", "4.142", "26 proyectos analizados", BLUE),
        card("Score explicable", "0–100", "Seis dimensiones determinísticas", YELLOW),
    ]
    story.append(Table([cards], colWidths=[56 * mm] * 3, hAlign="LEFT"))
    story.append(Spacer(1, 9 * mm))
    matrix = [
        [para("Capacidad", styles["VCardTitle"]), para("Estado", styles["VCardTitle"]), para("Lectura ejecutiva", styles["VCardTitle"])],
        [para("Captura y atribución", styles["VSmall"]), para("Implementada", styles["VSmall"]), para("Proyecto, campaña, anuncio y UTM", styles["VSmall"])],
        [para("Finanzas y scoring", styles["VSmall"]), para("Implementada", styles["VSmall"]), para("Reglas auditables; sin decisión crediticia", styles["VSmall"])],
        [para("Telegram + memoria", styles["VSmall"]), para("Parcial", styles["VSmall"]), para("Falta extracción estructurada y rescore", styles["VSmall"])],
        [para("CRM/HANA/Supabase", styles["VSmall"]), para("Simulado/objetivo", styles["VSmall"]), para("No existe conexión productiva", styles["VSmall"])],
        [para("Separación", styles["VSmall"]), para("Pendiente", styles["VSmall"]), para("Debe incorporarse a la demo", styles["VSmall"])],
    ]
    mt = Table(matrix, colWidths=[43 * mm, 32 * mm, 95 * mm], repeatRows=1)
    mt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(mt)
    story.append(Spacer(1, 8 * mm))
    story.append(para("Arquitectura lógica verificada", styles["VH2"]))
    story.append(Diagram("architecture", height=140))

    story.append(PageBreak())
    story.append(para("UML de componentes del backend", styles["VH1"]))
    story.append(HRFlowable(width="100%", thickness=2, color=YELLOW, spaceAfter=8))
    story.append(Diagram("uml", height=150))
    story.append(Spacer(1, 6))
    story.append(
        para(
            "La IA conversa y extrae señales; las reglas financieras y el score deben "
            "permanecer fuera del modelo generativo. Esta separación reduce alucinaciones "
            "y permite auditar cada punto.",
            styles["VBody"],
        )
    )

    story.extend(audit_story())

    doc = NumberedDocTemplate(str(OUTPUT))
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
