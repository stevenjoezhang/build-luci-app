import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/download-release-sdk.sh"
FILENAME = "openwrt-sdk-25.12.6-x86-64_gcc-14.3.0_musl.Linux-x86_64.tar.zst"

# Stub only HTTP transfers; checksum verification and archive extraction are real.
HTTP_STUB = r'''
import fnmatch
import os
from pathlib import Path
import shutil
import sys

root = Path(os.environ["FIXTURE_ROOT"])
args = sys.argv[1:]
tool = Path(sys.argv[0]).name
with (root / "requests").open("a") as log:
    log.write(tool + " " + " ".join(args) + "\n")
if tool == "curl":
    url = next(arg for arg in args if arg.startswith("https://"))
    name = "versions.json" if url.endswith("/.versions.json") else "sha256sums"
    if os.environ.get("FAIL_TRANSFER") == name:
        sys.exit(22)
    if "--output" in args:
        shutil.copyfile(root / name, args[args.index("--output") + 1])
    else:
        sys.stdout.write((root / name).read_text())
else:
    if os.environ.get("FAIL_TRANSFER") == "wget":
        sys.exit(8)
    assert "--recursive" in args and "--level=1" in args
    assert "--no-parent" in args and "--https-only" in args
    pattern = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--accept="))
    dest = Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("--directory-prefix=")))
    for file in (root / "downloads").iterdir():
        if fnmatch.fnmatchcase(file.name, pattern):
            shutil.copyfile(file, dest / file.name)
'''


class DownloadReleaseSDKTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.downloads = self.root / "downloads"
        self.downloads.mkdir()
        self.dest = self.root / "sdk"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for tool in ("curl", "wget"):
            stub = self.bin / tool
            stub.write_text(f"#!{sys.executable}\n" + HTTP_STUB)
            stub.chmod(0o755)
        self.env = dict(os.environ, FIXTURE_ROOT=str(self.root),
                        PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        self.versions = self.root / "versions.json"
        self.versions.write_text(json.dumps({"stable_version": "25.12.6"}))
        archive = self.root / "sdk.tar"
        with tarfile.open(archive, "w") as tar:
            data = b"SDK fixture\n"
            entry = tarfile.TarInfo("openwrt-sdk/README")
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
        self.archive = self.downloads / FILENAME
        subprocess.run(["zstd", "-q", str(archive), "-o", str(self.archive)], check=True)
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.checksum_line = f"{digest} *{FILENAME}\n"
        self.sums = self.root / "sha256sums"
        self.sums.write_text(self.checksum_line)

    def run_script(self, version="stable", success=True):
        result = subprocess.run(["bash", str(SCRIPT), version, str(self.dest)],
                                env=self.env, text=True, capture_output=True)
        output = result.stdout + result.stderr
        if success:
            self.assertEqual(result.returncode, 0, output)
            self.assertEqual((self.dest / "README").read_text(), "SDK fixture\n")
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertFalse(self.dest.exists(), output)
        return output

    def test_latest_release(self):
        output = self.run_script()
        self.assertIn(f"Installed verified SDK: https://downloads.openwrt.org/releases/25.12.6/targets/x86/64/{FILENAME}", output)

    def test_pinned_release_skips_version_index(self):
        self.run_script("25.12.6")
        self.assertNotIn(".versions.json", (self.root / "requests").read_text())

    def test_text_mode_checksum(self):
        self.sums.write_text(self.checksum_line.replace(" *", "  "))
        self.run_script()

    def test_invalid_release(self):
        self.assertIn("Invalid stable release version", self.run_script("../snapshot", False))
        self.assertFalse((self.root / "requests").exists())

    def test_missing_stable_version(self):
        self.versions.write_text("{}")
        self.run_script(success=False)
        self.assertNotIn("wget", (self.root / "requests").read_text())

    def test_no_matching_archive(self):
        self.archive.unlink()
        self.assertIn("found 0", self.run_script(success=False))

    def test_multiple_matching_archives(self):
        shutil.copyfile(self.archive, self.downloads / FILENAME.replace("14.3.0", "14.4.0"))
        self.assertIn("found 2", self.run_script(success=False))

    def test_unrelated_files_ignored(self):
        (self.downloads / FILENAME.replace("sdk", "imagebuilder")).write_text("ignore")
        self.run_script()

    def test_corrupt_archive(self):
        self.archive.write_bytes(b"corrupt")
        self.assertIn("FAILED", self.run_script(success=False))

    def test_missing_checksum(self):
        self.sums.write_text(self.checksum_line.replace(FILENAME, "another-file"))
        self.assertIn("SHA-256 entry", self.run_script(success=False))

    def test_duplicate_checksum(self):
        self.sums.write_text(self.checksum_line * 2)
        self.assertIn("SHA-256 entry", self.run_script(success=False))

    def test_invalid_checksum(self):
        self.sums.write_text(f"invalid *{FILENAME}\n")
        self.assertIn("SHA-256 entry", self.run_script(success=False))

    def test_failed_transfers(self):
        for transfer in ("versions.json", "wget", "sha256sums"):
            with self.subTest(transfer=transfer):
                self.env["FAIL_TRANSFER"] = transfer
                self.run_script(success=False)


if __name__ == "__main__":
    unittest.main()
