"""Grade Analytics Dashboard: metric cards, charts and top performers."""
import customtkinter as ctk

from ..models import fmt_num
from .base_view import BaseView
from .charts import BarChart
from .widgets import DataTable


class DashboardView(BaseView):
    TITLE = "Grade Analytics Dashboard"

    def __init__(self, master, ctx, user):
        super().__init__(master, ctx, user)
        self._staff = user.role != "student"
        self.grid_rowconfigure(2, weight=3)
        self.grid_rowconfigure(3, weight=2)

        self._cards = ctk.CTkFrame(self, fg_color="transparent")
        self._cards.grid(row=1, column=0, sticky="ew", padx=20)

        charts = ctk.CTkFrame(self, fg_color="transparent")
        charts.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        charts.grid_columnconfigure((0, 1), weight=1, uniform="charts")
        charts.grid_rowconfigure(0, weight=1)
        self._average_chart = BarChart(charts, "Average score per module (%)", max_value=100)
        self._average_chart.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._distribution_chart = BarChart(charts, "Score distribution (number of quizzes)")
        self._distribution_chart.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self._top = None
        if self._staff:
            holder = ctk.CTkFrame(self, fg_color="transparent")
            holder.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 16))
            holder.grid_columnconfigure(0, weight=1)
            holder.grid_rowconfigure(1, weight=1)
            ctk.CTkLabel(holder, text="Top performers (cumulative)",
                         font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w",
                                                                        pady=(0, 4))
            self._top = DataTable(holder, [("rank", "#", 50), ("name", "Student", 260),
                                           ("no", "Student No", 140), ("score", "Score", 140),
                                           ("pct", "Cumulative %", 130), ("remark", "Standing", 130)],
                                  height=5)
            self._top.grid(row=1, column=0, sticky="nsew")

    def refresh(self) -> None:
        analytics = self.ctx.analytics
        for child in self._cards.winfo_children():
            child.destroy()
        cards = analytics.dashboard_cards(self.user)
        for index, (label, value) in enumerate(cards):
            self._cards.grid_columnconfigure(index, weight=1, uniform="cards")
            card = ctk.CTkFrame(self._cards, corner_radius=10)
            card.grid(row=0, column=index, sticky="ew", padx=4, pady=4)
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=24, weight="bold")).pack(
                padx=12, pady=(12, 0))
            ctk.CTkLabel(card, text=label, text_color=("gray40", "gray70")).pack(pady=(0, 12))

        self._average_chart.set_data(*analytics.module_averages(self.user))
        self._distribution_chart.set_data(*analytics.score_distribution(self.user))

        if self._top is not None:
            rows = [(s.ref_id, (rank, s.label, s.detail,
                                f"{fmt_num(s.total)} / {fmt_num(s.maximum)}",
                                f"{s.percentage:.2f}%", s.remark))
                    for rank, s in enumerate(analytics.top_students(self.user), 1)]
            self._top.load(rows)
