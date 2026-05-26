from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SRC = ROOT / "services" / "crm-service" / "src"
sys.path.append(str(SERVICE_SRC))

from handoff import create_handoff  # noqa: E402


class HandoffTest(unittest.TestCase):
    def test_handoff_persists_lead_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            result = create_handoff(
                project_root=project_root,
                session_id="s_001",
                identity={"user_id": "u_1", "role": "parent", "campus": "zhengzhou"},
                message="想预约到校看看，顺便了解学费。",
                answer="可以先预约到校咨询。",
                intent="pricing_consulting",
                retrieval={"allowed_chunks": [{"title": "报名流程说明"}]},
            )
            self.assertGreaterEqual(result["lead_score"], 50)
            lead_path = project_root / "data" / "crm" / "leads.jsonl"
            row = json.loads(lead_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["session_id"], "s_001")
            self.assertIn("到校", row["recommended_action"])


if __name__ == "__main__":
    unittest.main()
