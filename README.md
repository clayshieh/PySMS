# PySMS
Simple Python API that that allows you to send texts via SMTP servers with a best effort approach

### Prerequisites
The only non standard Python Library you need is smtplib which you can install by running

`pip install smtplib`


### Getting Started
Import PySMS into your Python file by including the following line 

`import PySMS`

### Usage
Initialize the client with your email, password, smtp_server, smtp_port and an optional ssl flag.

`ps = PySMS(email="text@example.com", password="password", smtp_server="smtp.example.com", smtp_port="465", ssl=True)`

Add numbers with corresponding carriers that you want the client to text whenever you call the `.text()` method.

`ps.add_number("5551231234", "att")`

Whenever you want to send a message to said numbers call the `.text()` method

`ps.text("This is a text!")`

### Contributing
Pull requests and contributions are welcomed!

### Support
For any questions or concerns, please create an issue or contact me.
