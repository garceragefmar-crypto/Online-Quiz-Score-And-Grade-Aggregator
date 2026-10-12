"""Backend unit tests (no GUI needed). Run:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.context import AppContext
from app.errors import AuthenticationError, PermissionDenied, ValidationError
from app.models import AssessmentScore
from app.reports import CSVExporter, KIND_MODULE, KIND_SUMMARY, KIND_TRANSCRIPT, PDFExporter


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.ctx = AppContext(":memory:", seed=False)
        db = self.ctx.db
        from app.security import hash_password
        def user(name, role, sid=None):
            salt, h = hash_password("secret1")
            return db.execute("INSERT INTO users (username, full_name, role, salt, password_hash, "
                              "student_id) VALUES (?,?,?,?,?,?)", (name, name.title(), role, salt, h, sid))
        user("admin", "admin")
        self.prof_id = user("prof", "instructor")
        self.other_id = user("other", "instructor")
        self.admin = self.ctx.auth.login("admin", "secret1")
        self.prof = self.ctx.auth.login("prof", "secret1")
        self.other = self.ctx.auth.login("other", "secret1")
        self.s1 = self.ctx.students.add_student(self.admin, "S1", "Ann", "Lee")
        self.s2 = self.ctx.students.add_student(self.admin, "S2", "Bob", "Kim")
        self.mod = self.ctx.modules.add_module(self.admin, "it101", "Intro", self.prof_id)
        self.q1 = self.ctx.modules.add_assessment(self.prof, self.mod, "Quiz 1", 20)
        self.q2 = self.ctx.modules.add_assessment(self.prof, self.mod, "Quiz 2", 30)
        user("stud", "student", self.s1)
        self.stud = self.ctx.auth.login("stud", "secret1")

    def test_sum_aggregation(self):
        self.ctx.scores.record_score(self.prof, self.s1, self.q1, 15)
        self.ctx.scores.record_score(self.prof, self.s1, self.q2, "24.5")
        overall = self.ctx.aggregator.overall(self.s1)
        self.assertEqual(overall.total, 39.5)
        self.assertEqual(overall.maximum, 50)
        self.assertAlmostEqual(overall.percentage, 79.0)
        self.assertEqual(overall.remark, "Passed")
        modules = self.ctx.aggregator.module_standings(self.s1)
        self.assertEqual(modules[0].label, "IT101")
        self.assertEqual(modules[0].items, 2)

    def test_upsert_replaces_score(self):
        self.ctx.scores.record_score(self.prof, self.s1, self.q1, 10)
        self.ctx.scores.record_score(self.prof, self.s1, self.q1, 18)
        scores = self.ctx.scores.list_scores(self.admin)
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].score, 18)

    def test_score_validation(self):
        with self.assertRaises(ValidationError):
            self.ctx.scores.record_score(self.prof, self.s1, self.q1, 21)
        with self.assertRaises(ValidationError):
            self.ctx.scores.record_score(self.prof, self.s1, self.q1, -1)
        with self.assertRaises(ValidationError):
            self.ctx.scores.record_score(self.prof, self.s1, self.q1, "abc")
        with self.assertRaises(ValidationError):
            AssessmentScore(None, 1, 1, 99, 20)

    def test_rbac(self):
        with self.assertRaises(PermissionDenied):
            self.ctx.students.add_student(self.prof, "S9", "X", "Y")
        with self.assertRaises(PermissionDenied):
            self.ctx.scores.record_score(self.stud, self.s1, self.q1, 5)
        with self.assertRaises(PermissionDenied):
            self.ctx.scores.record_score(self.other, self.s1, self.q1, 5)  # not their module
        with self.assertRaises(PermissionDenied):
            self.ctx.modules.add_module(self.prof, "X1", "Nope")
        with self.assertRaises(PermissionDenied):
            self.ctx.students.list_students(self.stud)

    def test_student_sees_only_own_scores(self):
        self.ctx.scores.record_score(self.prof, self.s1, self.q1, 15)
        self.ctx.scores.record_score(self.prof, self.s2, self.q1, 5)
        own = self.ctx.scores.list_scores(self.stud, student_id=self.s2)  # filter must be ignored
        self.assertEqual([s.student_id for s in own], [self.s1])
        self.assertEqual(len(self.ctx.scores.list_scores(self.other)), 0)
        self.assertEqual(len(self.ctx.scores.list_scores(self.prof)), 2)

    def test_login(self):
        with self.assertRaises(AuthenticationError):
            self.ctx.auth.login("admin", "wrong")
        for _ in range(6):
            try:
                self.ctx.auth.login("admin", "wrong")
            except AuthenticationError:
                pass
        with self.assertRaises(AuthenticationError) as cm:
            self.ctx.auth.login("admin", "secret1")
        self.assertIn("Too many", str(cm.exception))

    def test_duplicate_and_lowering_max(self):
        with self.assertRaises(ValidationError):
            self.ctx.students.add_student(self.admin, "S1", "Dup", "Licate")
        self.ctx.scores.record_score(self.prof, self.s1, self.q1, 18)
        with self.assertRaises(ValidationError):
            self.ctx.modules.update_assessment(self.prof, self.q1, "Quiz 1", 10)

    def test_delete_student_cascades(self):
        self.ctx.scores.record_score(self.prof, self.s1, self.q1, 18)
        self.ctx.students.delete_student(self.admin, self.s1)
        self.assertEqual(len(self.ctx.scores.list_scores(self.admin)), 0)

    def test_reports_and_exports(self):
        self.ctx.scores.record_score(self.prof, self.s1, self.q1, 18)
        self.ctx.scores.record_score(self.prof, self.s2, self.q1, 12)
        for kind, target in ((KIND_TRANSCRIPT, self.s1), (KIND_MODULE, self.mod), (KIND_SUMMARY, None)):
            report = self.ctx.reports.build(self.prof, kind, target)
            self.assertTrue(report.rows)
            with tempfile.TemporaryDirectory() as tmp:
                csv_path = os.path.join(tmp, "r.csv")
                CSVExporter().export(report, csv_path)
                self.assertGreater(os.path.getsize(csv_path), 20)
                try:
                    import reportlab  # noqa: F401
                except ImportError:
                    continue
                pdf_path = os.path.join(tmp, "r.pdf")
                PDFExporter().export(report, pdf_path)
                with open(pdf_path, "rb") as fh:
                    self.assertEqual(fh.read(4), b"%PDF")
        with self.assertRaises(PermissionDenied):
            self.ctx.reports.build(self.stud, KIND_SUMMARY)
        own = self.ctx.reports.build(self.stud, KIND_TRANSCRIPT, self.s2)  # target ignored
        self.assertIn("S1", own.subtitle)

    def test_analytics(self):
        self.ctx.scores.record_score(self.prof, self.s1, self.q1, 18)
        labels, counts = self.ctx.analytics.score_distribution(self.admin)
        self.assertEqual(sum(counts), 1)
        cards = dict(self.ctx.analytics.dashboard_cards(self.admin))
        self.assertEqual(cards["Students"], "2")
        self.assertEqual(dict(self.ctx.analytics.dashboard_cards(self.stud))["Cumulative"], "90.0%")

    def test_seed(self):
        ctx = AppContext(":memory:", seed=True)
        admin = ctx.auth.login("admin", "admin123")
        self.assertEqual(len(ctx.students.list_students(admin)), 8)
        student = ctx.auth.login("student1", "student123")
        self.assertGreater(ctx.aggregator.overall(student.student_id).maximum, 0)


if __name__ == "__main__":
    unittest.main()
