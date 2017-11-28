import smtplib
import imaplib
import email
import datetime
import time
import random
import inspect
import logging


class PySMSException:
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return repr(self.value)


class PySMS:
    def __init__(self, address, password, smtp_server, smtp_port, imap_server=None, ssl=False, window=5, delimiter=":",
                 identifier_length=4, max_tries=5, wait_time=5):
        self.carriers = {
            # US
            "alltel": "@mms.alltelwireless.com",
            "att": "@mms.att.net",
            "boost": "@myboostmobile.com",
            "cricket": "@mms.cricketwireless.net",
            "p_fi": "msg.fi.google.com",
            "sprint": "@pm.sprint.com",
            "tmobile": "@tmomail.net",
            "us_cellular": "@mms.uscc.net",
            "verizon": "@vzwpix.com",
            "virgin": "@vmpix.com",
            # Canada
            "bell": "@txt.bell.ca",
            "chatr": "@fido.ca",
            "fido": "@fido.ca",
            "freedom": "@txt.freedommobile.ca",
            "koodo": "@msg.koodomobile.com",
            "public_mobile": "@msg.telus.com",
            "telus": "@msg.telus.com",
            "rogers": "@pcs.rogers.com",
            "sasktel": "@sms.sasktel.com",
            "speakout": "@pcs.rogers.com",
            "virgin_ca": "@vmobile.ca"
        }

        # Smtp
        self.smtp = None
        self.validate(address, password)
        self.address = address.encode("utf-8")
        self.password = password.encode("utf-8")
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.ssl = ssl

        # Imap
        self.imap = None
        self.imap_server = imap_server
        self.imap_mailbox = "INBOX"
        self.delimiter = delimiter
        self.identifier_length = identifier_length

        # Parameters
        self.window = window
        self.max_tries = max_tries
        self.wait_time = wait_time

        # Format: key => [time, address, lambda]
        self.hook_dict = {}
        # Format: number => address
        self.addresses = {}
        # Format: address => [uids]
        self.ignore_dict = {}
        self.ignore_set = set()
        self.tracked = set()

        # Logger
        logging.basicConfig()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.init_server()

    # Getter/Setter Functions

    def get_smtp_server(self):
        return self.smtp

    def get_imap_server(self):
        return self.imap

    def get_imap_mailbox(self):
        return self.imap_mailbox

    def set_imap_mailbox(self, mailbox):
        self.imap_mailbox = mailbox

    def get_hook_dict(self):
        return self.hook_dict

    def get_hook_address(self, key):
        return self.hook_dict[key][1]

    def get_delimiter(self):
        return self.delimiter

    def set_delimiter(self, delimiter):
        self.delimiter = delimiter

    def get_window(self):
        return self.window

    def set_window(self, window):
        self.window = window

    def get_max_tries(self):
        return self.max_tries

    def set_max_tries(self, max_tries):
        self.max_tries = max_tries

    def get_wait_time(self):
        return self.wait_time

    def set_wait_time(self, wait_time):
        self.wait_time = wait_time

    def get_identifier_length(self):
        return self.identifier_length

    def set_identifier_length(self, identifier_length):
        self.identifier_length = identifier_length

    # Utility Functions

    def validate(self, address, password):
        try:
            assert isinstance(address, basestring)
            assert isinstance(password, basestring)
        except AssertionError:
            raise PySMSException("Please make sure address and password are strings.")

    def check_callback_requirements(self, callback):
        if self.imap:
            if callable(callback):
                if len(inspect.getargspec(callback).args) == 2:
                    return
                else:
                    raise PySMSException("Callback function does not have the correct number of arguments.")
            else:
                raise PySMSException("Callback function is not callable.")
        else:
            raise PySMSException("IMAP settings not configured or valid.")

    def get_current_time(self):
        return time.time()

    # MMS/Internal Functions

    def init_server(self):
        self.logger.info("Initializing SMTP/IMAP servers.")
        # PySMS at minimum uses smtp server
        try:
            if self.ssl:
                self.smtp = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                self.smtp = smtplib.SMTP(self.smtp_server, self.smtp_port)
                self.smtp.starttls()
            self.smtp.login(self.address, self.password)
        except smtplib.SMTPException:
            raise PySMSException("Unable to start smtp server, please check credentials.")

        # If responding functionality is enabled
        if self.imap_server:
            try:
                if self.ssl:
                    self.imap = imaplib.IMAP4_SSL(self.imap_server)
                else:
                    self.imap = imaplib.IMAP4(self.imap_server)
                r, data = self.imap.login(self.address, self.password)
                if r == "OK":
                    r, data = self.imap.select(self.imap_mailbox)
                    if r != "OK":
                        raise PySMSException("Unable to select mailbox: {0}".format(self.imap_mailbox))
                else:
                    raise PySMSException("Unable to login to IMAP server with given credentials.")
            except imaplib.IMAP4.error:
                raise PySMSException("Unable to start IMAP server, please check address and SSL/TLS settings.")

    def add_number(self, number, carrier):
        if carrier in self.carriers:
            address = number + self.carriers[carrier]
            self.addresses[number] = address
            self.logger.info("Number: {0} added.".format(number))
        else:
            raise PySMSException("Please enter a valid carrier.")

    def del_number(self, number):
        if number in self.addresses:
            del self.addresses[number]
            self.logger.info("Number: {0} deleted.".format(number))
        self.logger.error("Number: {0} not found in list of addresses, ignoring.".format(number))

    def add_hook(self, identifier, address, callback_function):
        self.hook_dict[identifier] = [self.get_current_time(), address, callback_function]
        if address not in self.tracked:
            self.tracked.add(address)

    def remove_hook(self, key):
        if key in self.hook_dict:
            self.tracked.remove(self.hook_dict[key][1])
            del self.hook_dict[key]

    def add_ignore(self, mail, uid):
        if mail["From"] in self.tracked:
            ignore_list = [uid]
            if mail["From"] in self.ignore_dict:
                ignore_list += self.ignore_dict[mail["From"]]
            self.ignore_dict[mail["From"]] = ignore_list
            self.ignore_set.add(uid)

    def del_ignore(self, address):
        for uid in self.ignore_dict[address]:
            self.ignore_set.remove(uid)
        del self.ignore_dict[address]

    def generate_identifier(self):
        def generate():
            ret = ""
            for num in random.sample(range(0, 10), self.identifier_length):
                ret += str(num)
            return ret
        identifier = generate()
        while identifier in self.hook_dict:
            identifier = generate()
        return identifier

    def generate_rfc_query(self):
        ret = ""
        for _ in range(len(self.tracked) - 1):
            ret += "OR "
        for track in self.tracked:
            ret += "FROM " + track + " "
        return ret[:-1]

    def check_tracked(self):
        if self.tracked:
            date = (datetime.date.today() - datetime.timedelta(1)).strftime("%d-%b-%Y")
            r, uids = self.imap.uid("search", None,
                                    "(SENTSINCE {date} {query})".format(date=date, query=self.generate_rfc_query()))
            if r == "OK":
                email_data = self.get_emails(uids)
                if email_data:
                    # Pass a static current time because emails might take time to execute
                    current_time = self.get_current_time()
                    for e_d in email_data:
                        self.check_email(e_d[0], e_d[1], current_time)
                else:
                    self.logger.info("No new emails to check (either ignored or no new mail).")
        else:
            self.logger.info("No addresses being tracked")
        # Clean at end to avoid race condition
        self.clean_hook_dict()

    def get_email(self, uid):
        r, email_data = self.imap.uid('fetch', uid, '(RFC822)')
        if r == "OK":
            return email_data
        return None

    def get_emails(self, uids):
        ret = []
        for uid in uids[0].split():
            if uid not in self.ignore_set:
                ret.append((uid, self.get_email(uid)))
        return ret

    # TODO: use min heap to speed up runtime if a lot of keys
    def clean_hook_dict(self):
        for key in self.hook_dict:
            if self.get_current_time() - self.hook_dict[key][0] > self.window * 60:
                self.del_ignore(self.hook_dict[key][1])
                self.remove_hook(key)

    def check_email(self, uid, email_data, current_time):
        mail = email.message_from_string(email_data[0][1])
        mail_time = email.utils.mktime_tz(email.utils.parsedate_tz(mail["Date"]))
        if current_time - mail_time < self.window * 60:
            if mail.get_content_maintype() == "multipart":
                for part in mail.walk():
                    if part.get_content_maintype() != 'multipart' and part.get('Content-Disposition') is not None:
                        response = part.get_payload(decode=True)
                        response = response.split(self.delimiter)
                        if len(response) == 2:
                            key = response[0].strip()
                            value = response[1].strip()
                            # If hook is not valid then also ignore
                            if not self.execute_hook(key, value):
                                self.logger.info("Adding failed hook with uid: {uid} to ignore.".format(uid=uid))
                                self.add_ignore(mail, uid)
                            return
        # Clean_hook_dict will take care of this later
        self.logger.info("Email with uid: {uid} is expired, ignoring in next check".format(uid=uid))
        # Add uid to ignore if uid is expired so it knows not to request it next cycle
        self.add_ignore(mail, uid)

    def execute_hook(self, key, value):
        success = True
        if key in self.hook_dict:
            try:
                self.hook_dict[key][2](self.hook_dict[key][1], value)
            # General Exception here to catch user defined lambda function
            except Exception:
                success = False
            if success:
                self.logger.info("Hook with key: {key} for {address} executed.".format(key=key, address=self.hook_dict[key][1]))
            else:
                self.logger.info("Hook with key: {key} for {address} was not executed or failed.".format(
                    key=key, address=self.hook_dict[key][1]))
            # Remove from ignore and remove from hook_dict
            self.del_ignore(self.hook_dict[key][1])
            self.remove_hook(key)
        else:
            self.logger.info("Hook with key: {key} not valid.".format(key=key))
            success = False
        return success

    def text(self, msg, address=None, callback=False):
        ret = []
        if address:
            addresses = [address]
        else:
            addresses = self.addresses.values()
        tmp_msg = msg

        for address in addresses:
            success = False
            for _ in range(self.max_tries):
                try:
                    # Add call back function if enabled
                    identifier = None
                    if callback:
                        # Validate callback function
                        self.check_callback_requirements(callback)
                        identifier = self.generate_identifier()
                        tmp_msg += "\rReply with identifier {identifier} followed by a \"{delimiter}\"".format(
                            identifier=identifier, delimiter=self.delimiter)

                    # Send text message through SMS gateway of destination address
                    self.smtp.sendmail(self.address, address, tmp_msg)
                    self.logger.info("Message: {message} sent to: {address} successfully.".format(message=tmp_msg, address=address))
                    # Only add hook if message was sent successfully
                    if callback:
                        self.add_hook(identifier, address, callback)
                    # Reset msg back to original
                    tmp_msg = msg
                    success = True
                    break
                except smtplib.SMTPException:
                    self.logger.info("Failed to send message, reinitializing server.")
                    try:
                        self.init_server()
                    except PySMSException:
                        self.logger.info("Server reinitialization failed.")
                        pass
                    time.sleep(self.wait_time)
                    pass
            if not success:
                self.logger.info("Message: \"{message}\" sent to: {address} unsuccessfully.".format(message=msg, address=address))
            ret.append(success)
        return ret

