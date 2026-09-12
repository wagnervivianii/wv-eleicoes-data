from typing import Any


def pytest_addoption(parser: Any) -> None:
    parser.addoption(
        "--analytics-test-url",
        default=None,
        help="Explicit disposable local PostgreSQL database at revision 8c31b79e5a02",
    )
