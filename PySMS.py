import smtplib
import imaplib
import email
import datetime
import time
import random
import inspect


class PySMSException:
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return repr(self.value)


class PySMS:
    def __init__(self, address, password, smtp_server, smtp_port, imap_server=None, window=5, delimiter=":",
                 identifier_length=4, ssl=False):
        # Referenced from https://www.digitaltrends.com/mobile/how-to-send-e-mail-to-sms-text/
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
        self.window = window
        self.delimiter = delimiter
        self.identifier_length = identifier_length

        # Format: key => [time, address, lambda]
        self.hook_dict = {}
        # Format: number => address
        self.addresses = {}
        # Format: address => [uids]
        self.ignore_dict = {}
        self.ignore_set = set()
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
                    r, data = self.imap.select(imap_mailbox)
                    if r != "OK":
                        raise PySMSException("Unable to select mailbox: {0}".format(imap_mailbox))
                else:
                    raise PySMSException("Unable to login to IMAP server with given credentials.")
            except imaplib.IMAP4.error:
                raise PySMSException("Unable to start IMAP server, please check address and SSL/TLS settings.")

    def get_smtp_server(self):
        return self.smtp

    def get_imap_server(self):
        return self.imap

    def get_hook_dict(self):
        return self.hook_dict

    def get_hook_address(self, key):
        return self.hook_dict[key][1]

    def check_callback_requirements(self, callback_function):
        if self.imap:
            if callable(callback_function):
                if len(inspect.getargspec(callback_function).args) == 2:
                    return
                else:
                    raise PySMSException("Callback function does not have the correct number of arguments.")
            else:
                raise PySMSException("Callback function is not callable.")
        else:
            raise PySMSException("IMAP settings not configured or valid.")

    def add_number(self, number, carrier):
        if carrier in self.carriers:
            address = number + self.carriers[carrier]
            self.addresses[number] = address
        else:
            raise PySMSException("Please enter a valid carrier.")

    def del_number(self, number):
        if number in self.addresses:
            del self.addresses[number]

    def add_hook(self, identifier, address, callback_function):
        self.hook_dict[identifier] = [self.get_current_time(), address, callback_function]
        if address not in self.tracked:
            self.tracked.append(address)

    def remove_hook(self, key):
        if key in self.hook_dict:
            self.tracked.remove(self.hook_dict[key][1])
            del self.hook_dict[key]

    def add_ignore(self, mail, uid):
        ignore_list = [uid]
        if mail["From"] in self.ignore_dict:
            ignore_list += self.ignore_dict[mail["From"]]
        self.ignore_dict[mail["From"]] = ignore_list
        self.ignore_set.add(uid)

    def del_ignore(self, address):
        for uid in self.ignore_dict[address]:
            self.ignore_set.remove(uid)
        del self.ignore_dict[address]

    def get_current_time(self):
        return time.time()

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
                    print "No new emails to check (either ignored or no new mail)"
        else:
            print "No addresses being tracked"
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
                self.remove_hook(key)

    # Referenced from: https://yuji.wordpress.com/2011/06/22/python-imaplib-imap-example-with-gmail/
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
                            return self.execute_hook(key, value)
        # Clean_hook_dict will take care of this later
        print "Email with uid: {uid} is expired, ignoring in next check".format(uid=uid)
        # Add uid to ignore if uid is expired so it knows not to request it next cycle
        self.add_ignore(mail, uid)

        return False

    def execute_hook(self, key, value):
        if key in self.hook_dict:
            success = True
            try:
                self.hook_dict[key][2](self.hook_dict[key][1], value)
            except Exception:
                success = False
            if success:
                print "Hook with key: {key} for {address} executed".format(key=key, address=self.hook_dict[key][1])
            else:
                print "Hook with key: {key} for {address} was not executed or failed".format(
                    key=key, address=self.hook_dict[key][1])
            # Remove from ignore and remove from hook_dict
            self.del_ignore(self.hook_dict[key][1])
            self.remove_hook(key)
        else:
            print "Hook with key: {key} not valid".format(key=key)

    def text(self, msg, address=None, callback=False, callback_function=None, max_tries=5, wait_time=5):
        # Pointer iterate through addresses and counter to track attempts for each address
        pointer = 0
        counter = 0

        if address:
            addresses = [address]
        else:
            addresses = self.addresses.values()
        tmp_msg = msg

        while pointer < len(addresses) and not (counter >= max_tries):
            try:
                # Add call back function if enabled
                if callback:
                    # Validate callback function
                    self.check_callback_requirements(callback_function)
                    identifier = self.generate_identifier()
                    tmp_msg += "\rReply with identifier {identifier} followed by a \"{delimiter}\"".format(
                        identifier=identifier, delimiter=self.delimiter)
                    self.add_hook(identifier, addresses[pointer], callback_function)

                # Send text message through SMS gateway of destination address
                self.smtp.sendmail(self.address, addresses[pointer], tmp_msg)
                pointer += 1
                counter = 0
                # Reset msg back to original
                tmp_msg = msg
            except smtplib.SMTPException:
                print "Failed. Address:{0} Msg:{1}".format(addresses[pointer], msg)
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

