"""

Bismuth Explorer Proceedures Module

Version 1.00

"""

import sqlite3, time, json, requests, re, socks, connections

import configparser as cp
from bs4 import BeautifulSoup

# Read config
config = cp.ConfigParser()
config.readfp(open(r'explorer.ini'))

try:
	db_root = config.get('My Explorer', 'dbroot')
except:
	db_root = "static/"
try:
	bis_root = config.get('My Explorer', 'bisroot')
except:
	bis_root = "static/ledger.db"
try:
	hyper_root = config.get('My Explorer', 'hyperroot')
except:
	hyper_root = "static/hyper.db"
try:
	ip = config.get('My Explorer', 'nodeip')
except:
	ip = "127.0.0.1"
try:
	port = config.get('My Explorer', 'nodeport')
except:
	port = "5658"

db_hyper = True

def getcirc():

	conn = sqlite3.connect(bis_root)
	conn.text_factory = str
	c = conn.cursor()
	
	c.execute("SELECT sum(reward) FROM transactions;")

	allcirc = c.fetchone()[0]
	
	c.execute("SELECT sum(amount) FROM transactions WHERE address = 'Development Reward';")
	
	alldev = c.fetchone()[0]

	c.execute("SELECT sum(amount) FROM transactions WHERE address = 'Hyperblock';")
	
	allhyp = c.fetchone()[0]
	
	c.execute("SELECT sum(amount) FROM transactions WHERE address = 'Hypernode Payouts';")
	
	allmno = c.fetchone()[0]
	
	if not allhyp:
		allhyp = 0
	if not alldev:
		alldev = 0
	if not allmno:
		allmno = 0

	total = float(allcirc) + float(alldev) + float(allhyp) + float(allmno)
	circulating = float(allcirc) + float(allhyp) + float(allmno)
	
	total = "{:.8f}".format(total)
	circulating = "{:.8f}".format(circulating)

	c.close()
	conn.close()
	
	return total,circulating

def rev_alias(tocheck):

	a_addy = tocheck.split(":")
	t_addy = str(a_addy[1])

	try:
		conn = sqlite3.connect('{}index.db'.format(db_root))
		conn.text_factory = str
		c = conn.cursor()
		c.execute("SELECT * FROM aliases WHERE alias=? ORDER BY block_height ASC;", (t_addy,))
		d_addy = c.fetchone()
	
		if d_addy:
			r_addy = d_addy[1]
		else:
			r_addy = "0"

		c.close()
		conn.close()
	except:
		r_addy = "0"
		
	with open('custom.txt', 'r') as infile:
		for line in infile:
			cust = line.split(':')
			if t_addy == cust[0].strip():
				r_addy = cust[1].strip()
		
	return str(r_addy)

def display_time(seconds, granularity=2):

	intervals = (
		('weeks', 604800),  # 60 * 60 * 24 * 7
		('days', 86400),    # 60 * 60 * 24
		('hours', 3600),    # 60 * 60
		('minutes', 60),
		('seconds', 1),
		)

	result = []

	for name, count in intervals:
		value = seconds // count
		if value:
			seconds -= value * count
			if value == 1:
				name = name.rstrip('s')
			result.append("{} {}".format(value, name))
	return ', '.join(result[:granularity])

def latest():

	conn = sqlite3.connect(bis_root)
	conn.text_factory = str
	c = conn.cursor()
	c.execute("SELECT * FROM transactions WHERE reward != 0 ORDER BY block_height DESC LIMIT 1;")
	block_get = c.fetchall()[0]
	
	c.execute("SELECT difficulty FROM misc WHERE block_height = ?;", (block_get[0],))
	diff = c.fetchall()[0]
	
	db_block_height = str(block_get[0])
	db_timestamp_last = block_get[1]
	db_block_finder = block_get[2]
	db_block_hash = block_get[7]
	db_block_txid = block_get[5][:56]
	db_block_open = block_get[11]
	time_now = str(time.time())
	last_block_ago = (float(time_now) - float(db_timestamp_last))#/60
	#last_block_ago = '%.2f' % last_block_ago
	diff_block_previous = diff[0]
	
	c.close()
	conn.close()

	return db_block_height, last_block_ago, diff_block_previous, db_block_finder, db_timestamp_last, db_block_hash, db_block_open, db_block_txid

	
