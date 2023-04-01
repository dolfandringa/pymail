"""Fixtures for testing."""
from base64 import b64encode
from pathlib import Path

import pytest


@pytest.fixture
def rfc822_email():
    """RFC822 email string."""
    return (
        (
            """From: John Smith <john.smith@example.com>\r\n"""
            """To: Jane Doe <jane.doe@example.com>\r\n"""
            """Subject: Example Email\r\n"""
            """Date: Thu, 17 Mar 2023 12:30:00 -0500\r\n"""
            """Message-ID: <1234@example.com>\r\n"""
            """Content-Type: multipart/mixed; boundary=1234567890\r\n\r\n"""
            """--1234567890\r\nContent-Type: text/plain; charset="us-ascii"\r\n\r\n"""
            """Hello Jane,\r\n\r\nI hope this email finds you well."""
            """I just wanted to reach out and say hello and see how you're doing. """
            """It's been a while since we last spoke, and I wanted to catch up.\r\n"""
            """\r\nBest regards,\r\n\r\nJohn\r\n\r\n"""
            """--1234567890\r\n"""
            """Content-Type: image/png\r\n"""
            """Content-Transfer-Encoding: base64\r\n"""
            """Content-Disposition: attachment; filename="example.png"\r\n\r\n"""
        )
        + b64encode((Path(__file__).parent / "example.png").open("rb").read()).decode(
            "utf-8"
        )
        + "\r\n\r\n--1234567890--"
    )


@pytest.fixture
def AsyncIterator():  # pylint: disable=invalid-name
    """Return the AsyncIterator class."""
    return _AsyncIterator


class _AsyncIterator:
    """Wrapper to make a sequence into an async iterator."""

    def __init__(self, seq):
        self.iter = iter(seq)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc
