"""Sample data so the app is usable on first launch."""
import random

from .database import DatabaseConnection
from .security import hash_password


def seed_if_empty(db: DatabaseConnection) -> None:
    if db.query_one("SELECT 1 FROM users LIMIT 1"):
        return

    def add_user(username, full_name, role, password, student_id=None):
        salt, digest = hash_password(password)
        return db.execute(
            "INSERT INTO users (username, full_name, role, salt, password_hash, student_id) "
            "VALUES (?, ?, ?, ?, ?, ?)", (username, full_name, role, salt, digest, student_id))

    add_user("admin", "System Administrator", "admin", "admin123")
    reyes = add_user("prof.reyes", "Prof. Maria Reyes", "instructor", "instructor123")
    santos = add_user("prof.santos", "Prof. Juan Santos", "instructor", "instructor123")

    people = [("2024-0001", "Ana", "Garcia"), ("2024-0002", "Miguel", "Cruz"),
              ("2024-0003", "Sofia", "Lopez"), ("2024-0004", "Daniel", "Mendoza"),
              ("2024-0005", "Bianca", "Ramos"), ("2024-0006", "Carlo", "Villanueva"),
              ("2024-0007", "Isabel", "Torres"), ("2024-0008", "Rafael", "Bautista")]
    student_ids = [
        db.execute("INSERT INTO students (student_no, first_name, last_name, email, course) "
                   "VALUES (?, ?, ?, ?, ?)",
                   (no, first, last, f"{first.lower()}.{last.lower()}@example.edu", "BSIT"))
        for no, first, last in people]
    add_user("student1", "Ana Garcia", "student", "student123", student_ids[0])

    modules = [("IT101", "Introduction to Programming", reyes),
               ("IT102", "Database Systems", reyes),
               ("IT103", "Web Development", santos)]
    quizzes = [("Quiz 1", 20), ("Quiz 2", 25), ("Quiz 3", 30), ("Quiz 4", 25)]
    rng = random.Random(2024)
    for code, title, instructor in modules:
        module_id = db.execute(
            "INSERT INTO modules (code, title, instructor_id) VALUES (?, ?, ?)",
            (code, title, instructor))
        for quiz_title, maximum in quizzes:
            assessment_id = db.execute(
                "INSERT INTO assessments (module_id, title, max_score) VALUES (?, ?, ?)",
                (module_id, quiz_title, maximum))
            for student_id in student_ids:
                if rng.random() < 0.08:
                    continue  # a few missing scores make the data realistic
                score = round(maximum * rng.uniform(0.55, 1.0), 1)
                db.execute("INSERT INTO student_scores (student_id, assessment_id, score) "
                           "VALUES (?, ?, ?)", (student_id, assessment_id, score))
