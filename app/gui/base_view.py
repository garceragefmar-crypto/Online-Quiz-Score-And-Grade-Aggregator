"""Abstract base class shared by every screen shown in the content area."""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from ..context import AppContext
from ..errors import AppError
from ..models import User


class BaseView(ctk.CTkFrame):
    TITLE = ""

    def __init__(self, master, ctx: AppContext, user: User):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.user = user
        self.grid_columnconfigure(0, weight=1)
        self._title = ctk.CTkLabel(self, text=self.TITLE,
                                   font=ctk.CTkFont(size=24, weight="bold"))
        self._title.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))

    def refresh(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def guard(self, func, *args, **kwargs) -> bool:
        """Run func; on an expected error show a message box and return False."""
        try:
            func(*args, **kwargs)
            return True
        except AppError as exc:
            messagebox.showerror("Cannot complete action", str(exc), parent=self)
            return False
