"""Report generation and export (CSV / PDF)."""
from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from xml.sax.saxutils import escape

from .database import DatabaseConnection
from .errors import AppError, PermissionDenied, ValidationError
from .models import Perm, User, fmt_num
from .services import GradeAggregator, ModuleManager, StudentManager, ensure_module_access

KIND_TRANSCRIPT = "Student transcript"
KIND_MODULE = "Module report"
KIND_SUMMARY = "Class summary"


@dataclass
class ReportData:
    title: str
    subtitle: str
    headers: list[str]
    rows: list[tuple]
    summary: list[str] = field(default_factory=list)
    suggested_name: str = "report"


class ReportGenerator:
    def __init__(self, db: DatabaseConnection, students: StudentManager,
                 modules: ModuleManager, aggregator: GradeAggregator):
        self._db = db
        self._students = students
        self._modules = modules
        self._agg = aggregator

    def build(self, actor: User, kind: str, target_id: int | None = None) -> ReportData:
        actor.require(Perm.EXPORT)
        if kind == KIND_TRANSCRIPT:
            student_id = actor.student_id if actor.role == "student" else target_id
            return self._transcript(actor, student_id)
        if actor.role == "student":
            raise PermissionDenied("Students can only view their own transcript.")
        if kind == KIND_MODULE:
            return self._module_report(actor, target_id)
        if kind == KIND_SUMMARY:
            return self._summary(actor)
        raise ValidationError("Unknown report type.")

    def _transcript(self, actor: User, student_id: int | None) -> ReportData:
        if not student_id:
            raise ValidationError("Choose a student.")
        student = self._students.get(student_id)
        standings = self._agg.module_standings(student_id, actor)
        overall = self._agg.overall(student_id, actor)
        rows = [(s.label, s.detail, s.items, fmt_num(s.total), fmt_num(s.maximum),
                 f"{s.percentage:.2f}%", s.remark) for s in standings]
        summary = [f"Cumulative score: {fmt_num(overall.total)} / {fmt_num(overall.maximum)}",
                   f"Cumulative percentage: {overall.percentage:.2f}%",
                   f"Standing: {overall.remark}"]
        return ReportData(
            "Student Transcript",
            f"{student.full_name}  |  {student.student_no}  |  {student.course}".strip(" |"),
            ["Module", "Title", "Quizzes", "Total", "Maximum", "Percent", "Standing"],
            rows, summary, f"transcript_{student.student_no}")

    def _module_report(self, actor: User, module_id: int | None) -> ReportData:
        if not module_id:
            raise ValidationError("Choose a module.")
        ensure_module_access(self._db, actor, module_id)
        module = next((m for m in self._modules.list_modules(actor) if m.id == module_id), None)
        if module is None:
            raise ValidationError("Module not found.")
        standings = self._agg.class_standings(module_id, actor)
        rows = [(i, s.detail, s.label, s.items, fmt_num(s.total), fmt_num(s.maximum),
                 f"{s.percentage:.2f}%", s.remark) for i, s in enumerate(standings, 1)]
        average = sum(s.percentage for s in standings) / len(standings) if standings else 0.0
        return ReportData(
            f"Module Report: {module.code}", module.title,
            ["Rank", "Student No", "Student", "Quizzes", "Total", "Maximum", "Percent", "Standing"],
            rows, [f"Students with scores: {len(standings)}", f"Class average: {average:.2f}%"],
            f"module_{module.code}")

    def _summary(self, actor: User) -> ReportData:
        standings = self._agg.student_standings(actor)
        rows = [(i, s.detail, s.label, s.items, fmt_num(s.total), fmt_num(s.maximum),
                 f"{s.percentage:.2f}%", s.remark) for i, s in enumerate(standings, 1)]
        average = sum(s.percentage for s in standings) / len(standings) if standings else 0.0
        return ReportData(
            "Cumulative Grade Summary", "All students, all modules",
            ["Rank", "Student No", "Student", "Quizzes", "Total", "Maximum", "Percent", "Standing"],
            rows, [f"Students: {len(standings)}", f"Average cumulative: {average:.2f}%"],
            "class_summary")


class Exporter(ABC):
    """Abstract exporter; subclasses decide the output format."""
    extension = ""
    label = ""

    @abstractmethod
    def export(self, report: ReportData, path: str) -> None: ...


class CSVExporter(Exporter):
    extension = ".csv"
    label = "CSV spreadsheet"

    def export(self, report: ReportData, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow([report.title])
            writer.writerow([report.subtitle])
            writer.writerow([])
            writer.writerow(report.headers)
            writer.writerows(report.rows)
            writer.writerow([])
            for line in report.summary:
                writer.writerow([line])


class PDFExporter(Exporter):
    extension = ".pdf"
    label = "PDF document"

    def export(self, report: ReportData, path: str) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            raise AppError("PDF export needs the 'reportlab' package.\n"
                           "Install it with:  pip install reportlab") from None

        page = landscape(A4) if len(report.headers) > 6 else A4
        doc = SimpleDocTemplate(str(path), pagesize=page, leftMargin=36, rightMargin=36,
                                topMargin=36, bottomMargin=36, title=report.title)
        styles = getSampleStyleSheet()
        cell = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=9, leading=11)

        data = [list(report.headers)]
        data += [[Paragraph(escape(str(value)), cell) for value in row] for row in report.rows]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f538d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0b0b0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4fa")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        story = [Paragraph(escape(report.title), styles["Title"]),
                 Paragraph(escape(report.subtitle), styles["Normal"]), Spacer(1, 14), table,
                 Spacer(1, 14)]
        story += [Paragraph(escape(line), styles["Normal"]) for line in report.summary]
        story += [Spacer(1, 18), Paragraph(
            f"Generated {datetime.now():%Y-%m-%d %H:%M}", styles["Italic"])]
        doc.build(story)
