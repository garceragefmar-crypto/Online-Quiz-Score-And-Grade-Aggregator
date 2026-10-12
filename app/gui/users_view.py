"""User account administration (admin only)."""
import customtkinter as ctk

from ..models import ROLE_CLASSES
from .base_view import BaseView
from .widgets import DataTable, Field, FormDialog, confirm, info

NO_STUDENT = "(none)"


class UsersView(BaseView):
    TITLE = "User Accounts"

    def __init__(self, master, ctx, user):
        super().__init__(master, ctx, user)
        self.grid_rowconfigure(2, weight=1)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="e", padx=20)
        ctk.CTkButton(bar, text="Add user", width=100, command=self._add).pack(side="left", padx=3)
        ctk.CTkButton(bar, text="Reset password", width=130,
                      command=self._reset).pack(side="left", padx=3)
        ctk.CTkButton(bar, text="Delete", width=90, fg_color="#c0392b", hover_color="#992d22",
                      command=self._delete).pack(side="left", padx=3)
        self._table = DataTable(self, [("username", "Username", 160), ("name", "Full name", 240),
                                       ("role", "Role", 110), ("student", "Linked student no", 150)])
        self._table.grid(row=2, column=0, sticky="nsew", padx=20, pady=12)

    def refresh(self) -> None:
        users = self.ctx.auth.list_users(self.user)
        self._table.load([(u["id"], (u["username"], u["full_name"], u["role"],
                                     u["student_no"] or "-")) for u in users])

    def _add(self) -> None:
        students = self.ctx.students.list_students(self.user)
        student_ids = {f"{s.full_name} ({s.student_no})": s.id for s in students}

        def submit(values):
            self.ctx.auth.create_user(self.user, values["username"], values["full_name"],
                                      values["role"], values["password"],
                                      student_ids.get(values["student"]))
            self.refresh()
        FormDialog(self, "Add user", [
            Field("username", "Username"),
            Field("full_name", "Full name"),
            Field("role", "Role", "option", list(ROLE_CLASSES), "instructor"),
            Field("password", "Password (min 6 characters)", "password"),
            Field("student", "Linked student (student role only)", "option",
                  [NO_STUDENT] + list(student_ids)),
        ], submit)

    def _reset(self) -> None:
        user_id = self._table.selected_id()
        if user_id is None:
            info(self, "Select a user first.")
            return

        def submit(values):
            self.ctx.auth.reset_password(self.user, user_id, values["password"])
        FormDialog(self, "Reset password", [Field("password", "New password", "password")], submit)

    def _delete(self) -> None:
        user_id = self._table.selected_id()
        if user_id is None:
            info(self, "Select a user first.")
            return
        if confirm(self, "Delete this account?"):
            self.guard(self.ctx.auth.delete_user, self.user, user_id)
            self.refresh()
