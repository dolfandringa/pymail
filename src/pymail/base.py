"""Base mail classes to inherit from."""
import imaplib
import logging
from base64 import b64encode
from email import message_from_bytes
from email.message import Message
from imaplib import IMAP4
from typing import AsyncIterator, List

from .exceptions import PermissionDeniedError


class BaseMailProvider:
    """Basic Mail Provider to inherit from"""

    def message_to_dict(self, message: Message) -> dict:
        """Convert an email.message.Message to a dictionary."""
        attachments = []

        body = ""
        if message.is_multipart():
            for part in message.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get("Content-Disposition"))
                if ctype in {"text/plain", "text/html"} and "attachment" not in cdispo:
                    body = part.get_payload(decode=True)  # decode
                elif "attachment" in cdispo:
                    payload = part.get_payload(decode=True)
                    attachments.append(
                        {
                            "content-type": ctype,
                            "content": b64encode(payload),
                            "name": part.get_filename(),
                        }
                    )
        else:
            body = message.get_payload(decode=True)
        return dict(message) | {"body": body, "attachments": attachments}

    def get_connection(self, username: str, secret: str) -> IMAP4:
        """Get the IMAP4 connection."""
        connection = IMAP4()
        print(f"connection.error: {connection.error} {type(connection.error)}")
        try:
            connection.login(username, secret)
        except imaplib.IMAP4.error as exc:
            # use the fully qualified class path else unittests will see a MagicMock
            raise PermissionDeniedError(
                "Permission denied when trying to login."
            ) from exc
        return connection

    def get_extra_fields_from_imap(self, fields_string: str, fields: List[str]) -> dict:
        """Take the extra fields from the IMAP string."""
        indices = sorted(
            list(
                filter(
                    lambda x: x[0] >= 0,
                    [(fields_string.find(field), field) for field in fields],
                )
            ),
            key=lambda x: x[0],
        )
        indices.append((len(fields_string), "end"))
        extra_fields = [
            (indices[i][1], fields_string[indices[i][0] : indices[i + 1][0]])
            for i in range(len(indices) - 1)
        ]
        extra_fields = dict(
            (f[0], f[1].replace(f[0] + " ", "").strip())
            for f in extra_fields
            if f[0] != "RFC822"
        )
        return extra_fields

    async def fetch(
        self, ids: List[int], connection: IMAP4, fields=("RFC822", "BODY[TEXT]")
    ) -> AsyncIterator[Message]:
        """Fetch emails by ids."""
        log = logging.getLogger(__name__)
        for mid in ids:
            _, message = connection.fetch(str(mid), f"""({" ".join(fields)})""")
            if message is None or message[0] is None:
                log.error("Message %i is empty", mid)
                continue
            log.debug("Got message %s", message[0])
            if not isinstance(message[0][1], bytes):
                log.error("Message %i is not of a bytes object: %s", mid, message[0][1])
                continue
            extra_fields = {}
            if isinstance(message[0][0], bytes):
                extra_fields = self.get_extra_fields_from_imap(
                    message[0][0].decode("utf-8"), fields
                )
            result = message_from_bytes(message[0][1])
            log.debug("Parsed %s", dict(result))
            for k, v in extra_fields.items():  # pylint: disable=invalid-name
                result[k] = v
            yield result

    async def search(self, query: str, username: str, secret: str) -> List[Message]:
        """Search for emails."""
        log = logging.getLogger(__name__)
        connection = self.get_connection(username, secret)
        log.debug("Connection established. Capability: %s", connection.PROTOCOL_VERSION)
        inboxes = connection.list()[1]
        log.debug(inboxes)
        connection.select(mailbox="INBOX")
        res = connection.search(None, query)
        if res[0] != "OK":
            log.error("Unexpected error executing search %s", res)
            raise RuntimeError("Unkown error executing search")
        ids = res[1][0].decode("utf-8").split()
        log.debug("ids: %s", ids)
        return [message async for message in self.fetch(ids, connection)]
