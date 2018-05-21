# PySMS
Simple Python API that that allows you to send texts via SMTP with a best effort approach and process replies via IMAP

### Motivation
I could afford shared hosting that gave me unlimited email accounts but I couldn't (didn't want to pay for) a SMS API such as Twilio so I decided to write my own given that this email to texting functionality exists already.

### Prerequisites
The only Python Libraries needed are included in the standard Python libraries but incase you don't have them you can install them with the following command.

`pip install smtplib imaplib email datetime time random inspect logging`


### Getting Started
Import PySMS into your Python file by including the following line 

`import PySMS`

### Usage
Not sure what IMAP and SMTP servers are? Read [here](https://github.com/clayshieh/PySMS/issues/3)

For only texting capability, initialize the client with your address, password, smtp_server, smtp_port and an optional ssl flag.

`ps = PySMS.PySMS(address="text@example.com", password="password", smtp_server="smtp.example.com", smtp_port="465", ssl=True)`

To enable the texting callback capability, you also have to initialize the client with your imap_server.
`ps = PySMS.PySMS(address="text@example.com", password="password", smtp_server="smtp.example.com", smtp_port="465", imap_server="imap.example.com", ssl=True)`

Add numbers with corresponding carriers that you want the client to text whenever you call the `text()` method using the `add_number()` method.

`ps.add_number("5551231234", "att")`

Whenever you want to send a text with no callback functionality to all added numbers call the `text()` method

`ps.text("This is a text!")`

If you want to text just one number, set the optional number argument in the `text()` method

`ps.text("This is an individual text", number="5551231234")`

You can also add a callback to the text by setting the `callback_function` argument to your function. **When the callback function is executed, the code expects and checks that the callback function  accepts two arguments the first being the address of the associated hook and the second being the value of the reply** See example below.

```
def test_callback(address, value):
	print "Callback function triggered by {address}!".format(address=address)
	print "Value was: " + value

ps.text("This is a text with a callback function!", callback=test_callback)
```

The receiver of the text will get the following message:

```
This is a text with a callback function!Reply with identifier 1234 followed by a ":"
```

To which they can reply:

```
1234: Amazing
```

The callback function once the `check_tracked()` function finds the correct email will then print:

```
Callback function triggered by 5551231234@mms.att.net!
Value was: Amazing
```

Additional settings such as the window time, delimiter and identifier length can be configured when you initialize the server object by setting the optional arguments `window`, `delimiter` and `identifier_length` repsectively.

### Acknowledgements
Referenced https://www.digitaltrends.com/mobile/how-to-send-e-mail-to-sms-text/ for emails for each US carrier in `self.carriers`

Referenced https://yuji.wordpress.com/2011/06/22/python-imaplib-imap-example-with-gmail/ for how to process email_data coming back from imaplib in `check_email()`

### Contributing
Pull requests and contributions are welcomed!

### Support
For any questions or concerns, please create an issue or contact me.