def get_block_time(my_hist):

	lb_tick = latest()
	lb_height = lb_tick[0]
	lb_stamp = lb_tick[4]
	sb_height = int(lb_height) - my_hist
	
	conn = sqlite3.connect(bis_root)
	conn.text_factory = str
	c = conn.cursor()
	c.execute("SELECT timestamp,block_height FROM transactions WHERE reward !=0 and block_height >= ?;",(str(sb_height),))
	result = c.fetchall()

	l = []
	y = 0
	for x in result:
		if y == 0:
			ts_difference = 0
		else:
			ts_difference = float(x[0]) - float(y)
		ts_block = x[1]
		#print(str(x[1])+" "+str(ts_difference))
		tx = (ts_block,ts_difference)
		l.append(tx)
		y = x[0]

	return l


def get_the_details(getdetail, get_addy):

	m_stuff = "{}%".format(str(getdetail))
	
	if db_hyper:
	
		conn = sqlite3.connect(hyper_root)
		conn.text_factory = str
		c = conn.cursor()
		c.execute("PRAGMA case_sensitive_like=OFF;")
		c.execute("SELECT * FROM transactions WHERE signature LIKE ?;", (m_stuff,))
		m_detail = c.fetchone()
		#print(m_detail)
		c.close()
		conn.close()
		
		if not m_detail:
		
			if get_addy:
		
				conn = sqlite3.connect(bis_root)
				conn.text_factory = str
				c = conn.cursor()
				c.execute("SELECT * FROM transactions WHERE address = ?;", (get_addy,))
				t_detail = c.fetchall()
				c.close()
				conn.close()

				x_detail = [sig for sig in t_detail if getdetail in sig[5]]
				
				m_detail = x_detail[0]
				
			else:
				conn = sqlite3.connect(bis_root)
				conn.text_factory = str
				c = conn.cursor()
				c.execute("PRAGMA case_sensitive_like=OFF;")
				c.execute("SELECT * FROM transactions WHERE signature LIKE ?;", (m_stuff,))
				m_detail = c.fetchone()
				#print(m_detail)
				c.close()
				conn.close()				

	else:
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		c = conn.cursor()
		c.execute("PRAGMA case_sensitive_like=OFF;")
		c.execute("SELECT * FROM transactions WHERE signature LIKE ?;", (m_stuff,))
		m_detail = c.fetchone()
		#print(m_detail)
		c.close()
		conn.close()	
	
	return m_detail

def test(testString):

	if testString.isalnum() == True:
		s = socks.socksocket()
		s.settimeout(10)
		s.connect((ip, int(port)))
		connections.send(s, "addvalidate")
		connections.send(s, testString)
		validate_result = connections.receive(s)
		if validate_result == "valid":
			test_result = 1
		else:
			test_result = 3

	elif testString.isdigit() == True:
		test_result = 2
	else:
		test_result = 3
	
	#print(test_result)
	return test_result
	
def s_test(testString):

	if testString.isalnum() == True:
		s = socks.socksocket()
		s.settimeout(10)
		s.connect((ip, int(port)))
		connections.send(s, "addvalidate")
		connections.send(s, testString)
		validate_result = connections.receive(s)
		
		if validate_result == "valid":
			return True
		else:
			return False
	else:
		return False
		
def d_test(testString):

	if len(testString) == 56:
		if bool(BeautifulSoup(testString,"html.parser").find()):
			return False
		else:
			return True
	else:
		return False

def miners():

	conn = sqlite3.connect('tools.db')
	conn.text_factory = str
	c = conn.cursor()
	c.execute("SELECT * FROM minerlist ORDER BY blockcount DESC;")
	miner_result = c.fetchall()
	c.close()
	conn.close()

	return miner_result

def richones():

	conn = sqlite3.connect('tools.db')
	conn.text_factory = str
	c = conn.cursor()
	c.execute("SELECT * FROM richlist ORDER BY balance DESC;")
	rich_result = c.fetchall()
	c.close()
	conn.close()

	return rich_result
	
