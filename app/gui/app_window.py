"""Main window: login screen, role-aware sidebar and view switching."""
import customtkinter as ctk

from ..context import AppContext
from .dashboard_view import DashboardView
from .login_view import LoginView
from .modules_view import ModulesView
from .reports_view import ReportsView
from .scores_view import ScoresView
from .students_view import StudentsView
from .users_view import UsersView
from .widgets import apply_table_style

VIEW_CLASSES = {
    "dashboard": DashboardView,
    "students": StudentsView,
    "modules": ModulesView,
    "scores": ScoresView,
    "reports": ReportsView,
    "users": UsersView,
}


class App(ctk.CTk):
    def __init__(self, ctx: AppContext):
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.title("Online Course Quiz Score and Cumulative Grade Aggregator")
        self.geometry("1240x760")
        self.minsize(1050, 640)
        apply_table_style()

        self.ctx = ctx
        self.user = None
        self._screen = None
        self._view = None
        self._active_key = None
        self._nav = {}
        self._content = None
        self._mode = "System"
        self.show_login()

    # -- screens
    def _clear_screen(self) -> None:
        if self._screen is not None:
            self._screen.destroy()
        self._screen = self._view = self._content = None
        self._nav = {}

    def show_login(self) -> None:
        self._clear_screen()
        self.user = None
        self._screen = LoginView(self, self.ctx.auth, self._on_login)
        self._screen.pack(fill="both", expand=True)

    def _on_login(self, user) -> None:
        self.user = user
        self._build_main()

    def _build_main(self) -> None:
        self._clear_screen()
        screen = ctk.CTkFrame(self, fg_color="transparent")
        screen.pack(fill="both", expand=True)
        screen.grid_columnconfigure(1, weight=1)
        screen.grid_rowconfigure(0, weight=1)
        self._screen = screen

        sidebar = ctk.CTkFrame(screen, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.pack_propagate(False)
        ctk.CTkLabel(sidebar, text="Grade Aggregator",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(padx=16, pady=(20, 2), anchor="w")
        ctk.CTkLabel(sidebar, text=f"{self.user.full_name}\n({self.user.role})",
                     justify="left", text_color=("gray35", "gray70")).pack(padx=16, pady=(0, 18),
                                                                          anchor="w")
        for key, label in self.user.views:
            button = ctk.CTkButton(
                sidebar, text=label, anchor="w", height=38, fg_color="transparent",
                text_color=("gray10", "gray90"), hover_color=("gray75", "gray30"),
                command=lambda k=key: self.open_view(k))
            button.pack(fill="x", padx=12, pady=3)
            self._nav[key] = button

        ctk.CTkButton(sidebar, text="Log out", fg_color="gray40", hover_color="gray30",
                      command=self.show_login).pack(side="bottom", fill="x", padx=12, pady=(6, 16))
        theme = ctk.CTkOptionMenu(sidebar, values=["System", "Light", "Dark"],
                                  command=self._change_appearance)
        theme.set(self._mode)
        theme.pack(side="bottom", fill="x", padx=12, pady=6)
        ctk.CTkLabel(sidebar, text="Appearance", text_color=("gray35", "gray70")).pack(
            side="bottom", anchor="w", padx=16)

        self._content = ctk.CTkFrame(screen, fg_color="transparent")
        self._content.grid(row=0, column=1, sticky="nsew")
        self.open_view(self.user.views[0][0])

    def open_view(self, key: str) -> None:
        if self._view is not None:
            self._view.destroy()
        self._active_key = key
        self._view = VIEW_CLASSES[key](self._content, self.ctx, self.user)
        self._view.pack(fill="both", expand=True)
        self._view.refresh()
        for nav_key, button in self._nav.items():
            button.configure(fg_color=("gray75", "gray28") if nav_key == key else "transparent")

    def _change_appearance(self, mode: str) -> None:
        self._mode = mode
        ctk.set_appearance_mode(mode)
        apply_table_style()
        if self._active_key:
            self.open_view(self._active_key)
