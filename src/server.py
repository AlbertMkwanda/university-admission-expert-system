"""Run the application with the production-oriented Waitress WSGI server."""

import argparse

from waitress import serve

from src.web import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the admission expert system.")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: localhost).")
    parser.add_argument("--port", type=int, default=8000, help="TCP port (default: 8000).")
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535.")
    serve(app, host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
