# Online Course Quiz Score and Cumulative Grade Aggregator

Python OOP desktop app (CustomTkinter + SQLite) with role-based access control (Admin, Instructor, Student),
SQL `SUM()` grade aggregation, an analytics dashboard, and CSV / PDF export.

## Run it in VS Code

1. Unzip the folder and open it: **File > Open Folder...**
2. Open a terminal (**Terminal > New Terminal**) and create a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate       # macOS / Linux
   pip install -r requirements.txt
   ```
3. Press **Ctrl+Shift+P > Python: Select Interpreter** and pick the `.venv` one.
4. Run `python main.py` (or open `main.py` and press the Run button).

The database file `data/grades.db` is created on first launch and filled with sample data.
Delete that file any time to reset to the sample data.

Linux only: if you get `No module named tkinter`, run `sudo apt install python3-tk`.

## Demo accounts

| Role       | Username     | Password      |
|------------|--------------|---------------|
| Admin      | admin        | admin123      |
| Instructor | prof.reyes   | instructor123 |
| Instructor | prof.santos  | instructor123 |
| Student    | student1     | student123    |

Remove the demo hint from `app/gui/login_view.py` and change these passwords before real use.

## What each role can do

| Feature                          | Admin | Instructor            | Student     |
|----------------------------------|:-----:|-----------------------|-------------|
| Dashboard                        | all   | own modules           | own results |
| Students (CRUD)                  | yes   | view only             | -           |
| Modules (CRUD)                   | yes   | -                     | -           |
| Quizzes/assessments (CRUD)       | yes   | own modules           | -           |
| Record / edit / delete scores    | yes   | own modules           | -           |
| Reports + CSV/PDF export         | all   | own modules           | own transcript |
| User accounts                    | yes   | -                     | -           |

Permissions are enforced in the service layer (`app/services.py`), not just by hiding buttons.

## Project layout

```
main.py                  entry point
app/
  database.py            DatabaseConnection + schema (students, modules, assessments, student_scores, users)
  models.py              User (abstract) -> AdminUser / InstructorUser / StudentUser, Student, CourseModule,
                         Assessment, AssessmentScore (validated/encapsulated), Standing
  auth.py                AuthManager (hashed passwords, lockout, account management)
  services.py            StudentManager, ModuleManager, ScoreTracker, GradeAggregator (SQL SUM), AnalyticsEngine
  reports.py             ReportGenerator, Exporter (abstract) -> CSVExporter / PDFExporter
  validators.py, security.py, errors.py, seed.py, context.py
  gui/                   app_window, login_view, dashboard_view, students_view, modules_view,
                         scores_view, reports_view, users_view, charts (ChartGenerator), widgets
tests/test_backend.py    unit tests:  python -m unittest discover -s tests -v
```

## Mapping to the proposal

| Proposal module            | Classes / files                                             |
|----------------------------|-------------------------------------------------------------|
| Login / Authentication     | `User`, `AuthManager`, `DatabaseConnection`, `login_view`   |
| Grade Analytics Dashboard  | `DashboardView`, `AnalyticsEngine`, `BarChart`              |
| Student & Module Management| `Student`, `CourseModule`, `StudentManager`, `ModuleManager`|
| Quiz Score Entry & Aggregation | `AssessmentScore`, `GradeAggregator`, `ScoreTracker`    |
| Reports & Data Export      | `ReportGenerator`, `PDFExporter`, `CSVExporter`             |

OOP principles: encapsulation (`AssessmentScore.score` setter, private user fields), inheritance (user roles),
polymorphism (`permissions` / `views` per role, `Exporter.export`), abstraction (`User`, `Exporter` ABCs).

## Grading rules

Cumulative % = `SUM(scores) / SUM(max scores)` over the quizzes a student has taken.
Remarks: >= 90 Excellent, >= 85 Very Good, >= 80 Good, >= 75 Passed, otherwise Failed.
Change `PASSING_PERCENT` and `grade_remark()` in `app/models.py` to match your school's scale.

## Switching to MySQL (optional)

All SQL lives in `database.py`, `auth.py`, `services.py`. Swap `sqlite3` for `mysql-connector-python`, change `?`
placeholders to `%s`, adjust the schema (`AUTO_INCREMENT`) and replace `ON CONFLICT ... DO UPDATE` in
`ScoreTracker.record_score` with `ON DUPLICATE KEY UPDATE`.
