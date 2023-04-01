"""GMail classes"""
import imaplib
import logging
from email.message import Message
from imaplib import IMAP4_SSL
from typing import AsyncIterator, List

from .base import BaseMailProvider
from .exceptions import PermissionDeniedError


class GMailProvider(BaseMailProvider):
    """GMail mail provider"""

    def get_connection(self, username: str, secret: str) -> IMAP4_SSL:
        """
        Get the connection using OAuth2 token.
        """
        log = logging.getLogger(__name__)
        connection = IMAP4_SSL(host="imap.gmail.com")
        auth_string = f"user={username}\1auth=Bearer {secret}\1\1".encode("utf-8")
        try:
            log.debug("auth_string: %s", auth_string)
            connection.authenticate("XOAUTH2", lambda _: auth_string)
        except imaplib.IMAP4.error as exc:
            raise PermissionDeniedError(
                f"Permission denied when authenticating: {exc}"
            ) from exc
        return connection

    async def fetch(
        self,
        ids: List[int],
        connection: IMAP4_SSL,
        fields=("RFC822", "BODY[TEXT]", "X-GM-LABELS", "X-GM-THRID", "X-GM-MSGID"),
    ) -> AsyncIterator[Message]:
        """Fetch GMail emails with additional fields."""
        async for message in super().fetch(ids, connection, fields):
            yield message
