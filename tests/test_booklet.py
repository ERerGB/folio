import json
import importlib.util
import io
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "booklet.py"


def load_script():
    spec = importlib.util.spec_from_file_location("booklet", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args, expect_ok=True):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        text=True, capture_output=True, check=False,
    )
    if expect_ok and result.returncode:
        raise AssertionError(result.stderr)
    return result


class BookletLifecycleTests(unittest.TestCase):
    def test_build_revision_delivery_and_move(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            run("init", root, "--id", "sample", "--title", "A Sample", "--language", "en")
            book = json.loads((root / "book.json").read_text())
            book["chapters"] = [{"id": "start", "title": "Start", "file": "chapters/start.md"}]
            (root / "book.json").write_text(json.dumps(book))
            chapter = root / "chapters" / "start.md"
            chapter.write_text("First version.\n")

            first = json.loads(run("build", root).stdout)
            self.assertEqual(first["edition"], 1)
            self.assertEqual(first["result"], "pending")
            self.assertFalse(Path(first["epub_path"]).is_absolute())
            with ZipFile(root / first["epub_path"]) as archive:
                self.assertEqual(archive.read("mimetype"), b"application/epub+zip")

            chapter.write_text("Revised before delivery.\n")
            revised = json.loads(run("build", root).stdout)
            self.assertEqual(revised["edition"], 1)
            self.assertNotEqual(revised["epub_sha256"], first["epub_sha256"])
            self.assertEqual(json.loads(run("build", root).stdout)["edition"], 1)

            moved = Path(temp) / "moved"
            root.rename(moved)
            recorded = json.loads(run(
                "record-delivery", moved, "--device", "Test reader", "--transport", "usb",
                "--remote-path", "Books/sample-e001.epub", "--verified-size", revised["epub_size"],
                "--evidence", "Device library showed matching filename and size",
            ).stdout)
            self.assertEqual(recorded["edition"], 1)
            self.assertEqual(json.loads(run("build", moved).stdout)["result"], "unchanged")

            chapter = moved / "chapters" / "start.md"
            chapter.write_text("Second edition.\n")
            second = json.loads(run("build", moved).stdout)
            self.assertEqual(second["edition"], 2)
            run("archive", moved)
            self.assertNotEqual(run("build", moved, expect_ok=False).returncode, 0)

    def test_rejects_public_and_loopback_delivery_hosts(self):
        module = load_script()
        for host in ("8.8.8.8:8085", "127.0.0.1:8085", "192.168.1.1:99999"):
            with self.assertRaises(ValueError):
                module.device_url(host)

    def test_booxdrop_adapter_verifies_before_recording(self):
        class Handler(BaseHTTPRequestHandler):
            file_size = None
            filename = None
            upload_count = 0

            def log_message(self, *args):
                pass

            def reply(self, value):
                data = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/":
                    self.reply({"page": "BOOX Drop"})
                elif self.path == "/api/device":
                    self.reply({"model": "TestReader"})
                elif self.path == "/api/library":
                    books = []
                    if self.file_size is not None:
                        books.append({"name": self.filename, "metadata": {
                            "size": self.file_size, "location": "/Books/" + self.filename,
                        }})
                    self.reply({"visibleBookList": books})
                else:
                    self.send_error(404)

            def do_POST(self):
                if self.path != "/api/library/upload":
                    self.send_error(404)
                    return
                data = self.rfile.read(int(self.headers["Content-Length"]))
                marker = b"Content-Type: application/epub+zip\r\n\r\n"
                boundary = self.headers["Content-Type"].split("boundary=", 1)[1].encode()
                uploaded_file = data.split(marker, 1)[1].split(b"\r\n--" + boundary + b"--", 1)[0]
                self.__class__.file_size = len(uploaded_file)
                self.__class__.filename = self.server.expected_name
                self.__class__.upload_count += 1
                self.reply({"code": 0, "successful": True})

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            run("init", root, "--id", "sample", "--title", "A Sample")
            book = json.loads((root / "book.json").read_text())
            book["chapters"] = [{"id": "start", "title": "Start", "file": "chapters/start.md"}]
            (root / "book.json").write_text(json.dumps(book))
            (root / "chapters" / "start.md").write_text("Hello reader.\n")
            candidate = json.loads(run("build", root).stdout)
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            server.expected_name = Path(candidate["epub_path"]).name
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                module = load_script()
                address = f"http://127.0.0.1:{server.server_port}"
                args = ["booklet.py", "send-booxdrop", str(root), "--host", "192.168.1.23:8085", "--device", "TestReader"]
                with patch.object(module, "device_url", return_value=address), patch.object(sys, "argv", args):
                    with redirect_stdout(io.StringIO()) as output:
                        module.main()
                    self.assertEqual(json.loads(output.getvalue())["result"], "delivered")
                    with redirect_stdout(io.StringIO()) as second_output:
                        module.main()
                    self.assertEqual(json.loads(second_output.getvalue())["result"], "already-delivered")
                self.assertEqual(len(json.loads((root / "lifecycle.json").read_text())["deliveries"]), 1)
                self.assertEqual(Handler.file_size, candidate["epub_size"])
                self.assertEqual(Handler.upload_count, 1)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
