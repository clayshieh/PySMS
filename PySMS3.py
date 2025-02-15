"""Python3 implementation for PySMS."""

import constants

import dataclasses
import logging
from typing import Sequence, Optional, Callable
import smtplib
import email
import email.policy

logger = logging.getLogger(__name__)


def convert_number_to_email(phone_number: str, carrier: str) -> Optional[str]:
    """Utility function to convert phone number to the equivalent email."""
    if carrier not in constants.CARRIERS:
        return None
    return f"{phone_number}{constants.CARRIERS[carrier]}"


class PySMS3Exception(Exception):
    """Exception class for PySMS3"""


@dataclasses.dataclass
class PhoneNumber:
    """Class to represent a phone number."""
    number: str
    carrier: str


class PySMS3:
    """Python3 class for PySMS."""
    def __init__(self, host: str, port: int, address: str, password: str, ssl: bool = True):
        # User parameters
        self.host: str = host
        self.port: int = port
        self.address: str = address
        self.password: str = password
        self.ssl: bool = ssl

        # Initialized variables
        self.smtp_client: smtplib.SMTP

        self.init_smtp(host=self.host, port=self.port, ssl=self.ssl)

    def init_smtp(self, host: str, port: int, ssl: bool):
        try:
            if ssl:
                self.smtp_client = smtplib.SMTP_SSL(host=host, port=port)
            else:
                self.smtp_client = smtplib.SMTP(host=host, port=port)
            self.smtp_client.login(self.address, self.password)
        except smtplib.SMTPException as e:
            raise PySMS3Exception(f"Unable to start smtp server, please check credentials. Error: {e}")

    def send_message(self, addresses: Sequence[str], msg: str):
        """Sends an email via the smtp client."""
        if not self.smtp_client:
            raise PySMS3Exception("SMTP client not initialized")
        message = email.message_from_string(s=msg, policy=email.policy.default)
        self.smtp_client.send_message(msg=message, from_addr=self.address, to_addrs=addresses)

    def send_text_message(self, phone_numbers: Sequence[PhoneNumber], msg: str, ignore_failures: bool = False):
        """Sends a message as a text message after converting the phone number into the equivalent email address."""

        # TODO(clayshieh): implement carrier lookup.
        converted_addresses = list()
        for pn in phone_numbers:
            if converted_addr := convert_number_to_email(phone_number=pn.number, carrier=pn.carrier):
                converted_addresses.append(converted_addr)
            elif ignore_failures:
                logger.warning(f"Failed to convert phone number: {pn}, skipping.")
                continue
            else:
                raise PySMS3Exception(f"Failed to convert phone number:")
        return self.send_message(addresses=converted_addresses, msg=msg)

    def send_text_message_with_callback(self, phone_numbers: Sequence[PhoneNumber], msg: str, callback: Callable[[str, str], None], ignore_failures: bool = False):
        """Sends a message as a text message with a callback function after converting the phone number into the equivalent email address."""
        converted_addresses = list()
        for pn in phone_numbers:
            if converted_addr := convert_number_to_email(phone_number=pn.number, carrier=pn.carrier):
                converted_addresses.append(converted_addr)
            elif ignore_failures:
                logger.warning(f"Failed to convert phone number: {pn}, skipping.")
                continue
            else:
                raise PySMS3Exception(f"Failed to convert phone number:")
        
        # Send the message
        self.send_message(addresses=converted_addresses, msg=msg)
        
        # Execute the callback function
        for address in converted_addresses:
            callback(address, msg)
