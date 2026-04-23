import tempfile
import unittest
from pathlib import Path

from agents.system import file_agent


class FileAgentSecurityTests(unittest.TestCase):
    def test_validate_safe_path_allows_workspace_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            dir=str(file_agent.PROJECT_ROOT),
            delete=False,
        ) as handle:
            handle.write("AURA workspace file")
            temp_path = Path(handle.name)

        try:
            allowed, safe_path, error = file_agent._validate_safe_path(str(temp_path))
            self.assertTrue(allowed)
            self.assertEqual(safe_path, temp_path.resolve())
            self.assertIsNone(error)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_validate_safe_path_blocks_traversal_attempts(self):
        allowed, safe_path, error = file_agent._validate_safe_path(r"..\secret.txt", must_exist=False)

        self.assertFalse(allowed)
        self.assertIsNone(safe_path)
        self.assertIn("Path traversal is blocked", error)

    def test_read_text_file_blocks_outside_workspace(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write("outside workspace")
            temp_path = Path(handle.name)

        try:
            result = file_agent.read_text_file(str(temp_path))
            self.assertIn("active workspace", result)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_list_files_blocks_outside_workspace_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = file_agent.list_files(temp_dir)
            self.assertIn("active workspace", result)


if __name__ == "__main__":
    unittest.main()
