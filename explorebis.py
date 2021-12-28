"""

Bismuth Explorer Main Module

Version 2.0.1

"""
from gevent.pywsgi import WSGIServer # Imports the WSGIServer
from gevent import monkey; monkey.patch_all()

import json, time, os, sqlite3, requests, datetime, calendar, re, toolsp, bisurl, pyqrcode, logging, socks
from bs4 import BeautifulSoup
from threading import Lock
from decimal import *

from flask import Flask, render_template, session, request, Markup
from flask_socketio import SocketIO, emit, join_room, leave_room, \
	close_room, rooms, disconnect

from logging.handlers import RotatingFileHandler

import configparser as cp

# Read config
config = cp.ConfigParser()
config.readfp(open(r'explorer.ini'))

try:
	alt_curr = config.get('My Explorer', 'altcurrency')
except:
	alt_curr = "GBP"
try:
	ip = config.get('My Explorer', 'nodeip')
except:
	ip = "127.0.0.1"
try:
	port = config.get('My Explorer', 'nodeport')
except:
	port = "5658"
try:
	expssl = config.get('My Explorer', 'ssl')
	if expssl.lower() == "true":
		dossl = True
		try:
			key_path = config.get('My Explorer', 'keypath')
		except:
			dossl = False
		try:
			crt_path = config.get('My Explorer', 'crtpath')
		except:
			dossl = False
	else:
		dossl = False
except:
	dossl = False
try:
	db_root = config.get('My Explorer', 'dbroot')
except:
	db_root = "static/"
try:
	bis_root = config.get('My Explorer', 'bisroot')
except:
	bis_root = "static/ledger.db"
try:
	app_secret = config.get('My Explorer', 'secret')
except:
	app_secret = "3d6f45a5fc12445dbac2f59c3b6c7cb1"	
try:
	mydisplay = int(config.get('My Explorer', 'maxdisplay'))
except:
	mydisplay = 1000
try:
	diff_ch = int(config.get('My Explorer', 'diff_ch'))
except:
	diff_ch = 75
try:
	block_ch = int(config.get('My Explorer', 'block_ch'))
except:
	block_ch = 150
try:
	bis_limit = int(config.get('My Explorer', 'bis_limit'))
except:
	bis_limit = 1
try:
	txlistlim = int(config.get('My Explorer', 'txlistlim'))
except:
	txlistlim = 50
try:
	app_port = int(config.get('My Explorer', 'webport'))
except:
	app_port = 8080
try:
	l_level = config.get('My Explorer', 'logging')
	if l_level.lower() == "warning":
		log_level = logging.WARNING
	if l_level.lower() == "info":
		log_level = logging.INFO
	else:
		log_level = logging.WARNING
except:
	log_level = logging.INFO
	
try:
	dev_get = config.get('My Explorer', 'devmode')
	if dev_get.lower() == "true":
		dev_state = True
		log_level = logging.INFO
	else:
		dev_state = False
except:
	dev_state = True
	
try:
	do_ledger = config.get('My Explorer', 'do_ledger')
	if do_ledger.lower() == "true":
		do_ledger = True
	else:
		do_ledger = False
except:
	do_ledger = True
	
try:
	do_quicksearch = config.get('My Explorer', 'do_quicksearch')
	if do_quicksearch.lower() == "true":
		do_quicksearch = True
	else:
		do_quicksearch = False
except:
	do_quicksearch = True

