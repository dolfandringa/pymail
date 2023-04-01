"""Test GMail class"""
# pylint: disable=duplicate-code

from email import message_from_bytes
from imaplib import IMAP4_SSL
from unittest.mock import call

import pytest

from pymail import gmail
from pymail.exceptions import PermissionDeniedError

pytestmark = pytest.mark.asyncio


@pytest.fixture(name="imap")
def imap_fixture(mocker):
    """Fixture to return and mock GMailProvider"""
    mock_imap4 = mocker.patch("pymail.gmail.IMAP4_SSL")
    mocker.patch.object(mock_imap4, "open")
    connection = mock_imap4.return_value
    provider = gmail.GMailProvider()
    return (provider, connection, mock_imap4)


class TestGMailProvider:
    """Test GMailProvider"""

    def test_get_connection(self, mocker, imap):
        """test get_connection."""
        username = "roger.rabbit@gmail.com"
        token = "versecret"
        auth_string = f"user={username}\1auth=Bearer {token}\1\1"
        provider, connection, mock_imap4 = imap
        mock_auth = mocker.patch.object(connection, "authenticate")
        mock_auth.return_value = "OK", ""
        provider.get_connection(username, token)
        mock_auth.assert_called_once()
        print(f"calls: {mock_auth.calls}")
        assert mock_auth.call_args[0][0] == "XOAUTH2"
        assert mock_auth.call_args[0][1]("bla") == auth_string.encode("utf-8")
        mock_imap4.assert_called_once_with(host="imap.gmail.com")

    def test_get_connection_error(self, mocker, imap):
        """test get_connection when raising an imap error."""
        username = "dolf"
        token = "secret"
        auth_string = f"user={username}\1auth=Bearer {token}\1\1"
        provider, connection, _ = imap
        mock_auth = mocker.patch.object(connection, "authenticate")
        mock_auth.side_effect = IMAP4_SSL.error("Permission denied")
        with pytest.raises(PermissionDeniedError):
            provider.get_connection(username, token)
        mock_auth.assert_called_once()
        assert mock_auth.call_args[0][0] == "XOAUTH2"
        assert mock_auth.call_args[0][1]("bla") == auth_string.encode("utf-8")

    async def test_fetch(
        self, mocker, imap, rfc822_email: str
    ):  # pylint: disable=too-many-locals
        """Test fetching and individual mail."""
        ids = [1, 25, 12, 34]
        fields = ("RFC822", "BODY[TEXT]", "X-GM-LABELS", "X-GM-THRID", "X-GM-MSGID")
        email = rfc822_email.encode("utf-8")
        calls = [call(str(id), f"""({" ".join(fields)})""") for id in ids]
        provider, connection, _ = imap
        mock_fetch = mocker.patch.object(connection, "fetch")
        mail_size = len(email)
        gmail_fields = (
            """X-GM-THRID 1760246054454316889 X-GM-MSGID """
            """1760246054454316889 X-GM-LABELS ("\\\\Important")"""
        )
        messages = [
            [
                (f"{id} ({gmail_fields} RFC822 {{{mail_size}}}".encode("utf-8"), email),
                b")",
            ]
            for id in ids
        ]
        mock_fetch.side_effect = [(b"OK", message) for message in messages]
        actual = [
            provider.message_to_dict(message)
            async for message in provider.fetch(ids, connection)
        ]
        assert mock_fetch.mock_calls == calls
        expected = [
            provider.message_to_dict(message_from_bytes(m[0][1])) for m in messages
        ]
        extra_fields = provider.get_extra_fields_from_imap(gmail_fields, fields)
        assert actual == [d | extra_fields for d in expected]
