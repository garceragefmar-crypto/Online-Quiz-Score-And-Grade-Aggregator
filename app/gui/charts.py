"""ChartGenerator: a lightweight bar chart drawn on a tkinter Canvas (no extra libraries)."""
from __future__ import annotations

import math
import tkinter as tk

import customtkinter as ctk

BAR_COLOR = "#3a7ebf"


class BarChart(ctk.CTkFrame):
    def __init__(self, master, title: str, max_value: float | None = None, **kwargs):
        super().__init__(master, **kwargs)
        self._max_value = max_value
        self._labels: list[str] = []
        self._values: list[float] = []
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=14, pady=(10, 0))
        self._canvas = tk.Canvas(self, highlightthickness=0, height=200)
        self._canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self._canvas.bind("<Configure>", lambda _event: self._draw())

    def set_data(self, labels: list[str], values: list[float]) -> None:
        self._labels, self._values = list(labels), list(values)
        self._draw()

    @staticmethod
    def _fmt(value: float) -> str:
        return f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"

    def _draw(self) -> None:
        canvas = self._canvas
        canvas.delete("all")
        dark = ctk.get_appearance_mode() == "Dark"
        background, text, grid = ("#2b2b2b", "#dce4ee", "#444444") if dark else \
                                 ("#ebebeb", "#1a1a1a", "#c8c8c8")
        canvas.configure(bg=background)
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 60 or height < 60:
            return
        if not self._values:
            canvas.create_text(width / 2, height / 2, text="No data yet", fill=text)
            return

        left, right, top, bottom = 44, 14, 24, 30
        plot_w, plot_h = width - left - right, height - top - bottom
        top_value = self._max_value or max(4, math.ceil(max(self._values) / 4) * 4)

        for step in range(5):
            fraction = step / 4
            y = top + plot_h * (1 - fraction)
            canvas.create_line(left, y, width - right, y, fill=grid)
            canvas.create_text(left - 6, y, text=self._fmt(top_value * fraction), anchor="e",
                               fill=text, font=("Helvetica", 8))

        slot = plot_w / len(self._values)
        bar_width = min(slot * 0.6, 64)
        baseline = top + plot_h
        for index, (label, value) in enumerate(zip(self._labels, self._values)):
            x0 = left + index * slot + (slot - bar_width) / 2
            x1 = x0 + bar_width
            y0 = baseline - plot_h * min(value / top_value, 1.0)
            canvas.create_rectangle(x0, y0, x1, baseline, fill=BAR_COLOR, outline="")
            centre = (x0 + x1) / 2
            canvas.create_text(centre, y0 - 8, text=self._fmt(value), fill=text, font=("Helvetica", 9))
            short = label if len(label) <= 12 else label[:11] + "..."
            canvas.create_text(centre, baseline + 14, text=short, fill=text, font=("Helvetica", 9))
