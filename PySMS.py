import smtplib, time

class PySMSException():
	def __init__(self, value):
		self.value = value
	
	def __str__(self):
		return repr(self.value)

class PySMS():
	def __init__(self, email, password, smtp_server, smtp_port, ssl=False):
		self.carriers = {"att":"@mms.att.net", "tmobile":"@tmomail.net", "verizon":"@vtext.com", "sprint":"@page.nextel.com"}
		
		self.validate(email, password)
		self.email = email
		self.password = password
		self.smtp_server = smtp_server
		self.smtp_port = smtp_port
		self.ssl = ssl

		self.server = None
		self.init_server()

		self.addresses = []

	def validate(self, email, password):
		try:
			assert isinstance(email, basestring)
			assert isinstance(password, basestring)
		except AssertionError:
			raise PySMSException("Please make sure email and password are strings")

	def init_server(self):
		try:
			if self.ssl:
				self.server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
			else:
				self.server = smtplib.SMTP(self.smtp_server, self.smtp_port)
				self.server.starttls()
			self.server.login(self.email.encode('utf-8'), self.password.encode('utf-8'))
		except Exception:
			raise PySMSException("Unable to start server, please check credentials")

	def get_server(self):
		return self.server

	def add_number(self, phone_num, carrier):
		if carrier in self.carriers:
			address = phone_num + self.carriers[carrier]
			self.addresses.append(address)
		else:
			raise PySMSException("Please enter a valid carrier.")

	def del_number(self, phone_num):
		try:
			self.addresses.remove(phone_num)
		except Exception:
			pass

	def text(self, msg, max_tries=5):
		pointer = 0
		counter = 0

		while pointer < len(self.addresses) and not (counter >= max_tries):
			try:
				# Send text message through SMS gateway of destination number
				self.server.sendmail(self.email, self.addresses[pointer], msg)
				pointer += 1
				counter = 0
			except Exception as e:
				print e
				print "Failed. Number:{0} Msg:{1}".format(self.addresses[pointer], msg)
				try:
					self.init_server()
				except PySMSException:
					print "Init failed."
					pass
				counter += 1
				time.sleep(5)
				pass
		if counter >= max_tries:
			print "Max tries for text reached."
			return False
		return True


