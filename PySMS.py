import smtplib
import imaplib
import email
import datetime
import time
import random


class PySMSException:
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return repr(self.value)


class PySMS:
    def __init__(self, address, password, smtp_server, smtp_port, imap_server=None, window=None, delimiter=":",
                 identifier_length=4, ssl=False):
        # referenced from https://www.digitaltrends.com/mobile/how-to-send-e-mail-to-sms-text/
        self.carriers = {
            "alltel": "@mms.alltelwireless.com",
            "att": "@mms.att.net",
            "boost": "@myboostmobile.com",
            "cricket": "@mms.cricketwireless.net",
            "p_fi": "msg.fi.google.com",
            "sprint": "@pm.sprint.com",
            "tmobile": "@tmomail.net",
            "us_cellular": "@mms.uscc.net",
            "verizon": "@vzwpix.com",
            "virgin": "@vmpix.com"
        }

        # smtp
        self.smtp = None
        self.validate(address, password)
        self.address = address.encode("utf-8")
        self.password = password.encode("utf-8")
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.ssl = ssl

        # imap
        self.imap = None
        self.imap_server = imap_server
        self.window = window
        self.delimiter = delimiter
        self.identifier_length = identifier_length

        # format: key => [time, lambda]
        self.hook_dict = {}
        # format: number => address
        self.addresses = {}
        self.tracked = []

        self.init_server()

    def validate(self, address, password):
        try:
            assert isinstance(address, basestring)
            assert isinstance(password, basestring)
        except AssertionError:
            raise PySMSException("Please make sure address and password are strings.")

    def init_server(self, imap_mailbox="INBOX"):
        # PySMS at minimum uses smtp server
        try:
            if self.ssl:
                self.smtp = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                self.smtp = smtplib.SMTP(self.smtp_server, self.smtp_port)
                self.smtp.starttls()
            self.smtp.login(self.address, self.password)
        except Exception:
            raise PySMSException("Unable to start smtp server, please check credentials.")

        # if responding functionality is enabled
        if self.imap_server:
            try:
                if self.ssl:
                    self.imap = imaplib.IMAP4_SSL(self.imap_server)
                else:
                    self.imap = imaplib.IMAP4(self.imap_server)
                r, data = self.imap.login(self.address, self.password)
                if r == "OK":
                    r, data = self.imap.select(imap_mailbox)
                    if r != "OK":
                        raise PySMSException("Unable to select mailbox: {0}".format(imap_mailbox))
                else:
                    raise PySMSException("Unable to login to imap server with given credentials.")
            except Exception:
                raise PySMSException("Unable to start imap server, please check address and SSL/TLS settings.")

    def get_smtp_server(self):
        return self.smtp

    def get_imap_server(self):
        return self.imap

    def add_number(self, number, carrier):
        if carrier in self.carriers:
            address = number + self.carriers[carrier]
            self.addresses[number] = address
        else:
            raise PySMSException("Please enter a valid carrier.")

    def del_number(self, number):
        try:
            del self.addresses[number]
        except Exception:
            pass

    def get_current_time(self):
        return time.time()

    def generate_identifier(self):
        ret = ""
        for num in random.sample(range(0, 10), self.identifier_length):
            ret += str(num)
        return ret

    def generate_rfc_query(self):
        ret = ""
        if len(self.tracked) == 1:
            return "FROM {address}".format(address=self.tracked[0])
        for _ in range(len(self.tracked) - 1):
            ret += "OR "
        for track in self.tracked:
            ret += track + " "
        return ret[:-1]

    def check_tracked(self):
        date = (datetime.date.today() - datetime.timedelta(1)).strftime("%d-%b-%Y")
        r, uids = self.imap.uid("search", None,
                                "(SENTSINCE {date} HEADER {query})".format(date=date, query=self.generate_rfc_query()))
        if r == "OK":
            return uids
        return None

    def get_email(self, uid):
        r, email_data = self.imap.uid('fetch', uid, '(RFC822)')
        if r == "OK":
            return email_data
        return None

    def get_emails(self, uids):
        ret = []
        for uid in uids[0].split():
            ret.append(self.get_email(uid))
        return ret

    # TODO: use min heap to speed up runtime if a lot of keys
    def clean_hook_dict(self):
        for key in self.hook_dict:
            if self.get_current_time() - self.hook_dict[key][0] > self.window * 60:
                del self.hook_dict[key]

    def check_email(self, email_data):
        mail = email.message_from_string(email_data[0][1])
        mail_time = email.utils.mktime_tz(email.utils.parsedate_tz(mail["Date"]))
        if self.get_current_time() - mail_time < self.window * 60:
            if mail.get_content_maintype() == "multipart":
                for part in mail.walk():
                    if part.get_content_maintype() != 'multipart' and part.get('Content-Disposition') is not None:
                        response = part.get_payload(decode=True)
                        response = response.split(self.delimiter)
                        if len(response) == 2:
                            key = response[0].strip()
                            value = response[1].strip()
                            self.clean_hook_dict()
                            return self.execute_hook(key, value)
        print "Email is expired"
        return False

    def execute_hook(self, key, value):
        if key in self.hook_dict:
            self.hook_dict[key][2](value)
            self.tracked.remove(self.hook_dict[key][1])
            print "Hook with key: {key} executed".format(key=key)
            return True
        print "Hook with key: {key} not executed".format(key=key)
        return False

    def text(self, msg, with_identifier=False, callback=None, max_tries=5, wait_time=5):
        # pointer iterate through numbers and counter to track attempts for each number
        pointer = 0
        counter = 0

        addresses = self.addresses.values()

        while pointer < len(addresses) and not (counter >= max_tries):
            try:
                # Add call back function if enabled
                if with_identifier:
                    identifier = self.generate_identifier()
                    msg += "\r Reply with identifier {identifier} followed by a \"{delimiter}\"".format(
                        identifier=identifier, delimiter=self.delimiter)
                    # add entry to track identifier to callback function
                    self.hook_dict[identifier] = [self.get_current_time(), addresses[pointer], callback]
                    # add to list of tracked addresses
                    self.tracked.append(addresses[pointer])

                # Send text message through SMS gateway of destination number
                self.smtp.sendmail(self.address, addresses[pointer], msg)
                pointer += 1
                counter = 0
            except Exception as e:
                print "Failed. Number:{0} Msg:{1}".format(addresses[pointer], msg)
                try:
                    self.init_server()
                except PySMSException:
                    print "Init failed."
                    pass
                counter += 1
                time.sleep(wait_time)
                pass
        if counter >= max_tries:
            print "Max tries for text reached."
            return False
        return True