log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
logFile = 'explorer.log'
my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=5 * 1024 * 1024, backupCount=2, encoding="UTF-8", delay=0)
my_handler.setFormatter(log_formatter)
app_log = logging.getLogger('root')
app_log.setLevel(log_level)
app_log.addHandler(my_handler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(log_formatter)
consoleHandler.setLevel(log_level)
app_log.addHandler(consoleHandler)

topia = "8b447aa5845a2b6900589255b7d811a0a40db06b9133dcf9569cdfa0"
dev_address = "4edadac9093d9326ee4b17f869b14f1a2534f96f9c5d7b48dc9acaed"

vip_mess = ""
do_cmc_once = False

app_log.info("Config and logging done")

if not do_ledger:
	app_log.warning("Ledger Query Disabled")
if not do_quicksearch:
	app_log.warning("Quick Search Disabled")

# Read config

try:
	with open('price_info.txt') as json_file:
		cmc_vals = json.load(json_file)
		app_log.info("Price information loaded")
except:
	cmc_vals = {"BTC": 0.001e-05, "USD": 0.01, "EUR": 0.01, "GBP": 0.01, "CNY": 0.01, "AUD": 0.01}
	app_log.error("price_info.txt has an issue or is missing.... I will try to fix")
	with open('price_info.txt', 'w') as outfile:
		json.dump(cmc_vals, outfile)


# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.

async_mode = "gevent"
app_log.info("Async mode is: {}".format(async_mode))

app = Flask(__name__)
app.config['SECRET_KEY'] = app_secret
socketio = SocketIO(app, async_mode=async_mode)
thread = None
cmc_thread = None
thread_lock = Lock()

db_hyper = False

if os.path.isfile('{}hyper.db'.format(db_root)):
	db_hyper = True
	hyper_root = '{}hyper.db'.format(db_root)
else:
	hyper_root = bis_root # just in case

	
def get_50():

	txlist50 = ''
	arg1 = "50"
	
	try:
		myall = toolsp.get_one_arg("listlim",arg1)
	except:
		myall = [[0,0.0,'','',0,'','','',0,0.0,'',''],]

	for r in myall:
	
		r_from = str(r[2]) # from address
		r_to = str(r[3]) # to address
		a_from = toolsp.get_alias(r_from) # alias from
		if r_from == r_to:
			a_to = a_from # alias of recipient is same a sender
		else:
			a_to = toolsp.get_alias(r_to) # get alias of recipient
			
		if r_from == "Hypernode Payouts" or r_from == "Development Reward":
			r_from_d = r_from
		else:
			r_from_d = "{}....{}".format(r_from[:5],r_from[-5:])
			
		r_to_d = "{}....{}".format(r_to[:5],r_to[-5:])
			
		# build the sender html entry
		if a_from == "":
			a_from = "<span data-toggle='tooltip' title='{0} : Left Click to Copy' onclick='copyToClipboard(&quot;{0}&quot;)'>{1}</span>".format(r_from,r_from_d)
		else:
			a_from = "<ul class='list-unstyled mb-0' data-toggle='tooltip' title='{0} : Left Click to Copy' onclick='copyToClipboard(&quot;{0}&quot;)'><li><b>{1}</b></li><li>{2}</li></ul>".format(r_from,a_from,r_from_d)
		# build the sender html entry
		
		# build the recipient html entry
		if a_to == "":
			a_to = "<span data-toggle='tooltip' title='{0} : Left Click to Copy' onclick='copyToClipboard(&quot;{0}&quot;)'>{1}</span>".format(r_to,r_to_d)
		else:
			a_to = "<ul class='list-unstyled mb-0' data-toggle='tooltip' title='{0} : Left Click to Copy' onclick='copyToClipboard(&quot;{0}&quot;)'><li><b>{1}</b></li><li>{2}</li></ul>".format(r_to,a_to,r_to_d)
		# build the recipient html entry

		det_str = str(r[5][:56])
		det_str = det_str.replace("+","%2B")
		det_str = det_str.replace("<","&lt;")
		det_str = det_str.replace(">","&gt;")
		
		r_sig = str(r[5][:56])
		r_sig_d = "{}....{}".format(r_sig[:5],r_sig[-5:])
		a_sig = "<span data-toggle='tooltip' title='{0} : Left Click to Copy' onclick='copyToClipboard(&quot;{0}&quot;)'>{1}</span>".format(r_sig,r_sig_d)
	
		det_link = "/details?mydetail={}&myaddress={}".format(det_str,str(r[2]))
		
		tx_tm = str(time.strftime("%H:%M:%S, %d/%m/%Y", time.gmtime(float(r[1]))))

		if r[0] < 0:
			txlist50 = txlist50 + '<tr><th scope="row"> {} </th>\n'.format(str(r[0]))
		else:
			txlist50 = txlist50 + '<tr><th scope="row"><a href="{}">{}</a></th>\n'.format(det_link,str(r[0]))
		txlist50 = txlist50 + '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(tx_tm,a_from,a_to,str(float(r[4])),a_sig,str(float(r[8])),str(float(r[9])))

	return txlist50


def cmc_alt(message):

	with open('dump_cmc.txt') as json_file:
		x = json.load(json_file)
		socketio.emit('my_info',{'btc': x['btc'], 'usd': x['usd'], 'fiat': x['fiat'], 'toc': x['toc'], 'mess': message},namespace='/test',broadcast=True)

	try:
		with open('price_info.txt') as json_file:
			cmc_vals = json.load(json_file)
			app_log.info("price_info.txt has been read")
	except:
		cmc_vals = {"BTC": 0.001e-05, "USD": 0.01, "EUR": 0.01, "GBP": 0.01, "CNY": 0.01, "AUD": 0.01}
		app_log.error("price_info.txt has an issue or is missing")
		
	return cmc_vals

		
def get_cmc_info(alt_curr, testmess, mystate, this_dev_state):

	ch = alt_curr.lower()
	c_btc = c_usd = c_cus = '0.0'
	r_cmc_vals = None
	
	if mystate:
	
		try:
			t = "https://api.coingecko.com/api/v3/coins/bismuth?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
			r = requests.get(t)
			x = r.text
			y = json.loads(x)
			
			try:
				c_btc = "{:.8f}".format(float(y['market_data']['current_price']['btc']))
				c_usd = "{:.3f}".format(float(y['market_data']['current_price']['usd']))
				c_cus = "{:.3f}".format(float(y['market_data']['current_price'][ch]))
				app_log.info("Coingecko Price Thread: Updated OK")
				socketio.emit('my_info',{'btc': c_btc, 'usd': c_usd, 'fiat': c_cus, 'toc': alt_curr, 'mess': testmess},namespace='/test',broadcast=True)
				cmc = {'btc': c_btc, 'usd': c_usd, 'fiat': c_cus, 'toc': alt_curr, 'mess': testmess}
				
				with open('dump_cmc.txt', 'w') as outfile:
					json.dump(cmc, outfile)
					
				r_cmc_vals = toolsp.get_cmc_val(y)

				with open('price_info.txt', 'w') as outfile:
					json.dump(r_cmc_vals, outfile)
					
			except:
				app_log.error("Coingecko Price Thread: NOK")
				r_cmc_vals = cmc_alt(testmess)
		
		except requests.exceptions.RequestException as e:
			app_log.error("Coingecko Price Thread: Error {}".format(e))
			r_cmc_vals = cmc_alt(testmess)
	
	else:
	
		r_cmc_vals = cmc_alt(testmess)
		
		if this_dev_state:
			app_log.warning("Coingecko Price Thread: Dev Mode")
		else:
			app_log.info("Coingecko Price Thread: Read from file")

	return r_cmc_vals

		
def get_status_info():

	try:

		st = toolsp.get_no_arg("statusjson")
		
		w_uptime = st['uptime']
		n_up = toolsp.display_time(int(w_uptime),4)
		st['uptime'] = n_up
		socketio.emit('my_status',st,namespace='/test',broadcast=True)
		app_log.info("Status Thread: OK")
	
	except requests.exceptions.RequestException as e:
		w_uptime = "0"
		n_up = toolsp.display_time(int(w_uptime),4)
		st['uptime'] = n_up
		socketio.emit('my_status',st,namespace='/test',broadcast=True)
		app_log.error("Status Thread: Error {}".format(e))

		
def get_block_info(last_block):

	try:
		
		b = toolsp.get_no_arg("blocklastjson")
						
		blheight = b['block_height']
		
		if blheight == last_block:
			app_log.info("Block Thread: Looking For New Block")
			r_block = last_block
		else:
			d = toolsp.get_no_arg("difflastjson")
			time_now = str(time.time())
			bltimestamp = b['timestamp']
			bltm = str(time.strftime("%H:%M:%S on %d/%m/%Y", time.gmtime(float(bltimestamp))))
			rawminer = b['recipient']
			blminer = toolsp.get_alias(rawminer)
			if blminer == "":
				blminer = rawminer
			bldiff = d['difficulty']
			x = toolsp.getcirc()
			socketio.emit('my_latest',{'height': blheight, 'miner': blminer, 'diff': bldiff, 'bltime': bltm, 'btotal': x[0], 'bcirc': x[1]},namespace='/test',broadcast=True)
			app_log.info("Block Thread: New Block Seen {}".format(blheight))
			r_block = blheight
	
	except requests.exceptions.RequestException as e:
		app_log.error("Block Thread: Error {}".format(e))
		r_block = last_block

	return r_block

	
def get_message_info():

	n_ann = False
	c_toast = ""
	
	try:
		
		ann = toolsp.get_no_arg("annget")
		
		if ann != "No announcement":
			n_ann = True
			c_toast = "Dev Team Announcement: {}".format(ann)
			socketio.emit("my_toast", {"c_toast": c_toast}, namespace="/test", broadcast=True)
			app_log.warning(c_toast)
		else:
			app_log.info("No Announcements")
		
	except requests.exceptions.RequestException as e:
		app_log.error("Message Thread: Error {}".format(e))

	with open('message.txt') as json_file:
		m = json.load(json_file)
		my_code = m['secret']
		
		if my_code == app_secret:
			if n_ann:
				this_message = c_toast
			else:
				this_message = m['message']
			app_log.info("Message Checked: Code Good")
		else:
			this_message = ""
			app_log.error("Message Checked: Code Bad")
	
	if dev_state:
		this_message = "DEV MODE | {}".format(this_message)

	return this_message

	
def get_wallet_servers():

	live_x = ""

	try:
	
		x = toolsp.xws()
		
		live_x = ""
		
		for live_ones in x:
			live_x = live_x + "<p>{}</p>".format(live_ones['label'])
		
		w_num = len(x)
		
	except:
		w_num = '0'
		
	socketio.emit('my_w_servers',{'active': str(w_num),'list': live_x},namespace='/test',broadcast=True)
	app_log.info("Wallet Servers Checked")
	
	return x

	
def get_mem_tx_no():

	try:
		mempool = toolsp.get_no_arg("mpgetjson")
		num_tx = str(len(mempool))
		app_log.info("Number of mempool transactions checked")
	except:
		num_tx = "0"
		mempool = []
		app_log.warning("Error checking mempool transactions")
	
	socketio.emit('my_mem',{'mem': num_tx},namespace='/test',broadcast=True)

	if len(mempool) != 0:
		c_toast = "There are {} transactions in local mempool".format(num_tx)
		mem_list = toolsp.mem_html(mempool)
		socketio.emit("update", {"data": mem_list}, namespace="/mem", broadcast=True)
		socketio.emit("my_toast", {"c_toast": c_toast}, namespace="/test", broadcast=True)
		#print(c_toast)
	else:
		b = ""
		c_toast = "Nothing in the local mempool"
		mem_list = toolsp.mem_html(b)
		socketio.emit("update", {"data": mem_list}, namespace="/mem", broadcast=True)
		#socketio.emit("my_toast", {"c_toast": c_toast}, namespace="/test", broadcast=True)
		#print(c_toast)
	
	app_log.info(c_toast)


def main_info():
	# Rename to something better
	# Better timings

	global cmc_vals
	count = 0
	current_block = "1"
	last_block = "0"
	global txlist50

	while True:

		if count % 60 == 0: # check every 10 mins or so
			vip_mess = get_message_info()
			if dev_state:
				cmc_vals = get_cmc_info(alt_curr,vip_mess,False,dev_state)
			else:
				cmc_vals = get_cmc_info(alt_curr,vip_mess,True,dev_state)
			
		else:
			vip_mess = get_message_info()
			cmc_vals = get_cmc_info(alt_curr,vip_mess,False,dev_state)
			
		if count == 0 or count % 12 == 0:
			x = get_wallet_servers()
			
		get_status_info()
		get_mem_tx_no()
		current_block = get_block_info(current_block)
						
		# Refresh tx list
		if current_block != last_block:
			txlist50 = get_50()
			socketio.emit('my_transactions', {'data': txlist50},namespace='/test',broadcast=True)
			app_log.info("Transaction List Refreshed")
			last_block = current_block
		else:
			app_log.info("No new transactions")
	
		if count == 299: # Prevent counting forever
			count = 0
		else:
			count += 1
		
		time.sleep(10)

	
def rich_html(a,c):

	send_back = ""
	
	i = 1
	
	for r in a:
		amt = "{:.8f}".format(r[1])
		if amt == "0.00000000" or amt == "-0.00000000":
			pass
		else:
			rank = str(i)
			address = r[0]
			address_d = "{}....{}".format(address[:5],address[-5:]) # abbreviated address
			alias = r[2]
			bal_bis = "{:.8f}".format(r[1])
			bal_curr = "{:.2f}".format(r[1]*c)
		
		send_back = send_back + '<tr><th scope="row"> {} </th>\n'.format(rank)
		# send_back = send_back + '<td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(address,alias,bal_bis,bal_curr)
		send_back = send_back + '<td><span data-toggle="tooltip" title="{} : Left Click to Copy" onclick="copyToClipboard(&quot;{}&quot;)">{}</span></td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(address,address,address_d,alias,bal_bis,bal_curr)
		i +=1

	return send_back

		
#//////////////////

@app.route('/')
def index():
	return render_template('index.html')

	
@app.route('/realmem')
def mempool():
	return render_template('mempool.html')

	
@app.route('/ledgerquery', methods=['GET'])
def ledger_form():

	if do_ledger:
		starter = ''
		extext = ''
		valtext = ''
		return render_template('ledgerquery.html', starter=starter, extext=extext, valtext=valtext)
	else:
		starter = 'Ledger Query'
		return render_template('generic.html', starter=starter)
	
@app.route('/ledgerquery', methods=['POST'])
def ledger_query():

	mylatest = toolsp.latest()
	
	valtext = ""
	
	a_display = False

	myblock = request.form.get('block')
	xdate = request.form.get('sdate')
	ydate = request.form.get('fdate')
	f_addy = request.form.get('extra')
	
	if not f_addy:
		f_addy = "0"
	
	f_addy = f_addy.strip()
	
	if not f_addy:
		f_addy = "0"
	
	if not toolsp.test(f_addy) == 1:
		f_addy = None

	if xdate:
		l_date = float(calendar.timegm(time.strptime(xdate, '%Y-%m-%d')))
	else:
		l_date = 1493640955.47
		
	if ydate:
		r_date = float(calendar.timegm(time.strptime(ydate, '%Y-%m-%d'))) + 86399
	else:
		r_date = mylatest[4]
	
	#print("Start date: {}".format(l_date))
	#print("End date: {}".format(r_date))

	r_block = myblock
	
	#Nonetype handling - simply replace with "0"
	
	if not myblock:
		myblock = "0"
		
	myblock = myblock.strip()
	
	if "f:" in myblock:
		a_display = True # to display all transactions regardless of limit (undocumented)
		myblock = myblock.split(":")[1]
		#print(myblock)
		#print(a_display)
	
	if "a:" in myblock:
		myblock = toolsp.rev_alias(myblock) # address from alias
	
	my_type = toolsp.test(myblock) # test the data - is it an address, block or error.
	
	if my_type == 3:
		myblock = "0"
		my_type = 2
	
	if my_type == 1: # an address
		
		myxtions = toolsp.refresh(myblock,1) 
		#print(myxtions)
		
		if float(myxtions[0]) or float(myxtions[2]) > 0:
					
			if myxtions[8] == "":
				alias_disp = "None found"
			else:
				alias_disp = myxtions[8]
				
			extext = "<p style='color:#08750A'><b>ALIAS: {}</b></p>\n".format(alias_disp)
			extext = extext + "<p style='color:#08750A'><b>ADDRESS FOUND | Credits: {} | Debits: {} | Rewards: {} |".format(myxtions[0],myxtions[1],myxtions[2])
			extext = extext + " Fees: {} | BALANCE: {}</b></p>".format(myxtions[3],myxtions[4])
			
			#s = socks.socksocket()
			#s.settimeout(10)
			#s.connect((ip, int(port)))
			#connections.send(s, "addlist", 10)
			#connections.send(s, myblock)
			#dump_all = connections.receive(s, 10)
			#s.close()
			
			#temp_all = [d for d in dump_all if l_date <= d[1] <= r_date]
		
			conn = sqlite3.connect(bis_root)
			
			c = conn.cursor()
			c.execute("SELECT * FROM transactions WHERE (timestamp BETWEEN ? AND ?) AND (address = ? OR recipient = ?) ORDER BY abs(block_height) DESC;", (l_date,r_date,str(myblock),str(myblock)))
			temp_all = c.fetchall()

			if str(myblock) == dev_address:
				temp_all = [a for a in temp_all if "Development Reward" not in a[2]]

			if mydisplay == 0 or a_display or l_date > 1493640955.47:
				all = temp_all
				a_display = False
			elif str(myblock) == topia:
				all = temp_all
			else:
				all = temp_all[:mydisplay]

			c.close()
			conn.close()
		
		else:

			dump_all = toolsp.get_one_arg("api_getblockfromhash",myblock)
				
			try:
				hash_block = list(dump_all.keys())[0]
				
				all = toolsp.get_one_arg("blockget",hash_block)
				
				extext = "<center><p style='color:#08750A'><b>Transaction(s) found for the hash you entered</b></p><center>"
				
			except:
				all = None

			if not all:
			
				try:
					
					all = [toolsp.get_two_arg("api_gettransaction",str(myblock),False)]

					#print(all)
					
					extext = "<center><p style='color:#08750A'><b>Transaction found for the txid you entered</b></p><center>"
					
				except:
					all = None
				
				#all = [toolsp.get_the_details(str(myblock),f_addy)] # get transactions for signature
				#print(all)
				
			if not all[0]:				
				extext = "<center><p style='color:#C70039'>Nothing found for the block, address, txid or hash you entered - perhaps no transactions have been made?</p></center>"
			#else:
				#extext = "<center><p style='color:#08750A'><b>Transaction found for the txid you entered</b></p><center>"
	
	if my_type == 2:
	
		if myblock == "0":
		
			all = []
		
		else:
		
			try:
				
				all = toolsp.get_one_arg("blockget",myblock)
				
			except:
				all = None
	
		if not all:
			extext = "<p style='color:#C70039'>Block, address, txid or hash not found. Maybe there have been no transactions, you entered bad data, or you entered nothing at all?</p>\n"
		else:
			pblock = int(myblock) -1
			nblock = int(myblock) +1
			extext = "<form class='form-inline justify-content-center' action='/ledgerquery' method='post'>\n"
			if pblock > 0:
				extext = extext + "<button type='submit' name='block' value='{}' class='btn btn-link btn-sm'><< Previous Block</button>\n".format(str(pblock))
			else:
				extext = extext + "<p></p>\n"		
			extext = extext + "<b> Transactions for block {} </b>\n".format(str(myblock))
			if nblock < (int(mylatest[0]) + 1):
				extext = extext + "<button type='submit' name='block' value='{}' class='btn btn-link btn-sm'>Next Block >></button>\n".format(str(nblock))
			else:
				extext = extext + "<p></p>\n"
			extext = extext + "</form><p></p>\n"
			
	if not all:
		starter = ""
	elif not all[0]:
		starter = ""
	else:
			
		view = []
		i = 0
		for x in all:
				
			if not "http" in str(x[11]):
				if bool(BeautifulSoup(str(x[11]),"html.parser").find()):
					x_open = "HTML NOT SHOWN HERE"
				else:
					x_open = str(x[11][:20])
			else:
				x_open = str(x[11][:20])
			
			det_str = str(x[5][:56])
			det_str = det_str.replace("+","%2B")
			det_str = det_str.replace("<","&lt;")
			det_str = det_str.replace(">","&gt;")
			det_link = "/details?mydetail={}&myaddress={}".format(det_str,str(x[2]))
			tx_address_from = x[2] #short from address
			tx_address_from_d = "{}....{}".format(tx_address_from[:5],tx_address_from[-5:]) #short from address
			tx_address_to = x[3] #short to address
			tx_address_to_d = "{}....{}".format(tx_address_to[:5],tx_address_to[-5:]) #short to address
			tx_id_d = "{}....{}".format(det_str[:5],det_str[-5:]) #short tx_id
			view.append('<tr>')

			if x[0] < 0:
				view.append('<td>{}</td>'.format(str(x[0])))
			else:
				view.append('<td><a href="{}">{}</a></td>'.format(det_link,str(x[0])))
			view.append('<td>{}'.format(str(time.strftime("%Y/%m/%d,%H:%M:%S", time.gmtime(float(x[1]))))))
			#view.append('<td>{}</td>'.format(str(x[2])))
			view.append("<td><a href='search?quicksearch={}'>{}</a></td>".format(str(tx_address_from),str(tx_address_from_d))) #short from address
			#view.append('<td>{}</td>'.format(str(x[3])))
			view.append("<td><a href='search?quicksearch={}'>{}</a></td>".format(str(tx_address_to),str(tx_address_to_d))) #short to address
			view.append('<td>{}</td>'.format(str(x[4])))
			#view.append('<td>{}</td>'.format(str(x[5][:56])))
			view.append('<td><a href="{}">{}</a></td>'.format(det_link,str(tx_id_d)))
			view.append('<td>{}</td>'.format(str(x[8])))
			view.append('<td>{}</td>'.format(str(x[9])))
			view.append('<td>{}</td>'.format(str(x[10])))
			view.append('<td>{}</td>'.format(x_open))
			view.append('</tr>\n')
			i = i+1

		replot = []
		
		replot.append('<table style="font-size: 65%" class="table table-striped table-sm">\n')
		replot.append('<tr>\n')
		replot.append('<td><b>Block</b></td>\n')
		replot.append('<td><b>Timestamp</b></td>\n')
		replot.append('<td><b>From</b></td>\n')
		replot.append('<td><b>To</b></td>\n')
		replot.append('<td><b>Amount</b></td>\n')
		replot.append('<td><b>Transaction ID (txid)</b></td>\n')
		replot.append('<td><b>Fee</b></td>\n')
		replot.append('<td><b>Reward</b></td>\n')
		replot.append('<td><b>Operation</b></td>\n')
		replot.append('<td><b>Message Starts</b></td>\n')
		replot.append('</tr>\n')
		replot = replot + view
		replot.append('</table>\n')
		
		starter = "" + str(''.join(replot))
		valtext = myblock

	return render_template('ledgerquery.html', starter=starter, extext=extext, valtext=valtext)

	
@app.route('/richest', methods=['GET', 'POST'])
def richest_form():

	#print(cmc_vals)
	
	try:
		def_curr = request.form.get('my_curr')
	except:
		def_curr = "BTC"
		
	if not def_curr:
		def_curr = "BTC"
	rawall = toolsp.richones()
	all = []
	conv_curr = cmc_vals["{}".format(def_curr)]
		
	for r in rawall:
		all.append((r[0],float(r[1]),r[2]))
			
	all = sorted(all, key=lambda address: address[1], reverse=True)
	
	view = rich_html(all,conv_curr)
	
	#print(all[0])
	
	return render_template('richlist.html', bislim=str(bis_limit), defcurr=def_curr, richest=view)
	

@app.route('/minerquery', methods=['GET'])
def minerquery():

	try:
		getaddress = request.args.get('myaddy') or ""
	except:
		getaddress = None
		
	if not getaddress:
		addressis = ""
	elif getaddress == "":
		addressis = ""
	else:
		#print("Info requested: " + getaddress)
		m_info = toolsp.bgetvars(getaddress)
		m_alias = toolsp.get_alias(getaddress)
		addressis = "<table style='font-size: 80%' class='table table-sm'>"
		addressis = addressis + "<tr><th scope='row' align='right' bgcolor='#DAF7A6'><b>Address:</b></th><td bgcolor='#D0F7C3'>{}".format(str(m_info[0]))
		if len(m_alias) > 0:
			addressis = addressis + " [<b>{}</b>]</td></tr>".format(m_alias)
		else:
			addressis = addressis + "</td></tr>"
		addressis = addressis + "<tr><th scope='row' align='right' bgcolor='#DAF7A6'><b>Latest Block Found:</b></th><td bgcolor='#D0F7C3'>{}</td></tr>".format(str(m_info[1]))
		addressis = addressis + "<tr><th scope='row' align='right' bgcolor='#DAF7A6'><b>First Block Found:</b></th><td bgcolor='#D0F7C3'>{}</td></tr>".format(str(m_info[2]))
		addressis = addressis + "<tr><th scope='row' align='right' bgcolor='#DAF7A6'><b>Total Blocks Found:</b></th><td bgcolor='#D0F7C3'>{}</td></tr>".format(str(m_info[3]))
		addressis = addressis + "<tr><th scope='row' align='right' bgcolor='#DAF7A6'><b>Total Rewards:</b></th><td bgcolor='#D0F7C3'>{}</td></tr>".format(str(m_info[4]))
		addressis = addressis + "</table>"
		
	all = toolsp.miners()

	send_back = ""

	j = 1
	for x in all:
		thisminer = str(x[0])
		
		if len(thisminer) == 56:
			send_back = send_back + "<tr><th scope='row'> {} </th>\n".format(str(j))
			if len(str(x[5])) > 0:
				send_back = send_back + "<td><a href='/minerquery?myaddy={}'>{}</a></td>".format(thisminer,str(x[5]))
			else:
				send_back = send_back + "<td><a href='/minerquery?myaddy={}'>{}</a></td>".format(thisminer,thisminer)
			send_back = send_back + "<td>{}</td>".format(str(x[3]))
			send_back = send_back + "</tr>"
			j = j+1
	
	return render_template('minerquery.html', miners=send_back, details=addressis)


@app.route('/wservers', methods=['GET'])
def wallet_servers():

	ttl = "Toggle Graph"
	lt = "bar"
	b = [] #labels
	d = [] #values

	x = get_wallet_servers()
	
	wallet_list = ""
		
	for w in x:
		b.append(w['label'])
		d.append(w['clients'])
		wallet_list = wallet_list + "<tr><th scope='row'> {} </th>\n".format(w['label'])
		wallet_list = wallet_list + "<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(w['ip'],w['port'],w['height'],w['version'],w['clients'],w['total_slots'])
		
	legend = "Connected Clients"
	return render_template('wallets.html', wallets=wallet_list, values=d, labels=b, legend=legend, ttl=ttl, lt=lt)
	
	
@app.route('/time_chart')
def b_chart():

	ttl = "Recent Bismuth Blocktime"
	lt = "bar"
	b = []
	d = []
	d_result = toolsp.get_block_time(block_ch)
	#print(d_result)
	
	#d_result = list(reversed(d_result))

	for v in d_result:
		b.append(v[0])
		d.append(round(v[1],8))

	legend = 'Blocktime (seconds)'
	#print(d)

	return render_template('chart.html', values=d, labels=b, legend=legend, ttl=ttl, lt=lt)

	
@app.route('/diff_chart')
def d_chart():

	ttl = "Recent Bismuth Difficulty"
	lt = "line"
	conn = sqlite3.connect(bis_root)
	conn.text_factory = str
	c = conn.cursor()
	c.execute("SELECT * FROM misc ORDER BY block_height DESC LIMIT ?;", (diff_ch,))
	d_result = c.fetchall()
	#print(d_result)
	b = []
	d = []
	d_result = list(reversed(d_result))
	for v in d_result:
		b.append(v[0])
		d.append(float(v[1]))
	
	c.close()
	conn.close()	
	
	legend = 'Difficulty'

	return render_template('chart.html', values=d, labels=b, legend=legend, ttl=ttl, lt=lt)

	
@app.route('/geturl', methods=['GET'])
def url_form():
		
	plotter = []
	
	return render_template('bisurl.html', starter="")

	
@app.route('/geturl', methods=['POST'])
def url_gen():

	is_ok = True
	do_qr = True
	
	try:
		my_add = request.form.get('address')
		my_add = my_add.strip()
		if toolsp.test(my_add) == 3:
			is_ok = False
			my_r = "Bad address entered"
	except:
		my_add = ""
		is_ok = False
		my_r = "No recipient entered"
	
	try:
		my_amount = request.form.get('amount')
	except:
		my_amount = ""
	
	my_op = request.form.get('operation')
	my_mess = request.form.get('message')
	
	try:		
		amdo = Decimal(my_amount)
	except:
		is_ok = False
		my_r = "Invalid Bismuth amount entered"
	
	if not my_op:
		my_op = "0"
	if len(my_op) > 30:
		is_ok = False
		my_r = "Operation text over 30 Characters"
		
	if not my_mess:
		my_mess = ""
		
	if len(my_mess) > 100000:
		is_ok = False
		my_r = "Message text too big"
		
	if len(my_mess) > 250:
		do_qr = False
	
	if is_ok:
		receive_str = bisurl.create_url(app_log, "pay", my_add, my_amount, my_op, my_mess)
		clr_str = '<p style="color:green">'
		if do_qr:
			receive_qr = pyqrcode.create(receive_str)
			receive_qr_png = receive_qr.png('static/qr_{}{}.png'.format(my_add, my_amount), scale=2)
		else:
			receive_qr_png = ''
	else:
		receive_str = my_r
		clr_str = '<p style="color:red">'

	if not is_ok:
		do_qr = False

	print(receive_str)
	
	receive_str = receive_str.replace("<","&lt;")
	receive_str = receive_str.replace(">","&gt;")
		
	plotter = []
	
	plotter.append('<table class="table table-sm">\n')
	plotter.append('<tr><th><center>RESULT</center></th></tr>\n')
	plotter.append('<tr><td align="center"><p></p>{}{}</p><p></p></td></tr>\n'.format(clr_str,receive_str))
	if do_qr:
		plotter.append('<tr><td align="center"><img src="static/qr_{}{}.png" height="175px"></img></td></tr>\n'.format(my_add, my_amount))
	plotter.append('</table>\n')	

	starter = "" + str(''.join(plotter))
	
	return render_template('bisurl.html', starter=starter, my_add=my_add, my_amount=my_amount, my_op=my_op, my_mess=my_mess)


@app.route('/details')
def detailinfo():

	try:
		getdetail = request.args.get('mydetail')
	except:
		getdetail = None
	try:
		get_addy = request.args.get('myaddress')
	except:
		get_addy = None
		
	if toolsp.s_test(get_addy) == False:
		get_addy = None

	if toolsp.d_test(getdetail) == False:
		getdetail = None
		
	if getdetail:
	
		m_detail = toolsp.get_the_details(getdetail,get_addy)
		#print(m_detail)
		
		if m_detail:
		
			d_block = str(m_detail[0])
			d_time = str(time.strftime("%H:%M:%S, %d/%m/%Y", time.gmtime(float(m_detail[1]))))
			#d_time = str(m_detail[1])
			d_from = str(m_detail[2])
			d_to = str(m_detail[3])
			d_amount = str(m_detail[4])
			d_sig = str(m_detail[5])
			d_txid = d_sig[:56]
			d_pub = str(m_detail[6])
			d_hash = str(m_detail[7])
			d_fee = str(m_detail[8])
			d_reward = str(m_detail[9])
			d_operation = str(m_detail[10][:30])
			d_open = str(m_detail[11][:1000])
			
		else:
			
			d_block = "Not Found"
			d_time = ""
			d_from = ""
			d_to = ""
			d_amount = ""
			d_sig = ""
			d_txid = ""
			d_pub = ""
			d_hash = ""
			d_fee = ""
			d_reward = ""
			d_operation = ""
			d_open = ""
			
	else:
	
		d_block = "Not Found"
		d_time = ""
		d_from = ""
		d_to = ""
		d_amount = ""
		d_sig = ""
		d_txid = ""
		d_pub = ""
		d_hash = ""
		d_fee = ""
		d_reward = ""
		d_operation = ""
		d_open = ""
		
	return render_template('detail.html', ablock=d_block, atime=d_time, afrom=d_from, ato=d_to, aamount=d_amount, asig=d_sig, atxid=d_txid, apub=d_pub, ahash=d_hash, afee=d_fee, areward=d_reward, aoperation=d_operation, aopen=d_open)


@app.route('/apihelp')
def apihelp():

	if mydisplay == 0:
		a_text = " "
	else:
		a_text = " ({} record limit)".format(str(mydisplay))
	
	return render_template('apihelp.html', atext=a_text)

	
@app.route('/tokens')
def tokens():

	token_list = toolsp.get_tokens("issued")
	
	tview = []
	
	for t in token_list:

		token_address_tx = t[4] #short token tx address 2021-12-21
		token_address_tx_d = "{}....{}".format(token_address_tx[:5],token_address_tx[-5:]) #short token tx address 2021-12-21

		token_txid = t[5] #short token txid 2021-12-21
		token_txid_d = "{}....{}".format(token_txid[:5],token_txid[-5:]) #short token txid 2021-12-21

		tview.append('<tr>')

		tview.append("<td><b><a href='/tokenquery?token={}'>{}</a><b></td>".format(str(t[2]),str(t[2])))
		#tview.append("<td><a href='tokentxquery?address={}'>{}</a></td>".format(str(t[4]),str(t[4])))
		tview.append("<td><a href='tokentxquery?address={}'>{}</a></td>".format(str(token_address_tx),str(token_address_tx_d)))
		tview.append('<td>{}</td>'.format(str(t[6])))
		tview.append('<td>{}</td>'.format(str(t[0])))
		#tview.append('<td>{}</td>'.format(str(t[5])))
		tview.append("<td><span data-toggle='tooltip' title='{0} : Left Click to Copy' onclick='copyToClipboard(&quot;{0}&quot;)'>{1}</span></td>".format(str(token_txid),str(token_txid_d))) #added short token txid 2021-12-21
		tview.append('<td>{}</td>'.format(str(time.strftime("%d/%m/%Y at %H:%M:%S", time.gmtime(float(t[1]))))))
		tview.append('</tr>\n')
		
	tplot = []
	
	tplot.append('<center><h4>List of Issued Tokens</h4></center>')
	tplot.append('<table style="font-size: 80%" class="table table-striped table-sm">\n')
	tplot.append('<tr><thead>\n')
	tplot.append('<th scope="col">Token Name</th>\n')
	tplot.append('<th scope="col">Issued By</th>\n')
	tplot.append('<th scope="col">Quantity</th>\n')
	tplot.append('<th scope="col">Issue Block</th>\n')
	tplot.append('<th scope="col">TXID</th>\n')
	tplot.append('<th scope="col">Timestamp</th>\n')
	tplot.append('</thead></tr>\n')
	tplot = tplot + tview
	tplot.append('</table>\n')
		
	starter = "" + str(''.join(tplot))
	
	return render_template('tokens.html', starter=starter)


@app.route('/tokenquery')
def tokenquery():

	try:
		this_token = request.args.get('token')
	except:
		this_token = None
		
	if this_token:

		query_list = toolsp.query_token(this_token)
		
	else:
		
		query_list = []
		
	#print(query_list)
	
	tview = []
		
	for t in query_list:
	
		tview.append('<tr>')

		tview.append("<td><b><a href='search?quicksearch={}'>{}</a><b></td>".format(str(t[0]),str(t[0])))
		tview.append('<td>{}</td>'.format(str(time.strftime("%d/%m/%Y at %H:%M:%S", time.gmtime(float(t[1]))))))
		if str(t[3]) == "issued":
			tview.append("<td>{}</td>".format(str(t[3])))
		else:
			tview.append("<td><a href='tokentxquery?address={}'>{}</a></td>".format(str(t[3]),str(t[3])))
		tview.append("<td><a href='tokentxquery?address={}'>{}</a></td>".format(str(t[4]),str(t[4])))
		tview.append('<td>{}</td>'.format(str(t[6])))
		tview.append('<td>{}</td>'.format(str(t[5])))
		tview.append('</tr>\n')
		
	tplot = []
	
	tplot.append('<center><h4>{} - List of Transactions</h4></center>'.format(this_token))
	tplot.append('<table style="font-size: 80%" class="table table-striped table-sm">\n')
	tplot.append('<tr><thead>\n')
	tplot.append('<th scope="col">Block</th>\n')
	tplot.append('<th scope="col">Date</th>\n')
	tplot.append('<th scope="col">From</th>\n')
	tplot.append('<th scope="col">To</th>\n')
	tplot.append('<th scope="col">Amount</th>\n')
	tplot.append('<th scope="col">TXID</th>\n')
	tplot.append('</thead></tr>\n')
	tplot = tplot + tview
	tplot.append('</table>\n')
		
	starter = "" + str(''.join(tplot))
	
	return render_template('tokenquery.html', starter=starter)


@app.route('/tokentxquery')
def tokentxquery():

	try:
		this_tkaddy = request.args.get('address')
	except:
		this_tkaddy = None
		
	if this_tkaddy:

		txquery_list = toolsp.query_tkaddy(this_tkaddy)
		
	else:
		
		txquery_list = []
		
	#print(txquery_list)
	
	tview = []
		
	for t in txquery_list:
	
		if this_tkaddy == str(t[3]):
			txcolor = "#FF0000"
			dude = t[6] * -1
		if this_tkaddy == str(t[4]):
			txcolor = "#008000"
			dude = t[6]
		if this_tkaddy == "issued":
			txcolor = "#008000"
			dude = t[6]
		
		tokentxquery_from = t[3] #short txquery list from
		tokentxquery_from_d = "{}....{}".format(tokentxquery_from[:5],tokentxquery_from[-5:]) #short txquery list from

		tokentxquery_to = t[4] #short txquery list to
		tokentxquery_to_d = "{}....{}".format(tokentxquery_to[:5],tokentxquery_to[-5:]) #short txquery list to
		
		tview.append('<tr>')

		tview.append("<td><b><a href='tokenquery?token={}'>{}</a><b></td>".format(str(t[2]),str(t[2])))
		tview.append("<td><a href='search?quicksearch={}'>{}</a></td>".format(str(t[0]),str(t[0])))
		tview.append('<td>{}</td>'.format(str(time.strftime("%d/%m/%Y at %H:%M:%S", time.gmtime(float(t[1]))))))
		if str(t[3]) == "issued":
			tview.append("<td>{}</td>".format(str(t[3])))
		else:
			tview.append("<td><a href='tokentxquery?address={}'>{}</a></td>".format(str(tokentxquery_from),str(tokentxquery_from_d)))
		tview.append("<td><a href='tokentxquery?address={}'>{}</a></td>".format(str(tokentxquery_to),str(tokentxquery_to_d)))
		tview.append('<td style="color:{}">{}</td>'.format(txcolor,str(dude)))
		tview.append('</tr>\n')
		
	tplot = []
	
	tplot.append('<center><h5>Address: {}</h5></center>'.format(this_tkaddy))
	tplot.append('<table style="font-size: 80%" class="table table-striped table-sm">\n')
	tplot.append('<tr><thead>\n')
	tplot.append('<th scope="col">Token</th>\n')
	tplot.append('<th scope="col">Block</th>\n')
	tplot.append('<th scope="col">Date</th>\n')
	tplot.append('<th scope="col">From</th>\n')
	tplot.append('<th scope="col">To</th>\n')
	tplot.append('<th scope="col">Amount</th>\n')
	tplot.append('</thead></tr>\n')
	tplot = tplot + tview
	tplot.append('</table>\n')
		
	starter = "" + str(''.join(tplot))
	
	return render_template('tokentxquery.html', starter=starter)


@app.route('/search', methods=['GET'])
def search_result():

	myblock = (request.args.get('quicksearch')).strip()
	
	my_type = toolsp.test(myblock)
	
	if do_quicksearch:
	
		if my_type == 1:
		
			myxtions = toolsp.refresh(myblock,1)
			#print(myxtions)
			
			if float(myxtions[0]) or float(myxtions[2]) > 0:
			
				a_block_d = "{}....{}".format(myblock[:5],myblock[-5:])
				
				if not os.path.exists('static/qr_{}.png'.format(myblock)):
					myblock_qr = pyqrcode.create(myblock)
					myblock_qr_png = myblock_qr.png('static/qr_{}.png'.format(myblock), scale=3)
						
				if myxtions[8] == "":
					alias_disp = "None found"
				else:
					alias_disp = myxtions[8]
					
				xplot = []
				
				xplot.append('<div class="card-deck mb-3 text-left">\n')
				xplot.append('<div class="card mb-4 box-shadow">\n')
				xplot.append('<div class="card-header"><h4 class="my-0 font-weight-normal">Information</h4></div>\n')
				xplot.append('<div style="font-size: 80%"  class="card-body">\n')
				xplot.append('<table style="font-size: 100%" class="table table-sm">\n')
				xplot.append('<tr><td>Address: {}</td></tr>\n'.format(myblock))
				xplot.append('<tr><td>Alias: {}</td></tr>\n'.format(alias_disp))
				xplot.append('<tr><td><b>Balance: {}</b></td></tr>\n'.format(myxtions[4]))
				xplot.append('<tr><td>Total Received: {}</td></tr>\n'.format(myxtions[0]))
				xplot.append('<tr><td>Total Spent: {}</td></tr>\n'.format(myxtions[1]))
				xplot.append('<tr><td>Rewards: {}</td></tr>\n'.format(myxtions[2]))
				xplot.append('<tr><td>Fees: {}</td></tr>\n'.format(myxtions[3]))
				xplot.append('</table>\n')
				xplot.append('</div></div>\n')
				xplot.append('<div class="card mb-4 box-shadow">\n')
				xplot.append('<div style="font-size: 100%"  class="card-body">\n')
				xplot.append('<center><p><img src="static/qr_{0}.png" alt="{0}"></img></p>\n'.format(myblock))
				xplot.append('<p>{}</p></center>\n'.format(myblock))
				xplot.append('</div></div>\n')
				
				extext = "" + str(''.join(xplot))
				
				xplot = None
			
				conn = sqlite3.connect(bis_root)
				c = conn.cursor()
				c.execute("SELECT * FROM transactions WHERE address = ? OR recipient = ? ORDER BY timestamp DESC;", (str(myblock),str(myblock)))
				
				temp_all = c.fetchall()

				if mydisplay == 0:
					all = temp_all
				elif str(myblock) == topia:
					all = temp_all
				else:
					all = temp_all[:mydisplay]
				
				c.close()
				conn.close()
			
			else:
			
				dump_all = toolsp.get_one_arg("api_getblockfromhash",myblock)
					
				try:
					hash_block = list(dump_all.keys())[0]
					
					all = toolsp.get_one_arg("blockget",hash_block)
					
					extext = "<center><p style='color:#08750A'><b>Transaction found for the hash you entered</b></p><center>"
				
				except:
					all = None
			
				if not all:
					
					all = [toolsp.get_the_details(str(myblock),"")]
					extext = "<center><p style='color:#08750A'><b>Transaction found for the txid you entered</b></p><center>"
					
				if not all[0]:				
					extext = "<center><p style='color:#C70039'>Nothing found for the block, address, txid or hash you entered - perhaps no transactions have been made?</p></center>"
				#else:
					#extext = "<center><p style='color:#08750A'><b>Transaction found for the txid you entered</b></p><center>"
		
		if my_type == 2:
		
			if myblock == "0":
			
				all = []
			
			else:
			
				try:
					
					all = toolsp.get_one_arg("blockget",myblock)
					
				except:
					all = None

			if not all:
				extext = "<center><p style='color:#C70039'>Block, address, txid or hash not found. Maybe there have been no transactions, you entered bad data, or you entered nothing at all?</p></center>\n"
			else:
				extext = "<center><p style='color:#08750A'><b>Block {} found</b></p></center>\n".format(myblock)
				
		if my_type == 3:
			all = None
			extext = "<center><p style='color:#C70039'>Block, address, txid or hash not found. Maybe there have been no transactions, you entered bad data, or you entered nothing at all?</p></center>\n"
		
		if not all:
			starter = ""
		elif not all[0]:
			starter = ""
		else:
			view = []
			i = 0
			
			for x in all:
							
				if bool(BeautifulSoup(str(x[11]),"html.parser").find()):
					x_open = "HTML NOT SHOWN HERE"
				else:
					x_open = str(x[11][:20])
				
				det_str = str(x[5][:56])
				det_str = det_str.replace("+","%2B")
				det_str = det_str.replace("<","&lt;")
				det_str = det_str.replace(">","&gt;")
				det_link = "/details?mydetail={}&myaddress={}".format(det_str,str(x[2]))
				tx_address_from = x[2] #short from address
				tx_address_from_d = "{}....{}".format(tx_address_from[:5],tx_address_from[-5:]) #short from address
				tx_address_to = x[3] #short to address
				tx_address_to_d = "{}....{}".format(tx_address_to[:5],tx_address_to[-5:]) #short to address
				tx_id_d = "{}....{}".format(det_str[:5],det_str[-5:]) #short tx_id
				view.append('<tr>')

				if x[0] < 0:
					view.append('<td>{}</td>'.format(str(x[0])))
				else:
					view.append('<td><a href="{}">{}</a></td>'.format(det_link,str(x[0])))
				view.append('<td>{}'.format(str(time.strftime("%Y/%m/%d,%H:%M:%S", time.gmtime(float(x[1]))))))
				#view.append('<td>{}</td>'.format(str(x[2])))
				view.append("<td><a href='search?quicksearch={}'>{}</a></td>".format(str(tx_address_from),str(tx_address_from_d))) #short from address
				#view.append('<td>{}</td>'.format(str(x[3])))
				view.append("<td><a href='search?quicksearch={}'>{}</a></td>".format(str(tx_address_to),str(tx_address_to_d))) #short to address
				view.append('<td>{}</td>'.format(str(x[4])))
				#view.append('<td>{}</td>'.format(str(x[5][:56])))
				view.append('<td><a href="{}">{}</a></td>'.format(det_link,str(tx_id_d))) #short tx_id
				view.append('<td>{}</td>'.format(str(x[8])))
				view.append('<td>{}</td>'.format(str(x[9])))
				view.append('<td>{}</td>'.format(str(x[10])))
				view.append('<td>{}</td>'.format(x_open))
				view.append('</tr>\n')
				i = i+1

			replot = []
			
			if mydisplay == 0:
				replot.append('<h4><center>Transaction List</center></h4>')
			else:
				replot.append('<center><h4>Transaction List</h4><sm>({} tx limit)</sm></center>'.format(str(mydisplay)))
			replot.append('<table style="font-size: 65%" class="table table-striped table-sm">\n')
			replot.append('<tr><thead>\n')
			replot.append('<th scope="col">Block</th>\n')
			replot.append('<th scope="col">Timestamp</th>\n')
			replot.append('<th scope="col">From</th>\n')
			replot.append('<th scope="col">To</th>\n')
			replot.append('<th scope="col">Amount</th>\n')
			replot.append('<th scope="col">Transaction ID (txid)</th>\n')
			replot.append('<th scope="col">Fee</th>\n')
			replot.append('<th scope="col">Reward</th>\n')
			replot.append('<th scope="col">Operation</th>\n')
			replot.append('<th scope="col">Message Starts</th>\n')
			replot.append('</thead></tr>\n')
			replot = replot + view
			replot.append('</table>\n')
			
			starter = "" + str(''.join(replot))
		
		return render_template('search.html', starter=starter, extext=extext)
		
	else:
		starter = 'Quick Search'
		return render_template('generic.html', starter=starter)

	
@app.route('/api/<param1>/<param2>', methods=['GET'])
def handler(param1, param2):

	if param1 == "node":
		failed_response = {"error":"request failed","data":"unable to connect to node - try again later"}

		try:
			s = socks.socksocket()
			s.settimeout(10)
			s.connect((ip, int(port)))
		except:
			response = failed_response
			return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
	
		#balance
		if "balanceget:" in param2 or "balancegetjson:" in param2:
			arg1 = (param2.split(":")[1]).strip()
			
			try:
				response = toolsp.get_one_arg("balancegetjson",arg1)	
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		
		#difficulty
		elif param2 == "diffget" or param2 == "diffgetjson":
		
			try:
				response = toolsp.get_no_arg("diffgetjson")
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}				
			
		elif param2 == "difflast" or param2 == "difflastjson":
			
			try:
				response = toolsp.get_no_arg("difflastjson")	
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		
		#mempool
		elif param2 == "mpget" or param2 == "mpgetjson":
			
			try:
				mems = toolsp.get_no_arg("mpgetjson")
				
				if len(mems) == 0:
					response = {"mempool":"empty"}
				else:
					response = mems
				
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			
		#lastblock
		elif param2 == "blocklast" or param2 == "blocklastjson":
			
			try:
				response = toolsp.get_no_arg("blocklastjson")
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			
		#get specific block
		elif "blockget:" in param2 or "blockgetjson:" in param2:
			arg1 = param2.split(":")[1]
			
			try:
				response = toolsp.get_one_arg("blockgetjson",arg1)
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		
		#transactions for an address
		elif "addlistlim:" in param2 or "addlistlimjson:" in param2:
			arg_list = param2.split(":")
			arg1 = arg_list[1]
			arg2 = arg_list[2]
			
			if int(arg2) > txlistlim:
				arg2 = str(txlistlim)
		
			try:
				response = toolsp.get_two_arg("addlistlimjson",arg1,arg2)
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		
		#list of last x transactions
		elif "listlim:" in param2 or "listlimjson:" in param2:
			arg_list = param2.split(":")
			arg1 = arg_list[1]
			
			if int(arg1) > txlistlim:
				arg1 = str(txlistlim)
			
			try:
				response = toolsp.get_one_arg("listlimjson",arg1)
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		
		#get alias for address
		elif "aliasget:" in param2:
			arg1 = param2.split(":")[1]
			
			try:
				add_all = toolsp.get_one_arg("aliasget",arg1)
				add_all = add_all[0][0]
				
				with open('custom.txt', 'r') as infile:
					for line in infile:
						cust = line.split(':')
						if arg1 == cust[1].strip():
							add_all = cust[0].strip()
							#print(r_alias)
			
				response = {"address": arg1,
							"alias": add_all}
					
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			
		#address from alias
		elif "addfromalias:" in param2:

			arg1 = param2.split(":")[1]
			
			try:
				add_all = toolsp.get_one_arg("addfromalias",arg1)
				
				with open('custom.txt', 'r') as infile:
					for line in infile:
						cust = line.split(':')
						if arg1 == cust[0].strip():
							add_all = cust[1].strip()

				response = {"alias": arg1,
							"address": add_all}
					
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:	
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			
		#validate an address
		elif "addvalidate:" in param2:

			arg1 = param2.split(":")[1]
			
			try:
				val_result = toolsp.get_one_arg("addvalidate",arg1)
				
				response = {"address": arg1,
							"status": val_result}
					
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		
		#get node peers
		elif param2 == "peersget":
		
			try:			
				response = toolsp.get_no_arg("peersget")
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			
		#get node status
		elif param2 == "statusget" or param2 == "statusjson":

			try:
				response = toolsp.get_no_arg("statusjson")
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}

		#get network announcement
		elif param2 == "annget":
			
			try:
				response = toolsp.get_no_arg("annget")
				return json.dumps(response), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			except:
				response = failed_response			
				return json.dumps(response), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			
		else:
			r = "invalid request"
			e = {"error":r}
			return json.dumps(e), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			
	elif param1 == "info":
		
		if param2 == "coinsupply":
			x = toolsp.getcirc()
			return json.dumps({'circulating':str(x[1]),'total':str(x[0])}), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		if param2 == "totalsupply":
			x = toolsp.getcirc()
			return json.dumps(str(x[0])).strip('"'), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		if param2 == "wservers":
			w = toolsp.xws()
			return json.dumps(w), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		if "richlist" in param2:
			rawall = toolsp.richones()
			x = toolsp.getcirc()
			
			supp = float(x[0])
			
			all = []
			
			for r in rawall:
				all.append((r[0],float(r[1]),r[2]))
					
			all = sorted(all, key=lambda address: address[1], reverse=True)
			all = all[:1000]
			
			y = []
			count = 1
			
			for i in all:
				i_percent = (float(i[1])/supp)*100
				y.append({"rank":str(count),"address":str(i[0]),"balance":str(i[1]),"alias":str(i[2]),"percent":str(i_percent)})
				count =+1
			
			return json.dumps(y), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			
	elif param1 == "getall":
	
		if do_ledger:
			getaddress = str(param2)
			a_display = False
			if "f:" in getaddress:
				a_display = True
				getaddress = getaddress.split(":")[1]
				#print(getaddress)
				#print(a_display)
				
			if "a:" in getaddress:
				getaddress = toolsp.rev_alias(getaddress)
				
			if not getaddress or not toolsp.s_test(getaddress):
				r = "invalid data entered"
				e = {"error":r}
				return json.dumps(e), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			else:
				all = []
				conn = sqlite3.connect(bis_root)
				c = conn.cursor()
				if mydisplay == 0 or a_display:
					c.execute("SELECT * FROM transactions WHERE address = ? OR recipient = ? ORDER BY abs(block_height) DESC;", (getaddress,getaddress))
				else:
					c.execute("SELECT * FROM transactions WHERE address = ? OR recipient = ? ORDER BY abs(block_height) DESC LIMIT ?;", (getaddress,getaddress,str(mydisplay)))
				all = c.fetchall()
				c.close()
				conn.close()
				if not all:
					r = "address does not exist or invalid address"
					e = {"error":r}
					return json.dumps(e), 404, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
				else:
					y = []
					#y.append({"address":getaddress,"limit":"{} records".format(str(mydisplay))})
					
					for b in all:
						y.append({"block":str(b[0]),"timestamp":str(b[1]),"from":str(b[2]),"to":str(b[3]),"amount":str(b[4]),"txid":str(b[5][:56]),"fee":str(b[8]),"reward":str(b[9]),"operation":str(b[10]),"openfield":str(b[11])})
					
					return json.dumps(y), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		else:
			r = "function not available"
			e = {"error":r}
			return json.dumps(e), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}

	elif param1 == "block":
		myblock = str(param2)
		if not myblock or not myblock.isalnum():
			r = "invalid data entered"
			e = {"error":r}
			return json.dumps(e), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		else:
			all = []
			
			try:
				
				all = toolsp.get_one_arg("blockget",myblock)
				
			except:
				all = None

			if not all:
				r = "block does not exist or invalid block"
				e = {"error":r}
				return json.dumps(e), 404, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
			else:
				y = []
				
				for b in all:
					y.append({"block":str(b[0]),"timestamp":str(b[1]),"from":str(b[2]),"to":str(b[3]),"amount":str(b[4]),"txid":str(b[5][:56]),"fee":str(b[8]),"reward":str(b[9]),"operation":str(b[10]),"openfield":str(b[11])})
				
				return json.dumps(y), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
				
	elif param1 == "txid":
			gettxid = str(param2)
			
			get_txid = gettxid.replace(".","/")
		
			m_stuff = "{}".format(str(get_txid))
			
			if toolsp.d_test(get_txid) == False:
			
				r = "txid does not appear to exist or invalid data"
				e = {"error":r}
				return json.dumps(e), 404, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}

			else:
			
				m_detail = toolsp.get_the_details(m_stuff,None)
		
				
				if m_detail:
				
					y = []
					y.append({"block":str(m_detail[0]),"timestamp":str(m_detail[1]),"from":str(m_detail[2]),"to":str(m_detail[3]),"amount":str(m_detail[4]),"signature":str(m_detail[5]),"txid":str(m_detail[5][:56]),"pubkey":str(m_detail[6]),"hash":str(m_detail[7]),"fee":str(m_detail[8]),"reward":str(m_detail[9]),"operation":str(m_detail[10]),"openfield":str(m_detail[11])})
					
					return json.dumps(y), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
					
				else:
					
					r = "txid does not appear to exist or invalid data"
					e = {"error":r}
					return json.dumps(e), 404, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
				
	elif param1 == "txidadd":
			gettxid = str(param2)
		
			tx_add_info = gettxid.split(":")
			get_txid = tx_add_info[0]
			get_add_from = tx_add_info[1]
						
			get_txid = get_txid.replace(".","/")
		
			m_stuff = "{}".format(str(get_txid))
			
			if toolsp.d_test(get_txid) == False:
			
				r = "txid does not appear to exist or invalid data"
				e = {"error":r}
				return json.dumps(e), 404, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}

			else:
			
				m_detail = toolsp.get_the_details(m_stuff,get_add_from)
					
				if m_detail:
				
					y = []
					y.append({"block":str(m_detail[0]),"timestamp":str(m_detail[1]),"from":str(m_detail[2]),"to":str(m_detail[3]),"amount":str(m_detail[4]),"signature":str(m_detail[5]),"txid":str(m_detail[5][:56]),"pubkey":str(m_detail[6]),"hash":str(m_detail[7]),"fee":str(m_detail[8]),"reward":str(m_detail[9]),"operation":str(m_detail[10]),"openfield":str(m_detail[11])})
					
					return json.dumps(y), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
					
				else:
					
					r = "txid does not appear to exist or invalid data"
					e = {"error":r}
					return json.dumps(e), 404, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}

	elif param1 == "richlist":
		rich_num = str(param2)
		nog = True
		ra = toolsp.richones()
		rag =[(r[0],float(r[1]),r[2]) for r in ra]
		rag = sorted(rag, key=lambda address: address[1], reverse=True)
		
		if rich_num.isdigit():
			rich_num = int(rich_num)
			if rich_num > len(rag):
				rich_num = len(rag)
		elif rich_num == "all":
			rich_num = len(rag)
		else:
			nog = False
		
		nt = range(rich_num)
			
		if nog:
			y = [{"rank":str(g+1),"address":str(rag[g][0]),"alias":str(rag[g][2]),"balance":('%.8f' % rag[g][1])} for g in nt]
			return json.dumps(y), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		else:
			r = "invalid request"
			e = {"error":r}
			return json.dumps(e), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}

	elif param1 == "miners":
		miner_num = str(param2)
		mog = True
		ma = toolsp.miners()
		
		if miner_num.isdigit():
			miner_num = int(miner_num)
			if miner_num > len(ma):
				miner_num = len(ma)
		elif miner_num == "all":
			miner_num = len(ma)
		else:
			mog = False
		
		nt = range(miner_num)
			
		if mog:
			y = [{"rank":str(g+1),"address":str(ma[g][0]),"blocks":str(ma[g][3]),"rewards":str(ma[g][4]),"alias":str(ma[g][5])} for g in nt]
			return json.dumps(y), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		else:
			r = "invalid request"
			e = {"error":r}
			return json.dumps(e), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}

	elif param1 == "aminer":
		#getaddress = str(param2)
		temp_addy = str(param2)
		if "a:" in temp_addy:
			getaddress = toolsp.rev_alias(temp_addy)
		else:
			getaddress = temp_addy
		if toolsp.s_test(getaddress):
			m_info = toolsp.bgetvars(getaddress)
			#print(m_info)
			if m_info:
				x = {'address':str(m_info[0]),'alias':str(m_info[5]),'latestblock':str(m_info[1]),'firstblock':str(m_info[2]),'totalblocks':str(m_info[3]),'rewards':str(m_info[4])}
				return json.dumps(x), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}				
			else:
				r = "{} is not a miner....".format(getaddress)
				e = {"error":r}
				return json.dumps(e), 404, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		else:
			r = "invalid address"
			e = {"error":r}
			return json.dumps(e), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}

	elif param1 == "diffhist":
		diff_num = str(param2)
		dog = False
		
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		c = conn.cursor()
				
		if diff_num.isdigit():
			if int(diff_num) > 10:
				dog = True
				c.execute("SELECT * FROM misc ORDER BY block_height DESC LIMIT ?;", (diff_num,))
				d_result = c.fetchall()
				y = []
				d_result = list(reversed(d_result))
				
				for v in d_result:
					b = str(v[0])
					d = {b:v[1],}
					y.append(d)
				
				c.close()
				conn.close()

		if dog:
			#y = [b,d]
			return json.dumps(y), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		else:
			r = "invalid request value must be more than 10"
			e = {"error":r}
			return json.dumps(e), 404, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}			
		
	else:
		r = "invalid request"
		e = {"error":r}
		return json.dumps(e), 400, {'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}
		
	s.close()


@socketio.on('my_event', namespace='/test')
def test_message(message):
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': message['data'], 'count': session['receive_count']})


@socketio.on('my_connect', namespace='/test')
def test_con_status(message):
	emit('my_con_status',{'data': message['data']})


@socketio.on('my_broadcast_event', namespace='/test')
def test_broadcast_message(message):
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': message['data'], 'count': session['receive_count']},
		 broadcast=True)


