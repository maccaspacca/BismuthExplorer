# Bismuth Explorer Installation

Requirements
============

1. A running full Bismuth node
2. Python 3.6 or better
3. Additional python modules as noted in requirements.txt

Steps
=====

If you are migrating from version 1.0 you no longer need the kafka server instance or the '601_exp_send_block' plugin.
The plugin folder '601_exp_send_block' should be removed.
If this was the only plugin being used the plugin folder can be removed or renamed

1. Copy the folder 'explorer' to a suitable folder on your server
2. Edit the file 'explorer.ini' with settings for your installation (see below)
3. Adjust your edge firewall settings to route your external port to the internal port configured in 'explorer.ini'

Starting
========

1. Start your node and let it fully synchronise.
2. Run 'toolsdb.py'. On first run this will create a new database called tools.db and fill it with information. Important: let this fully synchronise.
3. Run 'explorebis.py' this will run the Bismuth Explorer itself. If all is well you should now have your explorer instance up and running and ready for access.

explorer.ini
============

altcurrency = The display currency on the front page of the explorer and richlist options are: EUR,GBP,USD,CNY,AUD

nodeport = Port of your Bismuth node, this is usually 5658

nodeip = IP of your Bismuth node

ssl = set this to true if you are using ssl or false if not

keypath = path to your ssl certificate key file

crtpath = path to your ssl certificate file (crt file)

dbroot = path to your Bismuth/static folder

bisroot = path to your ledger.db file

hyperroot = path to your hyper.db file

maxdisplay = The maximum number of transactions to be displayed by a ledger query. Usual setting is 1000

diff_ch = Number of blocks for difficulty history chart. Usual setting is 75

block_ch = Number of blocks for block time chart. Usual setting is 150

bis_limit = Richlist minimum Bismuth balance. Addresses below this will not be displayed. Usual setting is 1

txlistlim = Maximum number of transactions to be returned by the api command addlistlim or addlistlimjson. The usual setting is 50

secret = A random string used for the Flask SECRET_KEY property. You can replace this with your own

webport = Port of the Tornado web server

logging = logging level options used are: info, warning

devmode = normally set to false

message.txt
===========

Edit the fields as follows

secret = the string in this field should match the secret in explorer.ini

message = the string in this field will be displayed in the middle information field on the explorer home page. Normally this is left blank
If there is a network message from the node this will displayed in its place.






