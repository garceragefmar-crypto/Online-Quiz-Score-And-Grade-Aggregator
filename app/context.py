"""Builds every service once and shares them with the GUI (simple dependency container)."""
from __future__ import annotations

from .auth import AuthManager
from .database import DB_PATH, DatabaseConnection
from .reports import ReportGenerator
from .seed import seed_if_empty
from .services import (AnalyticsEngine, GradeAggregator, ModuleManager, ScoreTracker,
                       StudentManager)


class AppContext:
    def __init__(self, db_path=DB_PATH, seed: bool = True):
        self.db = DatabaseConnection(db_path)
        if seed:
            seed_if_empty(self.db)
        self.auth = AuthManager(self.db)
        self.students = StudentManager(self.db)
        self.modules = ModuleManager(self.db)
        self.scores = ScoreTracker(self.db)
        self.aggregator = GradeAggregator(self.db)
        self.analytics = AnalyticsEngine(self.db, self.aggregator)
        self.reports = ReportGenerator(self.db, self.students, self.modules, self.aggregator)

    def close(self) -> None:
        self.db.close()