def bgetvars(myaddress):

	try:
		conn = sqlite3.connect('tools.db')
		conn.text_factory = str
		c = conn.cursor()
		c.execute("SELECT * FROM minerlist WHERE address = ?;",(myaddress,))
		miner_details = c.fetchone()
		c.close()
		conn.close()
	except:
		miner_details = None
		
	return miner_details
	
def get_cmc_val():

	global cmc_vals
	
	l = ["BTC","USD","EUR","GBP","CNY","AUD"]
	p = []
	
	t = "https://api.coingecko.com/api/v3/coins/bismuth?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
	r = requests.get(t)
	x = r.text
	y = json.loads(x)
	
	for curr in l:
	
		ch = curr.lower()
	
		try:
			s = float(y['market_data']['current_price'][ch])
		
		except:
			s = 0.00000001
			
		p.append(s)
		
		time.sleep(1)
		
	s = dict(zip(l, p))
		
	return s

def get_alias(address):

	try:
		conn = sqlite3.connect('{}index.db'.format(db_root))
		conn.text_factory = str
		c = conn.cursor()
		c.execute("SELECT * FROM aliases WHERE address=? ORDER BY block_height DESC;", (address,))
		r_alias = c.fetchone()[2]
		c.close()
		conn.close()
		
		if not r_alias:
			r_alias = ""
	except:
		r_alias = ""
	
	with open('custom.txt', 'r') as infile:
		for line in infile:
			cust = line.split(':')
			if address == cust[1].strip():
				r_alias = cust[0].strip()
				#print(r_alias)
		
	return r_alias

	
def get_tokens(address):

	try:
		conn = sqlite3.connect('{}index.db'.format(db_root))
		conn.text_factory = str
		c = conn.cursor()
		c.execute("SELECT * FROM tokens WHERE address=? ORDER BY block_height ASC;", (address,))
		r_tokens = c.fetchall()
		c.close()
		conn.close()

	except:
		r_tokens = None

	return r_tokens


def refresh(testAddress,typical):

	if typical == 1:
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		c = conn.cursor()
	elif typical == 2:
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		c = conn.cursor()
	else:
		pass
	
	credit = float(0)
	try:
		c.execute("SELECT amount FROM transactions WHERE recipient = ?;",(testAddress,))
		entries = c.fetchall()
	except:
		entries = []
	try:
		for entry in entries:	
			credit = credit + float(entry[0])
			credit = 0 if credit is None else credit
	except:
		credit = 0
		
	c.execute("SELECT sum(amount),sum(fee),sum(reward) FROM transactions WHERE address = ?;",(testAddress,))
	tester = c.fetchall()

	debit = tester[0][0]
	fees = tester[0][1]
	rewards = tester[0][2]
	
	if not rewards:
		rewards = 0
	
	if rewards > 0:		
		c.execute("SELECT count(*) FROM transactions WHERE address = ? AND (reward != 0);",(testAddress,))
		b_count = c.fetchone()[0]
		c.execute("SELECT MAX(timestamp) FROM transactions WHERE recipient = ? AND (reward !=0);",(testAddress,))
		t_max = c.fetchone()[0]
		c.execute("SELECT MIN(timestamp) FROM transactions WHERE recipient = ? AND (reward !=0);",(testAddress,))
		t_min = c.fetchone()[0]

		t_min = str(time.strftime("at %H:%M:%S on %d/%m/%Y", time.gmtime(float(t_min))))
		t_max = str(time.strftime("at %H:%M:%S on %d/%m/%Y", time.gmtime(float(t_max))))
	else:
		b_count = 0
		t_min = 0
		t_max = 0
	
	if not debit:
		debit = 0
	if not fees:
		fees = 0
	if not rewards:
		rewards = 0
	if not credit:
		credit = 0

	balance = (credit + rewards) - (debit + fees)

	c.close()
	conn.close()
	
	if typical == 1:
		conn.close()
		
	r_alias = get_alias(testAddress)
	
	get_stuff = ["{:.8f}".format(credit),"{:.8f}".format(debit),"{:.8f}".format(rewards),"{:.8f}".format(fees),"{:.8f}".format(balance),t_max, t_min, b_count, r_alias]
		
	return get_stuff