"""Entry point:  python main.py"""
from app.context import AppContext
from app.gui.app_window import App


def main() -> None:
    ctx = AppContext()
    app = App(ctx)
    try:
        app.mainloop()
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
