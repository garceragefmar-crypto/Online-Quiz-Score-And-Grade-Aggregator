"""Course modules (admin) and their quizzes/assessments (admin + owning instructor)."""
import customtkinter as ctk

from ..models import Perm, fmt_num
from .base_view import BaseView
from .widgets import DataTable, Field, FormDialog, confirm, info

NONE_LABEL = "(unassigned)"


class ModulesView(BaseView):
    TITLE = "Modules & Quizzes"

    def __init__(self, master, ctx, user):
        super().__init__(master, ctx, user)
        self.grid_rowconfigure(1, weight=1)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))
        body.grid_columnconfigure((0, 1), weight=1, uniform="panels")
        body.grid_rowconfigure(0, weight=1)

        left, left_bar = self._panel(body, 0, "Modules")
        self._modules = DataTable(left, [("code", "Code", 80), ("title", "Title", 200),
                                         ("instructor", "Instructor", 140), ("quizzes", "Quizzes", 60)])
        self._modules.grid(row=2, column=0, sticky="nsew")
        self._modules.bind_select(self._load_assessments)
        if user.can(Perm.MANAGE_MODULES):
            self._button(left_bar, "Add", self._add_module)
            self._button(left_bar, "Edit", self._edit_module)
            self._button(left_bar, "Delete", self._delete_module, danger=True)

        right, right_bar = self._panel(body, 1, "Quizzes in selected module")
        self._assessments = DataTable(right, [("title", "Quiz", 240), ("max", "Maximum score", 120)])
        self._assessments.grid(row=2, column=0, sticky="nsew")
        if user.can(Perm.MANAGE_ASSESSMENTS):
            self._button(right_bar, "Add quiz", self._add_assessment)
            self._button(right_bar, "Edit", self._edit_assessment)
            self._button(right_bar, "Delete", self._delete_assessment, danger=True)

        self._instructors = []
        self._modules_by_id = {}

    # -- layout helpers
    def _panel(self, parent, column, heading):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(panel, text=heading, font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w")
        bar = ctk.CTkFrame(panel, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="e", pady=6)
        return panel, bar

    @staticmethod
    def _button(bar, text, command, danger=False):
        kwargs = {"fg_color": "#c0392b", "hover_color": "#992d22"} if danger else {}
        ctk.CTkButton(bar, text=text, width=80, command=command, **kwargs).pack(side="left", padx=3)

    # -- data
    def refresh(self) -> None:
        selected = self._modules.selected_id()
        modules = self.ctx.modules.list_modules(self.user)
        self._modules_by_id = {m.id: m for m in modules}
        self._modules.load([(m.id, (m.code, m.title, m.instructor_name or "-", m.assessment_count))
                            for m in modules])
        self._modules.select(selected)
        if self.user.can(Perm.MANAGE_USERS):
            self._instructors = self.ctx.auth.list_users(self.user, "instructor")
        self._load_assessments()

    def _load_assessments(self) -> None:
        module_id = self._modules.selected_id()
        if module_id is None:
            self._assessments.load([])
            return
        selected = self._assessments.selected_id()
        items = self.ctx.modules.list_assessments(self.user, module_id)
        self._assessments.load([(a.id, (a.title, fmt_num(a.max_score))) for a in items])
        self._assessments.select(selected)

    # -- module CRUD
    def _module_fields(self, module=None):
        labels = [NONE_LABEL] + [f"{u['full_name']} ({u['username']})" for u in self._instructors]
        default = NONE_LABEL
        if module and module.instructor_id:
            for u in self._instructors:
                if u["id"] == module.instructor_id:
                    default = f"{u['full_name']} ({u['username']})"
        return [Field("code", "Module code", default=module.code if module else ""),
                Field("title", "Module title", default=module.title if module else ""),
                Field("instructor", "Instructor", "option", labels, default)]

    def _instructor_id(self, label):
        for u in self._instructors:
            if f"{u['full_name']} ({u['username']})" == label:
                return u["id"]
        return None

    def _add_module(self) -> None:
        def submit(values):
            self.ctx.modules.add_module(self.user, values["code"], values["title"],
                                        self._instructor_id(values["instructor"]))
            self.refresh()
        FormDialog(self, "Add module", self._module_fields(), submit)

    def _edit_module(self) -> None:
        module_id = self._modules.selected_id()
        if module_id is None:
            info(self, "Select a module first.")
            return

        def submit(values):
            self.ctx.modules.update_module(self.user, module_id, values["code"], values["title"],
                                           self._instructor_id(values["instructor"]))
            self.refresh()
        FormDialog(self, "Edit module", self._module_fields(self._modules_by_id[module_id]), submit)

    def _delete_module(self) -> None:
        module_id = self._modules.selected_id()
        if module_id is None:
            info(self, "Select a module first.")
            return
        if confirm(self, "Delete this module with all its quizzes and recorded scores?"):
            self.guard(self.ctx.modules.delete_module, self.user, module_id)
            self.refresh()

    # -- assessment CRUD
    def _add_assessment(self) -> None:
        module_id = self._modules.selected_id()
        if module_id is None:
            info(self, "Select a module first.")
            return

        def submit(values):
            self.ctx.modules.add_assessment(self.user, module_id, values["title"], values["max"])
            self.refresh()
        FormDialog(self, "Add quiz", [Field("title", "Quiz title"),
                                      Field("max", "Maximum score")], submit)

    def _edit_assessment(self) -> None:
        module_id, assessment_id = self._modules.selected_id(), self._assessments.selected_id()
        if module_id is None or assessment_id is None:
            info(self, "Select a quiz first.")
            return
        current = next(a for a in self.ctx.modules.list_assessments(self.user, module_id)
                       if a.id == assessment_id)

        def submit(values):
            self.ctx.modules.update_assessment(self.user, assessment_id, values["title"],
                                               values["max"])
            self.refresh()
        FormDialog(self, "Edit quiz", [Field("title", "Quiz title", default=current.title),
                                       Field("max", "Maximum score",
                                             default=fmt_num(current.max_score))], submit)

    def _delete_assessment(self) -> None:
        assessment_id = self._assessments.selected_id()
        if assessment_id is None:
            info(self, "Select a quiz first.")
            return
        if confirm(self, "Delete this quiz and all scores recorded for it?"):
            self.guard(self.ctx.modules.delete_assessment, self.user, assessment_id)
            self.refresh()
