"""Reusable GUI building blocks: data table, generic form dialog, message helpers."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import messagebox, ttk

import customtkinter as ctk

from ..errors import AppError


def apply_table_style() -> None:
    """Style ttk.Treeview to match the current CustomTkinter appearance mode."""
    style = ttk.Style()
    style.theme_use("clam")
    dark = ctk.get_appearance_mode() == "Dark"
    background = "#2b2b2b" if dark else "#ffffff"
    foreground = "#dce4ee" if dark else "#1a1a1a"
    style.configure("Grade.Treeview", background=background, fieldbackground=background,
                    foreground=foreground, rowheight=28, borderwidth=0, font=("Helvetica", 11))
    style.configure("Grade.Treeview.Heading", background="#1f538d", foreground="white",
                    relief="flat", font=("Helvetica", 11, "bold"))
    style.map("Grade.Treeview", background=[("selected", "#3a7ebf")],
              foreground=[("selected", "white")])
    style.map("Grade.Treeview.Heading", background=[("active", "#144870")])


class DataTable(ctk.CTkFrame):
    """A scrollable table. Rows are (row_id, values) pairs."""

    def __init__(self, master, columns, height: int = 12, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(self, show="headings", style="Grade.Treeview",
                                 height=height, selectmode="browse")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.configure_columns(columns)

    def configure_columns(self, columns) -> None:
        """columns: list of (key, heading, width)."""
        self.tree.configure(columns=[c[0] for c in columns])
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w", stretch=True)

    def load(self, rows) -> None:
        self.tree.delete(*self.tree.get_children())
        for row_id, values in rows:
            self.tree.insert("", "end", iid=str(row_id), values=tuple(values))

    def selected_id(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def select(self, row_id) -> None:
        if row_id is not None and self.tree.exists(str(row_id)):
            self.tree.selection_set(str(row_id))
            self.tree.focus(str(row_id))

    def bind_select(self, callback) -> None:
        self.tree.bind("<<TreeviewSelect>>", lambda _event: callback())


@dataclass
class Field:
    name: str
    label: str
    kind: str = "entry"          # "entry" | "password" | "option"
    options: list = field(default_factory=list)
    default: str = ""


class FormDialog(ctk.CTkToplevel):
    """Generic modal form. on_submit(values: dict) may raise AppError to keep the form open."""

    def __init__(self, master, title: str, fields: list[Field], on_submit, submit_text: str = "Save"):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self._on_submit = on_submit
        self._widgets: dict[str, ctk.CTkBaseClass] = {}

        self.geometry(f"420x{110 + 62 * len(fields)}")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(18, 8))

        for index, spec in enumerate(fields, start=1):
            holder = ctk.CTkFrame(self, fg_color="transparent")
            holder.grid(row=index, column=0, sticky="ew", padx=24, pady=3)
            holder.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(holder, text=spec.label, anchor="w").grid(row=0, column=0, sticky="w")
            if spec.kind == "option":
                values = spec.options or ["-"]
                widget = ctk.CTkOptionMenu(holder, values=values, dynamic_resizing=False)
                widget.set(spec.default if spec.default in values else values[0])
            else:
                widget = ctk.CTkEntry(holder, show="*" if spec.kind == "password" else "")
                if spec.default:
                    widget.insert(0, spec.default)
            widget.grid(row=1, column=0, sticky="ew")
            self._widgets[spec.name] = widget

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=len(fields) + 1, column=0, sticky="e", padx=24, pady=(12, 16))
        ctk.CTkButton(buttons, text="Cancel", width=90, fg_color="gray40", hover_color="gray30",
                      command=self.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text=submit_text, width=110, command=self._submit).pack(side="left")

        self.bind("<Return>", lambda _event: self._submit())
        self.bind("<Escape>", lambda _event: self.destroy())
        first = next(iter(self._widgets.values()), None)
        self.after(200, lambda: self._activate(first))

    def _activate(self, first) -> None:
        try:
            self.grab_set()
            self.focus_force()
            if isinstance(first, ctk.CTkEntry):
                first.focus()
        except tk.TclError:
            pass

    def _submit(self) -> None:
        values = {name: widget.get().strip() for name, widget in self._widgets.items()}
        try:
            self._on_submit(values)
        except AppError as exc:
            messagebox.showerror("Please check your input", str(exc), parent=self)
            return
        self.destroy()


def confirm(parent, message: str, title: str = "Please confirm") -> bool:
    return messagebox.askyesno(title, message, parent=parent)


def info(parent, message: str, title: str = "Information") -> None:
    messagebox.showinfo(title, message, parent=parent)
