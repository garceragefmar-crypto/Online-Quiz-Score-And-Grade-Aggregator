"""Business logic: student/module management, score tracking and SQL SUM() aggregation."""
from __future__ import annotations

from datetime import date

from .database import DatabaseConnection
from .errors import NotFoundError, PermissionDenied, ValidationError
from .models import (Assessment, AssessmentScore, CourseModule, PASSING_PERCENT, Perm,
                     Standing, Student, User, fmt_num)
from . import validators as v

SCORE_JOINS = """
FROM student_scores ss
JOIN assessments a ON a.id = ss.assessment_id
JOIN modules m     ON m.id = a.module_id
JOIN students s    ON s.id = ss.student_id
"""


def score_scope(actor: User) -> tuple[list[str], list]:
    """WHERE-clauses that limit score queries to what the actor may see."""
    if actor.role == "student":
        return ["ss.student_id = ?"], [actor.student_id]
    if actor.role == "instructor":
        return ["m.instructor_id = ?"], [actor.id]
    return [], []


def _where(actor: User | None, clauses=(), params=()) -> tuple[str, list]:
    scope_clauses, scope_params = score_scope(actor) if actor else ([], [])
    all_clauses = list(scope_clauses) + list(clauses)
    all_params = list(scope_params) + list(params)
    return (" WHERE " + " AND ".join(all_clauses) if all_clauses else ""), all_params


def ensure_module_access(db: DatabaseConnection, actor: User, module_id: int) -> None:
    if actor.role == "admin":
        return
    if actor.role == "instructor":
        if db.query_one("SELECT 1 FROM modules WHERE id = ? AND instructor_id = ?",
                        (module_id, actor.id)):
            return
    raise PermissionDenied("You do not have access to that module.")


# ------------------------------------------------------------------ students
class StudentManager:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def list_students(self, actor: User, search: str = "") -> list[Student]:
        actor.require(Perm.VIEW_ALL)
        sql, params = "SELECT * FROM students", []
        term = search.strip()
        if term:
            sql += (" WHERE student_no LIKE ? OR first_name LIKE ? OR last_name LIKE ?"
                    " OR course LIKE ?")
            params = [f"%{term}%"] * 4
        sql += " ORDER BY last_name, first_name"
        return [Student.from_row(r) for r in self._db.query(sql, params)]

    def get(self, student_id: int) -> Student:
        row = self._db.query_one("SELECT * FROM students WHERE id = ?", (student_id,))
        if row is None:
            raise NotFoundError("Student not found.")
        return Student.from_row(row)

    @staticmethod
    def _clean(student_no, first_name, last_name, email, course):
        return (v.require_text(student_no, "Student number", 30),
                v.require_text(first_name, "First name", 60),
                v.require_text(last_name, "Last name", 60),
                v.validate_email(email),
                v.optional_text(course, "Course", 80))

    def add_student(self, actor: User, student_no, first_name, last_name, email="", course="") -> int:
        actor.require(Perm.MANAGE_STUDENTS)
        data = self._clean(student_no, first_name, last_name, email, course)
        return self._db.execute(
            "INSERT INTO students (student_no, first_name, last_name, email, course) "
            "VALUES (?, ?, ?, ?, ?)", data)

    def update_student(self, actor: User, student_id: int, student_no, first_name, last_name,
                       email="", course="") -> None:
        actor.require(Perm.MANAGE_STUDENTS)
        data = self._clean(student_no, first_name, last_name, email, course)
        self._db.execute(
            "UPDATE students SET student_no=?, first_name=?, last_name=?, email=?, course=? "
            "WHERE id=?", data + (student_id,))

    def delete_student(self, actor: User, student_id: int) -> None:
        actor.require(Perm.MANAGE_STUDENTS)
        self._db.execute("DELETE FROM students WHERE id = ?", (student_id,))


