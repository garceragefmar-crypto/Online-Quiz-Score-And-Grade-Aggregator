"""Student management (full CRUD for admins, read-only roster for instructors)."""
import customtkinter as ctk

from ..models import Perm
from .base_view import BaseView
from .widgets import DataTable, Field, FormDialog, confirm, info


class StudentsView(BaseView):
    TITLE = "Students"

    def __init__(self, master, ctx, user):
        super().__init__(master, ctx, user)
        self.grid_rowconfigure(2, weight=1)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=20)
        self._search = ctk.CTkEntry(bar, width=300,
                                    placeholder_text="Search name, student no or course")
        self._search.pack(side="left")
        self._search.bind("<KeyRelease>", lambda _e: self.refresh())

        if user.can(Perm.MANAGE_STUDENTS):
            ctk.CTkButton(bar, text="Delete", width=90, fg_color="#c0392b", hover_color="#992d22",
                          command=self._delete).pack(side="right", padx=(6, 0))
            ctk.CTkButton(bar, text="Edit", width=90, command=self._edit).pack(side="right", padx=6)
            ctk.CTkButton(bar, text="Add student", width=120, command=self._add).pack(side="right")

        self._table = DataTable(self, [("no", "Student No", 110), ("last", "Last name", 160),
                                       ("first", "First name", 160), ("email", "Email", 240),
                                       ("course", "Course", 100), ("pct", "Cumulative %", 110)])
        self._table.grid(row=2, column=0, sticky="nsew", padx=20, pady=12)

    def refresh(self) -> None:
        selected = self._table.selected_id()
        students = self.ctx.students.list_students(self.user, self._search.get())
        rows = []
        for s in students:
            overall = self.ctx.aggregator.overall(s.id, self.user)
            pct = f"{overall.percentage:.1f}%" if overall.maximum else "-"
            rows.append((s.id, (s.student_no, s.last_name, s.first_name, s.email, s.course, pct)))
        self._table.load(rows)
        self._table.select(selected)

    def _fields(self, s=None):
        return [Field("student_no", "Student number", default=s.student_no if s else ""),
                Field("first_name", "First name", default=s.first_name if s else ""),
                Field("last_name", "Last name", default=s.last_name if s else ""),
                Field("email", "Email (optional)", default=s.email if s else ""),
                Field("course", "Course (optional)", default=s.course if s else "")]

    def _add(self) -> None:
        def submit(values):
            self.ctx.students.add_student(self.user, **values)
            self.refresh()
        FormDialog(self, "Add student", self._fields(), submit)

    def _edit(self) -> None:
        student_id = self._table.selected_id()
        if student_id is None:
            info(self, "Select a student first.")
            return
        student = self.ctx.students.get(student_id)

        def submit(values):
            self.ctx.students.update_student(self.user, student_id, **values)
            self.refresh()
        FormDialog(self, "Edit student", self._fields(student), submit)

    def _delete(self) -> None:
        student_id = self._table.selected_id()
        if student_id is None:
            info(self, "Select a student first.")
            return
        if confirm(self, "Delete this student, their scores and their login account?"):
            self.guard(self.ctx.students.delete_student, self.user, student_id)
            self.refresh()
