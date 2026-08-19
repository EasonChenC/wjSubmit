"""Task count means successful submissions, not merely attempted submissions."""

import unittest

from api.models import SubmitConfig
from db.models import QuestionnaireTask


class SubmitSuccessTargetTests(unittest.TestCase):
    def test_default_retry_budget_is_ten(self):
        self.assertEqual(SubmitConfig().max_submit_attempts, 10)

    def test_retry_budget_is_persisted_on_task(self):
        self.assertIn("submit_max_attempts", QuestionnaireTask.__table__.columns)

    def test_unknown_submit_result_is_not_counted_as_success(self):
        from pathlib import Path
        source = Path("core/dynamic_submitter.py").read_text(encoding="utf-8")
        self.assertIn("未发现明确提交成功标志，判定本次提交失败", source)
        self.assertNotIn("提交成功（假定）", source)


if __name__ == "__main__":
    unittest.main()
