# Bismuth Explorer Installation

Requirements
============

1. A running full Bismuth node
2. A Kafka server instance
3. Python 3.6 or better
4. Additional python modules as noted in requirements.txt

Steps
=====

1. If you don't have one already create a folder called 'plugins' in your Bismuth installation folder
2. Copy the folder '601_exp_send_block' and its contents into the 'plugins' folder
3. Edit the file '601_plugin.ini' with settings for your installation (see below)
4. Copy the file '601_plugin.ini' to the root of your Bismuth installation folder
5. Copy the folder 'explorer' to a suitable folder on your server
6. Edit the file 'explorer.ini' with settings for your installation (see below)
7. Adjust your edge firewall settings to route your external port to the internal port configured in 'explorer.ini'

Starting
========

1. Start your node and let it fully synchronise. This will start producing block, status and other information and will send it to your Kafka server
2. Run 'toolsdb.py'. On first run this will create a new database called tools.db and fill it with information. Let this fully synchronise.
3. Run 'explorebis.py' this will run the Bismuth Explorer itself. If all is well you should now have your explorer instance up and running and ready for access.

601_plugin.ini
==============

This file contains the settings for the Bismuth Plugin for the explorer. This part of the explorer uses the Plugins feature of the Bismuth node.
It's job is to capture block, status and other information and send this to your kafka server.
The explorer itself picks up this information and sends it to attached clients using socket-io

kafkahost = IP address of the kafka server
kafkaport = Port of the kafka server
altcurrency = The display currency on the front page of the explorer options are: EUR,GBP,USD,CNY,AUD
nodeport = Port of your Bismuth node, this is usually 5658
nodeip = IP of your Bismuth node
doprice = Enable or disable price checking. Options are true or false. If you set this to false then no price information will appear on the explorer front page.

explorer.ini
============

kafkahost = IP address of the kafka server
kafkaport = Port of the kafka server
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
secret = random string used for the Flask SECRET_KEY property
webport = Port of the Tornado web server
