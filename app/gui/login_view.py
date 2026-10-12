"""Login screen."""
import customtkinter as ctk

from ..auth import AuthManager
from ..errors import AuthenticationError


class LoginView(ctk.CTkFrame):
    def __init__(self, master, auth: AuthManager, on_success):
        super().__init__(master)
        self._auth = auth
        self._on_success = on_success

        card = ctk.CTkFrame(self, corner_radius=14)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text="Quiz Score & Grade Aggregator",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(padx=48, pady=(36, 4))
        ctk.CTkLabel(card, text="Sign in to continue", text_color="gray").pack(pady=(0, 20))

        self._username = ctk.CTkEntry(card, placeholder_text="Username", width=280, height=38)
        self._username.pack(pady=6)
        self._password = ctk.CTkEntry(card, placeholder_text="Password", show="*",
                                      width=280, height=38)
        self._password.pack(pady=6)
        self._error = ctk.CTkLabel(card, text="", text_color="#e5484d", wraplength=280)
        self._error.pack(pady=(4, 0))
        ctk.CTkButton(card, text="Sign in", width=280, height=40, command=self._login).pack(pady=14)
        
                     

        self._username.bind("<Return>", lambda _e: self._password.focus())
        self._password.bind("<Return>", lambda _e: self._login())
        self.after(200, self._username.focus)

    def _login(self) -> None:
        try:
            user = self._auth.login(self._username.get(), self._password.get())
        except AuthenticationError as exc:
            self._error.configure(text=str(exc))
            self._password.delete(0, "end")
            return
        self._on_success(user)
