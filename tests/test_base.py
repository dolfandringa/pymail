"""Test Base Mail classes"""

# pylint: disable=duplicate-code

import logging
from base64 import b64encode
from email import message_from_bytes
from imaplib import IMAP4
from pathlib import Path
from unittest.mock import call

import pytest

from pymail import base
from pymail.exceptions import PermissionDeniedError

logging.basicConfig(level=logging.DEBUG)
pytestmark = pytest.mark.asyncio


@pytest.fixture(name="imap")
def imap_fixture(mocker):
    """Fixture to return and mock BaseMailProvider"""
    mock_imap4 = mocker.patch("pymail.base.IMAP4")
    mocker.patch.object(mock_imap4, "open")
    connection = mock_imap4.return_value
    provider = base.BaseMailProvider()
    return (provider, connection)


class TestBaseMailProvider:
    """Test BaseMailProvider"""

    def test_message_to_dict(self, rfc822_email: str, imap):
        """Test turning a message into a dictionary"""
        message = message_from_bytes(rfc822_email.encode("utf-8"))
        provider, *_ = imap
        actual = provider.message_to_dict(message)
        image = b64encode((Path(__file__).parent / "example.png").open("rb").read())
        assert dict(message).items() <= actual.items()
        assert actual["attachments"] == [
            {"name": "example.png", "content-type": "image/png", "content": image}
        ]
        assert len(actual["body"]) > 0 and isinstance(actual["body"], (bytes, str))

    def test_get_connection(self, mocker, imap):
        """test get_connection."""
        username = "dolf"
        password = "secret"
        provider, connection = imap
        mock_login = mocker.patch.object(connection, "login")
        mock_login.return_value = "OK", ""
        provider.get_connection(username, password)
        connection.login.assert_called_once_with(username, password)

    def test_get_connection_error(self, mocker, imap):
        """test get_connection when raising an imap error."""
        username = "dolf"
        password = "secret"
        provider, connection = imap
        mock_login = mocker.patch.object(connection, "login")
        mock_login.side_effect = IMAP4.error("Permission denied")
        with pytest.raises(PermissionDeniedError):
            provider.get_connection(username, password)
        connection.login.assert_called_once_with(username, password)

    async def test_fetch_extra_fields(
        self, mocker, imap, rfc822_email: str
    ):  # pylint: disable=too-many-locals
        """Test fetching and individual mail."""
        ids = [1, 25, 12, 34]
        email = rfc822_email.encode("utf-8")
        fields = ("RFC822", "BODY[TEXT]", "X-OTHERFIELD")
        calls = [call(str(id), f"""({" ".join(fields)})""") for id in ids]
        provider, connection = imap
        mock_fetch = mocker.patch.object(connection, "fetch")
        mail_size = len(email)
        extra_fields = f"""X-OTHERFIELDS 25 RC822 {{{mail_size}}}"""
        messages = [
            [
                (
                    f"{id} ({extra_fields}".encode("utf-8"),
                    email,
                ),
                b")",
            ]
            for id in ids
        ]
        mock_fetch.side_effect = [(b"OK", message) for message in messages]
        actual = [
            provider.message_to_dict(message)
            async for message in provider.fetch(ids, connection, fields=fields)
        ]
        assert mock_fetch.mock_calls == calls
        expected = [
            provider.message_to_dict(message_from_bytes(m[0][1])) for m in messages
        ]
        extra_fields = provider.get_extra_fields_from_imap(extra_fields, fields)
        assert actual == [d | extra_fields for d in expected]

    async def test_fetch(self, mocker, imap, rfc822_email: str):
        """Test fetching and individual mail."""
        ids = [1, 25, 12, 34]
        email = rfc822_email.encode("utf-8")
        calls = [call(str(id), "(RFC822 BODY[TEXT])") for id in ids]
        provider, connection = imap
        mock_fetch = mocker.patch.object(connection, "fetch")
        mail_size = len(email)
        messages = [
            [(f"{id} (RFC822 {{{mail_size}}}".encode("utf-8"), email), b")"]
            for id in ids
        ]
        mock_fetch.side_effect = [(b"OK", message) for message in messages]
        actual = [
            provider.message_to_dict(message)
            async for message in provider.fetch(ids, connection)
        ]
        assert mock_fetch.mock_calls == calls
        assert actual == [
            provider.message_to_dict(message_from_bytes(m[0][1])) for m in messages
        ]

    async def test_search(
        self, mocker, imap, rfc822_email, AsyncIterator  # pylint: disable=invalid-name
    ):  # pylint: disable=too-many-locals
        """test search"""
        username = "dolf"
        password = "secret"
        provider, connection = imap
        mock_get_connection = mocker.patch.object(provider, "get_connection")
        mock_get_connection.return_value = connection
        mock_list = mocker.patch.object(connection, "list")
        mock_list.return_value = (b"OK", [b"bla", b"INBOX", b"test"])
        mock_select = mocker.patch.object(connection, "select")
        mock_search = mocker.patch.object(connection, "search")
        ids = [b"1 25 12 34"]
        expected = [
            dict(message_from_bytes(m))
            for m in [rfc822_email.encode("utf-8")]
            * len(ids[0].decode("utf-8").split())
        ]
        mock_search.return_value = ("OK", ids)
        mock_fetch = mocker.patch.object(provider, "fetch")
        mock_fetch.return_value = AsyncIterator(expected)
        actual = [
            dict(message)
            for message in await provider.search("Something", username, password)
        ]
        mock_get_connection.assert_called_once_with(username, password)
        mock_list.assert_called_once_with()
        mock_select.assert_called_once_with(mailbox="INBOX")
        mock_search.assert_called_once_with(None, "Something")
        mock_fetch.assert_called_with(ids[0].decode("utf-8").split(), connection)
        assert actual == expected
