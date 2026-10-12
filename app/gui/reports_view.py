"""Report preview with CSV and PDF export."""
from tkinter import filedialog

import customtkinter as ctk

from ..errors import AppError
from ..reports import (CSVExporter, KIND_MODULE, KIND_SUMMARY, KIND_TRANSCRIPT, PDFExporter)
from .base_view import BaseView
from .widgets import DataTable, info


class ReportsView(BaseView):
    TITLE = "Reports & Export"

    def __init__(self, master, ctx, user):
        super().__init__(master, ctx, user)
        self._staff = user.role != "student"
        self._report = None
        self._targets: dict[str, int | None] = {}
        self._student_ids: dict[str, int] = {}
        self._module_ids: dict[str, int] = {}
        self.grid_rowconfigure(3, weight=1)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=20)
        kinds = [KIND_TRANSCRIPT, KIND_MODULE, KIND_SUMMARY] if self._staff else [KIND_TRANSCRIPT]
        ctk.CTkLabel(bar, text="Report:").pack(side="left", padx=(0, 6))
        self._kind_menu = ctk.CTkOptionMenu(bar, values=kinds, width=170, command=self._on_kind)
        self._kind_menu.pack(side="left")
        ctk.CTkLabel(bar, text="For:").pack(side="left", padx=(16, 6))
        self._target_menu = ctk.CTkOptionMenu(bar, values=["-"], width=260,
                                              command=lambda _v: self._preview())
        self._target_menu.pack(side="left")
        ctk.CTkButton(bar, text="Export PDF", width=110,
                      command=lambda: self._export(PDFExporter())).pack(side="right")
        ctk.CTkButton(bar, text="Export CSV", width=110,
                      command=lambda: self._export(CSVExporter())).pack(side="right", padx=6)

        self._heading = ctk.CTkLabel(self, text="", anchor="w", justify="left",
                                     font=ctk.CTkFont(size=14, weight="bold"))
        self._heading.grid(row=2, column=0, sticky="ew", padx=22, pady=(12, 4))
        self._table = DataTable(self, [("c0", "", 100)])
        self._table.grid(row=3, column=0, sticky="nsew", padx=20)
        self._footer = ctk.CTkLabel(self, text="", anchor="w", justify="left")
        self._footer.grid(row=4, column=0, sticky="ew", padx=22, pady=(8, 16))

    def refresh(self) -> None:
        if self._staff:
            self._student_ids = {f"{s.full_name} ({s.student_no})": s.id
                                 for s in self.ctx.students.list_students(self.user)}
            self._module_ids = {f"{m.code} - {m.title}": m.id
                                for m in self.ctx.modules.list_modules(self.user)}
        self._on_kind(self._kind_menu.get())

    def _on_kind(self, kind: str) -> None:
        if not self._staff:
            self._targets = {"My transcript": self.user.student_id}
        elif kind == KIND_TRANSCRIPT:
            self._targets = dict(self._student_ids)
        elif kind == KIND_MODULE:
            self._targets = dict(self._module_ids)
        else:
            self._targets = {"All students": None}
        labels = list(self._targets) or ["(nothing available)"]
        self._target_menu.configure(values=labels)
        self._target_menu.set(labels[0])
        self._preview()

    def _preview(self) -> None:
        kind = self._kind_menu.get()
        target = self._targets.get(self._target_menu.get())
        try:
            self._report = self.ctx.reports.build(self.user, kind, target)
        except AppError as exc:
            self._report = None
            self._table.load([])
            self._heading.configure(text=str(exc))
            self._footer.configure(text="")
            return
        report = self._report
        self._heading.configure(text=f"{report.title}\n{report.subtitle}")
        self._table.configure_columns([(f"c{i}", h, 90 if len(h) < 8 else 130)
                                       for i, h in enumerate(report.headers)])
        self._table.load([(i, row) for i, row in enumerate(report.rows)])
        self._footer.configure(text="\n".join(report.summary))

    def _export(self, exporter) -> None:
        if self._report is None:
            info(self, "Nothing to export yet. Choose a report first.")
            return
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=exporter.extension,
            initialfile=f"{self._report.suggested_name}{exporter.extension}",
            filetypes=[(exporter.label, f"*{exporter.extension}")])
        if not path:
            return
        if self.guard(exporter.export, self._report, path):
            info(self, f"Saved:\n{path}", "Export complete")