# ------------------------------------------------------------------- modules
class ModuleManager:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def list_modules(self, actor: User) -> list[CourseModule]:
        sql = ("SELECT m.id, m.code, m.title, m.instructor_id, u.full_name AS instructor_name, "
               "(SELECT COUNT(*) FROM assessments x WHERE x.module_id = m.id) AS assessment_count "
               "FROM modules m LEFT JOIN users u ON u.id = m.instructor_id")
        params: list = []
        if actor.role == "instructor":
            sql += " WHERE m.instructor_id = ?"
            params.append(actor.id)
        elif actor.role == "student":
            sql += (" WHERE m.id IN (SELECT a.module_id FROM student_scores ss "
                    "JOIN assessments a ON a.id = ss.assessment_id WHERE ss.student_id = ?)")
            params.append(actor.student_id)
        sql += " ORDER BY m.code"
        return [CourseModule.from_row(r) for r in self._db.query(sql, params)]

    def add_module(self, actor: User, code, title, instructor_id=None) -> int:
        actor.require(Perm.MANAGE_MODULES)
        return self._db.execute(
            "INSERT INTO modules (code, title, instructor_id) VALUES (?, ?, ?)",
            (v.require_text(code, "Module code", 20).upper(),
             v.require_text(title, "Module title", 100), instructor_id))

    def update_module(self, actor: User, module_id: int, code, title, instructor_id=None) -> None:
        actor.require(Perm.MANAGE_MODULES)
        self._db.execute(
            "UPDATE modules SET code = ?, title = ?, instructor_id = ? WHERE id = ?",
            (v.require_text(code, "Module code", 20).upper(),
             v.require_text(title, "Module title", 100), instructor_id, module_id))

    def delete_module(self, actor: User, module_id: int) -> None:
        actor.require(Perm.MANAGE_MODULES)
        self._db.execute("DELETE FROM modules WHERE id = ?", (module_id,))

    # -- assessments (quizzes) belong to a module
    def list_assessments(self, actor: User, module_id: int) -> list[Assessment]:
        ensure_module_access(self._db, actor, module_id)
        rows = self._db.query("SELECT * FROM assessments WHERE module_id = ? ORDER BY id",
                              (module_id,))
        return [Assessment.from_row(r) for r in rows]

    def add_assessment(self, actor: User, module_id: int, title, max_score) -> int:
        actor.require(Perm.MANAGE_ASSESSMENTS)
        ensure_module_access(self._db, actor, module_id)
        maximum = v.parse_number(max_score, "Maximum score")
        if maximum <= 0:
            raise ValidationError("Maximum score must be greater than zero.")
        return self._db.execute(
            "INSERT INTO assessments (module_id, title, max_score) VALUES (?, ?, ?)",
            (module_id, v.require_text(title, "Quiz title", 100), maximum))

    def _module_of_assessment(self, assessment_id: int) -> int:
        row = self._db.query_one("SELECT module_id FROM assessments WHERE id = ?", (assessment_id,))
        if row is None:
            raise NotFoundError("Quiz not found.")
        return row["module_id"]

    def update_assessment(self, actor: User, assessment_id: int, title, max_score) -> None:
        actor.require(Perm.MANAGE_ASSESSMENTS)
        ensure_module_access(self._db, actor, self._module_of_assessment(assessment_id))
        maximum = v.parse_number(max_score, "Maximum score")
        if maximum <= 0:
            raise ValidationError("Maximum score must be greater than zero.")
        highest = self._db.query_one(
            "SELECT MAX(score) AS top FROM student_scores WHERE assessment_id = ?",
            (assessment_id,))["top"]
        if highest is not None and highest > maximum:
            raise ValidationError(
                f"A student already scored {fmt_num(highest)}; the maximum cannot be lower.")
        self._db.execute("UPDATE assessments SET title = ?, max_score = ? WHERE id = ?",
                         (v.require_text(title, "Quiz title", 100), maximum, assessment_id))

    def delete_assessment(self, actor: User, assessment_id: int) -> None:
        actor.require(Perm.MANAGE_ASSESSMENTS)
        ensure_module_access(self._db, actor, self._module_of_assessment(assessment_id))
        self._db.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))


