import json
import os
import socket
import subprocess
import sys
import time
import unittest
from urllib.error import URLError
from urllib.request import Request, urlopen
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AdmissionSystemTests(unittest.TestCase):
    def test_waitress_server_serves_live_admission_decision(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(PROJECT_ROOT)
        server = subprocess.Popen(
            [sys.executable, "-m", "src.server", "--host", "127.0.0.1", "--port", str(port)],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            endpoint = f"http://127.0.0.1:{port}/api/admissions/evaluate"
            deadline = time.monotonic() + 10
            response_data = None
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    self.fail(f"Waitress exited with status {server.returncode}.")
                try:
                    request = Request(
                        endpoint,
                        data=json.dumps(
                            {
                                "level": "undergraduate",
                                "results_complete": True,
                                "msce_results": {
                                    "English": 6,
                                    "Mathematics": 5,
                                    "Biology": 5,
                                    "Physical Science": 5,
                                    "Geography": 6,
                                    "History": 6,
                                },
                            }
                        ).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with urlopen(request, timeout=1) as response:
                        response_data = json.loads(response.read())
                    break
                except (URLError, TimeoutError, ConnectionError):
                    time.sleep(0.1)
            self.assertIsNotNone(response_data, "Server did not become ready in time.")
            self.assertTrue(response_data["eligible"])
            self.assertTrue(
                any(
                    program["id"] == "mubas-information-technology"
                    and program["decision"] == "eligible"
                    for program in response_data["programs"]
                )
            )
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
