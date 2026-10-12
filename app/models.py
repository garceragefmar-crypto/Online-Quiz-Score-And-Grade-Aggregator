"""Domain model: user roles (inheritance/polymorphism) and grade entities (encapsulation)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .errors import PermissionDenied, ValidationError

PASSING_PERCENT = 75.0


def fmt_num(value: float) -> str:
    """85.0 -> '85', 85.5 -> '85.5'."""
    return f"{value:g}"


def grade_remark(percentage: float) -> str:
    if percentage >= 90:
        return "Excellent"
    if percentage >= 85:
        return "Very Good"
    if percentage >= 80:
        return "Good"
    if percentage >= PASSING_PERCENT:
        return "Passed"
    return "Failed"


class Perm:
    """Permission names used for Role-Based Access Control."""
    MANAGE_USERS = "manage_users"
    MANAGE_STUDENTS = "manage_students"
    MANAGE_MODULES = "manage_modules"
    MANAGE_ASSESSMENTS = "manage_assessments"
    RECORD_SCORES = "record_scores"
    VIEW_ALL = "view_all_scores"
    EXPORT = "export_reports"


# ---------------------------------------------------------------- users (RBAC)
class User(ABC):
    """Abstract signed-in user. Subclasses define what their role may do."""

    ROLE = "base"

    def __init__(self, user_id: int, username: str, full_name: str, student_id: int | None = None):
        self._id = user_id
        self._username = username
        self._full_name = full_name
        self._student_id = student_id

    @property
    def id(self) -> int:
        return self._id

    @property
    def username(self) -> str:
        return self._username

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def student_id(self) -> int | None:
        return self._student_id

    @property
    def role(self) -> str:
        return self.ROLE

    @property
    @abstractmethod
    def permissions(self) -> frozenset:
        """Set of Perm.* values this role holds."""

    @property
    @abstractmethod
    def views(self) -> list[tuple[str, str]]:
        """(view_key, sidebar label) pairs shown to this role."""

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise PermissionDenied("Your role is not allowed to perform this action.")

    @staticmethod
    def from_row(row) -> "User":
        cls = ROLE_CLASSES.get(row["role"])
        if cls is None:
            raise ValueError(f"Unknown role: {row['role']}")
        return cls(row["id"], row["username"], row["full_name"], row["student_id"])


class AdminUser(User):
    ROLE = "admin"

    @property
    def permissions(self) -> frozenset:
        return frozenset({
            Perm.MANAGE_USERS, Perm.MANAGE_STUDENTS, Perm.MANAGE_MODULES,
            Perm.MANAGE_ASSESSMENTS, Perm.RECORD_SCORES, Perm.VIEW_ALL, Perm.EXPORT,
        })

    @property
    def views(self):
        return [("dashboard", "Dashboard"), ("students", "Students"), ("modules", "Modules"),
                ("scores", "Quiz Scores"), ("reports", "Reports"), ("users", "Users")]


class InstructorUser(User):
    ROLE = "instructor"

    @property
    def permissions(self) -> frozenset:
        return frozenset({Perm.MANAGE_ASSESSMENTS, Perm.RECORD_SCORES, Perm.VIEW_ALL, Perm.EXPORT})

    @property
    def views(self):
        return [("dashboard", "Dashboard"), ("students", "Students"), ("modules", "My Modules"),
                ("scores", "Quiz Scores"), ("reports", "Reports")]


class StudentUser(User):
    ROLE = "student"

    @property
    def permissions(self) -> frozenset:
        return frozenset({Perm.EXPORT})

    @property
    def views(self):
        return [("dashboard", "My Dashboard"), ("scores", "My Scores"), ("reports", "My Transcript")]


ROLE_CLASSES = {cls.ROLE: cls for cls in (AdminUser, InstructorUser, StudentUser)}


# ---------------------------------------------------------------- grade entities
@dataclass
class Student:
    id: int
    student_no: str
    first_name: str
    last_name: str
    email: str = ""
    course: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.last_name}, {self.first_name}"

    @classmethod
    def from_row(cls, row) -> "Student":
        return cls(row["id"], row["student_no"], row["first_name"], row["last_name"],
                   row["email"] or "", row["course"] or "")


@dataclass
class CourseModule:
    id: int
    code: str
    title: str
    instructor_id: int | None = None
    instructor_name: str = ""
    assessment_count: int = 0

    @classmethod
    def from_row(cls, row) -> "CourseModule":
        return cls(row["id"], row["code"], row["title"], row["instructor_id"],
                   row["instructor_name"] or "", row["assessment_count"])


@dataclass
class Assessment:
    id: int
    module_id: int
    title: str
    max_score: float

    @classmethod
    def from_row(cls, row) -> "Assessment":
        return cls(row["id"], row["module_id"], row["title"], row["max_score"])


class AssessmentScore:
    """One student's score on one quiz. The score is encapsulated and always validated."""

    def __init__(self, score_id, student_id, assessment_id, score, max_score,
                 recorded_on="", student_name="", assessment_title="", module_code=""):
        self.id = score_id
        self.student_id = student_id
        self.assessment_id = assessment_id
        self._max_score = float(max_score)
        self._score = 0.0
        self.score = score  # goes through the validating setter
        self.recorded_on = recorded_on
        self.student_name = student_name
        self.assessment_title = assessment_title
        self.module_code = module_code

    @property
    def max_score(self) -> float:
        return self._max_score

    @property
    def score(self) -> float:
        return self._score

    @score.setter
    def score(self, value) -> None:
        number = float(value)
        if not 0 <= number <= self._max_score:
            raise ValidationError(f"Score must be between 0 and {fmt_num(self._max_score)}.")
        self._score = number

    @property
    def percentage(self) -> float:
        return self._score / self._max_score * 100 if self._max_score else 0.0

    @classmethod
    def from_row(cls, row) -> "AssessmentScore":
        return cls(row["id"], row["student_id"], row["assessment_id"], row["score"],
                   row["max_score"], row["date_recorded"], row["student_name"],
                   row["assessment_title"], row["module_code"])


@dataclass
class Standing:
    """Aggregated result (SUM of scores vs SUM of maximums) for one subject."""
    ref_id: int | None
    label: str
    detail: str
    total: float
    maximum: float
    items: int

    @property
    def percentage(self) -> float:
        return self.total / self.maximum * 100 if self.maximum else 0.0

    @property
    def remark(self) -> str:
        return grade_remark(self.percentage) if self.maximum else "No scores"