# -------------------------------------------------------------------- scores
class ScoreTracker:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def list_scores(self, actor: User, module_id: int | None = None,
                    student_id: int | None = None) -> list[AssessmentScore]:
        clauses, params = [], []
        if module_id:
            clauses.append("m.id = ?")
            params.append(module_id)
        if student_id and actor.role != "student":
            clauses.append("ss.student_id = ?")
            params.append(student_id)
        where, params = _where(actor, clauses, params)
        sql = ("SELECT ss.id, ss.student_id, ss.assessment_id, ss.score, ss.date_recorded, "
               "a.max_score, a.title AS assessment_title, m.code AS module_code, "
               "s.last_name || ', ' || s.first_name AS student_name "
               f"{SCORE_JOINS}{where} "
               "ORDER BY m.code, s.last_name, s.first_name, a.id")
        return [AssessmentScore.from_row(r) for r in self._db.query(sql, params)]

    def record_score(self, actor: User, student_id: int, assessment_id: int, score) -> None:
        """Insert or update (upsert) a score. Validated against the quiz's maximum."""
        actor.require(Perm.RECORD_SCORES)
        assessment = self._db.query_one(
            "SELECT id, module_id, max_score FROM assessments WHERE id = ?", (assessment_id,))
        if assessment is None:
            raise NotFoundError("Quiz not found.")
        ensure_module_access(self._db, actor, assessment["module_id"])
        if self._db.query_one("SELECT 1 FROM students WHERE id = ?", (student_id,)) is None:
            raise NotFoundError("Student not found.")
        value = v.parse_number(score, "Score")
        record = AssessmentScore(None, student_id, assessment_id, value, assessment["max_score"])
        self._db.execute(
            "INSERT INTO student_scores (student_id, assessment_id, score, date_recorded) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(student_id, assessment_id) DO UPDATE SET "
            "score = excluded.score, date_recorded = excluded.date_recorded",
            (student_id, assessment_id, record.score, date.today().isoformat()))

    def delete_score(self, actor: User, score_id: int) -> None:
        actor.require(Perm.RECORD_SCORES)
        row = self._db.query_one(
            "SELECT a.module_id FROM student_scores ss "
            "JOIN assessments a ON a.id = ss.assessment_id WHERE ss.id = ?", (score_id,))
        if row is None:
            raise NotFoundError("Score not found.")
        ensure_module_access(self._db, actor, row["module_id"])
        self._db.execute("DELETE FROM student_scores WHERE id = ?", (score_id,))


# ---------------------------------------------------------------- aggregation
class GradeAggregator:
    """Uses SQL SUM() to tally scores and maximums, then derives percentages."""

    def __init__(self, db: DatabaseConnection):
        self._db = db

    @staticmethod
    def _standing(row) -> Standing:
        return Standing(row["ref_id"], row["label"], row["detail"],
                        row["total"] or 0.0, row["maximum"] or 0.0, row["items"] or 0)

    def module_standings(self, student_id: int, actor: User | None = None) -> list[Standing]:
        """Per-module totals for one student."""
        where, params = _where(actor, ["ss.student_id = ?"], [student_id])
        sql = ("SELECT m.id AS ref_id, m.code AS label, m.title AS detail, "
               "SUM(ss.score) AS total, SUM(a.max_score) AS maximum, COUNT(ss.id) AS items "
               f"{SCORE_JOINS}{where} GROUP BY m.id ORDER BY m.code")
        return [self._standing(r) for r in self._db.query(sql, params)]

    def overall(self, student_id: int, actor: User | None = None) -> Standing:
        """Cumulative total across all modules for one student."""
        where, params = _where(actor, ["ss.student_id = ?"], [student_id])
        sql = ("SELECT NULL AS ref_id, 'Cumulative' AS label, '' AS detail, "
               "SUM(ss.score) AS total, SUM(a.max_score) AS maximum, COUNT(ss.id) AS items "
               f"{SCORE_JOINS}{where}")
        return self._standing(self._db.query_one(sql, params))

    def class_standings(self, module_id: int, actor: User | None = None) -> list[Standing]:
        """Every student's total for one module, best first."""
        where, params = _where(actor, ["m.id = ?"], [module_id])
        sql = ("SELECT s.id AS ref_id, s.last_name || ', ' || s.first_name AS label, "
               "s.student_no AS detail, SUM(ss.score) AS total, SUM(a.max_score) AS maximum, "
               f"COUNT(ss.id) AS items {SCORE_JOINS}{where} GROUP BY s.id "
               "ORDER BY SUM(ss.score) * 1.0 / SUM(a.max_score) DESC, s.last_name")
        return [self._standing(r) for r in self._db.query(sql, params)]

    def student_standings(self, actor: User | None = None) -> list[Standing]:
        """Cumulative total for every student inside the actor's scope, best first."""
        where, params = _where(actor)
        sql = ("SELECT s.id AS ref_id, s.last_name || ', ' || s.first_name AS label, "
               "s.student_no AS detail, SUM(ss.score) AS total, SUM(a.max_score) AS maximum, "
               f"COUNT(ss.id) AS items {SCORE_JOINS}{where} GROUP BY s.id "
               "ORDER BY SUM(ss.score) * 1.0 / SUM(a.max_score) DESC, s.last_name")
        return [self._standing(r) for r in self._db.query(sql, params)]


