Chillispot and freeradius scripts
=================================

by Michele Beltrame
License: GPL v2

Features:

* Modified hotspotlogin.cgi with changed layout and which does not require
an SSL connection (it was a PITA for users with Explorer 7 if the server
didn't have a CA-approved certificate).

* An admin web script which allows to create users assigning a connection
interval: it then computes a random username and password which wifi
roamers will use for login.

* A cron script which reaps users which access is expired, and logs them
off if they're still logged on.

