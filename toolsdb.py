"""

Bismuth Explorer Tools DB Module

Version 1.00

"""
import sqlite3, time, os, threading, logging, toolsp
from glob import glob
from logging.handlers import RotatingFileHandler

log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
logFile = 'toolsdb.log'
my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=5 * 1024 * 1024, backupCount=2, encoding="UTF-8", delay=0)
my_handler.setFormatter(log_formatter)
my_handler.setLevel(logging.INFO)
app_log = logging.getLogger('root')
app_log.setLevel(logging.INFO)
app_log.addHandler(my_handler)

import configparser as cp

# Read config
config = cp.ConfigParser()
config.readfp(open(r'explorer.ini'))

try:
	bis_root = config.get('My Explorer', 'bisroot')
except:
	bis_root = "static/ledger.db"
try:
	bis_limit = int(config.get('My Explorer', 'bis_limit'))
except:
	bis_limit = 1


def updatedb(do_first,last_block):

	if do_first:

		if os.path.exists('tools.db'):
			app_log.info("Tools DB: Already present...deleting")
			os.remove('tools.db')
			
		app_log.info("Tools DB: Create new database")
		# create empty tools database
		mlist = sqlite3.connect('tools.db')
		mlist.text_factory = str
		m = mlist.cursor()
		m.execute("CREATE TABLE IF NOT EXISTS richlist (address, balance, alias)")
		m.execute("CREATE TABLE IF NOT EXISTS minerlist (address, blatest, bfirst, blockcount, treward, mname)")
		mlist.commit()
		m.close()
		mlist.close()
		# create empty tools.db

		print("Filling up the new database.....wait")
		app_log.info("Tools DB: Getting info.....")
		
		r_all = []
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		r = conn.cursor()
		r.execute("SELECT distinct recipient FROM transactions WHERE amount !=0 OR reward !=0;")
		r_temp = r.fetchall()
		r.close()
		
		r_all = [a[0] for a in r_temp]
				
	else:
		latest_block = int(toolsp.latest()[0])
		start_block = int(last_block)
		block_limit = latest_block - start_block
		
		print("Tools DB: Getting info.....")
		app_log.info("Tools DB: Getting info.....")
		r_all = []
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		r = conn.cursor()
		r.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?;", (block_limit,))
		r_temp = r.fetchall()
		r.close()
				
		for t in r_temp:
			if t[2] not in r_all:
				if t[2].lower() == "hypernode payouts" or t[2].lower() == "development reward":
					app_log.info("Tools DB: Not Hypernode Payouts or Development Reward")
				else:
					r_all.append(t[2])
					#print(t[2])
			if t[3] not in r_all:
				r_all.append(t[3])
				#print(t[3])
				
					
	app_log.info("Tools DB: Updating tools database")
	print("Tools DB: Updating tools database")
	mlist = sqlite3.connect('tools.db')
	mlist.text_factory = str
	m = mlist.cursor()
	m.execute("begin")

	for x in r_all:
	
		if not do_first:
			try:
				m.execute("DELETE FROM richlist WHERE address =?;", (x,))
				m.execute("DELETE FROM minerlist WHERE address =?;", (x,))
				m.execute("commit")
				mlist.commit()
			except:
				pass

		btemp = toolsp.refresh(str(x),2)
		m_alias = btemp[8]
		print(str(x))
		#print(btemp[4])
		#amirich = float(btemp[4])
		
		if float(btemp[4]) > bis_limit:
			m.execute('INSERT INTO richlist VALUES (?,?,?)', (x,btemp[4],m_alias))

		if float(btemp[2]) > 0:
				temp_miner = str(x)
				m.execute('INSERT INTO minerlist VALUES (?,?,?,?,?,?)', (temp_miner, btemp[5], btemp[6], btemp[7], btemp[2], m_alias))
		
	#m.execute("commit")
	mlist.commit()
	m.close()
	mlist.close()

	return True
	
		
def buildtoolsdb():

	fpath = "block.txt"
	if not os.path.exists(fpath):
		do_first = True
		latest_block = str(toolsp.latest()[0])
		with open(fpath, "w") as file:
			file.write("{}\n".format(latest_block))	
		bobble = updatedb(do_first,None) 
	if os.path.exists(fpath):
		do_first = False
		while True:
		
			for f in glob("static/qr*.png"):
				os.remove(f)
			with open(fpath) as f:
				block_line = f.readline().rstrip()
				last_block = int(block_line) - 200 # take 200 just in case of rollbacks
			
			latest_block = str(toolsp.latest()[0])
			os.remove(fpath)
			with open(fpath, "w") as file:
				file.write("{}\n".format(latest_block))
			
			bobble = updatedb(do_first,last_block)
			print("Tools DB updated: Waiting for 20 minutes.......")
			time.sleep(1200)
		
if __name__ == "__main__":

	buildtoolsdb()

	#background_thread = threading.Thread(target=buildtoolsdb)
	#background_thread.daemon = True
	#background_thread.start()
	app_log.info("Databases: Start Thread")