@socketio.on('join', namespace='/test')
def join(message):
	join_room(message['room'])
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': 'In rooms: ' + ', '.join(rooms()),
		  'count': session['receive_count']})


@socketio.on('leave', namespace='/test')
def leave(message):
	leave_room(message['room'])
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': 'In rooms: ' + ', '.join(rooms()),
		  'count': session['receive_count']})


@socketio.on('close_room', namespace='/test')
def close(message):
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response', {'data': 'Room ' + message['room'] + ' is closing.',
						 'count': session['receive_count']},
		 room=message['room'])
	close_room(message['room'])


@socketio.on('my_room_event', namespace='/test')
def send_room_message(message):
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': message['data'], 'count': session['receive_count']},
		 room=message['room'])


@socketio.on('disconnect_request', namespace='/test')
def disconnect_request():
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': 'Disconnected!', 'count': session['receive_count']})
	disconnect()


@socketio.on('my_ping', namespace='/test')
def ping_pong():
	emit('my_pong')


@socketio.on('connect', namespace='/test')
def test_connect():
	global cmc_thread
	get_status_info()

	with thread_lock:
		if cmc_thread is None:
			cmc_thread = socketio.start_background_task(target=main_info)
			app_log.info("New Connection, New Thread {}".format(request.sid))
		else:
			with open('dump_cmc.txt') as json_file:
				x = json.load(json_file)
				emit('my_info',{'btc': x['btc'], 'usd': x['usd'], 'fiat': x['fiat'], 'toc': x['toc'], 'mess': x['mess']},namespace='/test',broadcast=True)
			app_log.info("New Connection {}".format(request.sid))
			x = get_wallet_servers()
			
			try:
				emit('my_transactions', {'data': txlist50},namespace='/test')
			except:
				tx_new_con = get_50()
				emit('my_transactions', {'data': tx_new_con},namespace='/test')


@socketio.on('disconnect', namespace='/test')
def test_disconnect():
	app_log.info('Home Page client disconnected {}'.format(request.sid))

	
@socketio.on('disconnect', namespace='/mem')
def mem_disconnect():
	app_log.info('Mempool client disconnected {}'.format(request.sid))

	
@socketio.on('connect', namespace='/mem')
def mem_connect():
	"""
	connect
	"""
	get_mem_tx_no()
	app_log.info('Mempool client connected {}'.format(request.sid))
	
	
if __name__ == '__main__':

	LISTEN = ('0.0.0.0',app_port)
	
	if dossl:
		http_server = WSGIServer( LISTEN, app, keyfile=key_path, certfile=crt_path, log = None )
	else:
		http_server = WSGIServer( LISTEN, app, log = None )
		
	http_server.serve_forever()
# ends