# ------------------------------------------------------------------ analytics
class AnalyticsEngine:
    BUCKETS = [("<60", 0, 60), ("60-69", 60, 70), ("70-79", 70, 80),
               ("80-89", 80, 90), ("90-100", 90, 101)]

    def __init__(self, db: DatabaseConnection, aggregator: GradeAggregator):
        self._db = db
        self._agg = aggregator

    def dashboard_cards(self, actor: User) -> list[tuple[str, str]]:
        where, params = _where(actor)
        row = self._db.query_one(
            "SELECT COUNT(ss.id) AS n, SUM(ss.score) AS total, SUM(a.max_score) AS maximum, "
            "COUNT(DISTINCT m.id) AS modules, COUNT(DISTINCT ss.student_id) AS students "
            f"{SCORE_JOINS}{where}", params)
        total, maximum = row["total"] or 0.0, row["maximum"] or 0.0
        pct = total / maximum * 100 if maximum else 0.0

        if actor.role == "student":
            standing = Standing(None, "", "", total, maximum, row["n"])
            return [("Modules taken", str(row["modules"])),
                    ("Quizzes taken", str(row["n"])),
                    ("Cumulative", f"{pct:.1f}%"),
                    ("Standing", standing.remark)]

        if actor.role == "instructor":
            modules = self._db.query_one(
                "SELECT COUNT(*) AS n FROM modules WHERE instructor_id = ?", (actor.id,))["n"]
            quizzes = self._db.query_one(
                "SELECT COUNT(*) AS n FROM assessments a JOIN modules m ON m.id = a.module_id "
                "WHERE m.instructor_id = ?", (actor.id,))["n"]
            students = row["students"]
        else:
            modules = self._db.query_one("SELECT COUNT(*) AS n FROM modules")["n"]
            quizzes = self._db.query_one("SELECT COUNT(*) AS n FROM assessments")["n"]
            students = self._db.query_one("SELECT COUNT(*) AS n FROM students")["n"]

        standings = self._agg.student_standings(actor)
        passed = sum(1 for s in standings if s.percentage >= PASSING_PERCENT)
        pass_rate = passed / len(standings) * 100 if standings else 0.0
        return [("Students", str(students)), ("Modules", str(modules)), ("Quizzes", str(quizzes)),
                ("Scores recorded", str(row["n"])), ("Average", f"{pct:.1f}%"),
                ("Pass rate", f"{pass_rate:.0f}%")]

    def module_averages(self, actor: User) -> tuple[list[str], list[float]]:
        where, params = _where(actor)
        rows = self._db.query(
            "SELECT m.code AS code, SUM(ss.score) * 100.0 / SUM(a.max_score) AS pct "
            f"{SCORE_JOINS}{where} GROUP BY m.id ORDER BY m.code", params)
        return [r["code"] for r in rows], [round(r["pct"], 1) for r in rows]

    def score_distribution(self, actor: User) -> tuple[list[str], list[int]]:
        where, params = _where(actor)
        rows = self._db.query(
            f"SELECT ss.score AS score, a.max_score AS maximum {SCORE_JOINS}{where}", params)
        counts = [0] * len(self.BUCKETS)
        for r in rows:
            pct = r["score"] / r["maximum"] * 100
            for i, (_, low, high) in enumerate(self.BUCKETS):
                if low <= pct < high:
                    counts[i] += 1
                    break
        return [b[0] for b in self.BUCKETS], counts

    def top_students(self, actor: User, limit: int = 5) -> list[Standing]:
        return self._agg.student_standings(actor)[:limit]
