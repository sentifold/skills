"""Shell helpers must survive a Windows Git checkout before Linux deployment."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LineEndingTests(unittest.TestCase):
    def test_windows_checkout_preserves_lf_in_shell_helpers(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            attributes = ROOT / ".gitattributes"
            if attributes.exists():
                shutil.copyfile(attributes, repo / attributes.name)
            helpers = sorted(ROOT.glob("skills/*/scripts/*.sh"))
            self.assertTrue(helpers)
            for helper in helpers:
                target = repo / helper.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(helper.read_bytes().replace(b"\r\n", b"\n"))
            subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=true", "add", "."],
                           check=True, capture_output=True)
            checkout = Path(temp) / "checkout"
            subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=true",
                            "checkout-index", "--all", "--prefix=" + checkout.as_posix() + "/"],
                           check=True, capture_output=True)
            for helper in helpers:
                with self.subTest(helper=helper.relative_to(ROOT).as_posix()):
                    data = (checkout / helper.relative_to(ROOT)).read_bytes()
                    self.assertNotIn(b"\r\n", data)


if __name__ == "__main__":
    unittest.main()
