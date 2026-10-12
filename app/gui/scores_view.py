"""Quiz score entry (staff) and score viewing with SQL SUM() cumulative totals."""
import customtkinter as ctk

from ..models import Perm, fmt_num
from .base_view import BaseView
from .widgets import DataTable, Field, FormDialog, confirm, info

ALL_MODULES = "All modules"
ALL_STUDENTS = "All students"


class ScoresView(BaseView):
    TITLE = "Quiz Scores"

    def __init__(self, master, ctx, user):
        super().__init__(master, ctx, user)
        self._staff = user.can(Perm.RECORD_SCORES)
        if not self._staff:
            self._title.configure(text="My Quiz Scores")
        self.grid_rowconfigure(2, weight=1)
        self._module_ids: dict[str, int | None] = {}
        self._student_ids: dict[str, int | None] = {}
        self._rows = {}

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=20)
        ctk.CTkLabel(bar, text="Module:").pack(side="left", padx=(0, 6))
        self._module_menu = ctk.CTkOptionMenu(bar, values=["-"], width=230,
                                              command=lambda _v: self._load_scores())
        self._module_menu.pack(side="left")
        self._student_menu = None
        if self._staff:
            ctk.CTkLabel(bar, text="Student:").pack(side="left", padx=(16, 6))
            self._student_menu = ctk.CTkOptionMenu(bar, values=[ALL_STUDENTS], width=230,
                                                   command=lambda _v: self._load_scores())
            self._student_menu.pack(side="left")
            ctk.CTkButton(bar, text="Delete", width=80, fg_color="#c0392b", hover_color="#992d22",
                          command=self._delete).pack(side="right", padx=(6, 0))
            ctk.CTkButton(bar, text="Edit selected", width=110,
                          command=lambda: self._dialog(edit=True)).pack(side="right", padx=6)
            ctk.CTkButton(bar, text="Record score", width=110,
                          command=lambda: self._dialog(edit=False)).pack(side="right")

        self._table = DataTable(self, [("module", "Module", 80), ("student", "Student", 200),
                                       ("quiz", "Quiz", 140), ("score", "Score", 80),
                                       ("max", "Maximum", 80), ("pct", "Percent", 80),
                                       ("date", "Recorded", 100)])
        self._table.grid(row=2, column=0, sticky="nsew", padx=20, pady=12)
        self._summary = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=15, weight="bold"),
                                     anchor="w")
        self._summary.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 16))

    # -- data loading
    def refresh(self) -> None:
        modules = self.ctx.modules.list_modules(self.user)
        self._module_ids = {} if self._staff else {ALL_MODULES: None}
        self._module_ids.update({f"{m.code} - {m.title}": m.id for m in modules})
        self._set_menu(self._module_menu, list(self._module_ids) or ["(no modules)"])
        if self._student_menu is not None:
            students = self.ctx.students.list_students(self.user)
            self._student_ids = {ALL_STUDENTS: None}
            self._student_ids.update({f"{s.full_name} ({s.student_no})": s.id for s in students})
            self._set_menu(self._student_menu, list(self._student_ids))
        self._load_scores()

    @staticmethod
    def _set_menu(menu, values) -> None:
        current = menu.get()
        menu.configure(values=values)
        menu.set(current if current in values else values[0])

    def _load_scores(self) -> None:
        module_id = self._module_ids.get(self._module_menu.get())
        student_id = self._student_ids.get(self._student_menu.get()) if self._student_menu else None
        scores = self.ctx.scores.list_scores(self.user, module_id, student_id)
        self._rows = {s.id: s for s in scores}
        self._table.load([(s.id, (s.module_code, s.student_name, s.assessment_title,
                                  fmt_num(s.score), fmt_num(s.max_score), f"{s.percentage:.1f}%",
                                  s.recorded_on)) for s in scores])
        self._update_summary(module_id, student_id)

    def _update_summary(self, module_id, student_id) -> None:
        agg = self.ctx.aggregator
        target = self.user.student_id if not self._staff else student_id
        if target is not None:
            if module_id:
                standing = next((s for s in agg.module_standings(target, self.user)
                                 if s.ref_id == module_id), None)
            else:
                standing = agg.overall(target, self.user)
            if standing is None or not standing.maximum:
                self._summary.configure(text="No scores recorded yet.")
                return
            self._summary.configure(
                text=f"Cumulative: {fmt_num(standing.total)} / {fmt_num(standing.maximum)}"
                     f"  =  {standing.percentage:.2f}%   ({standing.remark})")
        elif module_id:
            standings = agg.class_standings(module_id, self.user)
            average = sum(s.percentage for s in standings) / len(standings) if standings else 0
            self._summary.configure(
                text=f"Class average: {average:.2f}% across {len(standings)} student(s)")
        else:
            self._summary.configure(text="")

    # -- record / edit / delete
    def _dialog(self, edit: bool) -> None:
        module_id = self._module_ids.get(self._module_menu.get())
        if module_id is None:
            info(self, "Create or select a module first.")
            return
        existing = None
        if edit:
            score_id = self._table.selected_id()
            if score_id is None:
                info(self, "Select a score row to edit, or use 'Record score'.")
                return
            existing = self._rows[score_id]
        quizzes = self.ctx.modules.list_assessments(self.user, module_id)
        students = self.ctx.students.list_students(self.user)
        if not quizzes or not students:
            info(self, "This module needs at least one quiz, and there must be students.")
            return
        quiz_ids = {f"{q.title} (max {fmt_num(q.max_score)})": q.id for q in quizzes}
        student_ids = {f"{s.full_name} ({s.student_no})": s.id for s in students}

        def label_for(mapping, wanted):
            return next((k for k, v in mapping.items() if v == wanted), "")

        def submit(values):
            self.ctx.scores.record_score(self.user, student_ids[values["student"]],
                                         quiz_ids[values["quiz"]], values["score"])
            self._load_scores()

        current_student = self._student_ids.get(self._student_menu.get()) if self._student_menu else None
        FormDialog(self, "Edit score" if edit else "Record quiz score", [
            Field("student", "Student", "option", list(student_ids),
                  label_for(student_ids, existing.student_id if existing else current_student)),
            Field("quiz", "Quiz", "option", list(quiz_ids),
                  label_for(quiz_ids, existing.assessment_id) if existing else ""),
            Field("score", "Score", default=fmt_num(existing.score) if existing else ""),
        ], submit)

    def _delete(self) -> None:
        score_id = self._table.selected_id()
        if score_id is None:
            info(self, "Select a score row first.")
            return
        if confirm(self, "Delete this recorded score?"):
            self.guard(self.ctx.scores.delete_score, self.user, score_id)
            self._load_scores()
