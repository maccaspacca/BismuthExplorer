"""
Bismuth Explorer Node Plugin

Sends information to explorer kafka instance

Version 0.05 Test

"""

import json, threading, socks, connections, time, requests
import configparser as cp

# Read config
config = cp.ConfigParser()
config.readfp(open(r'601_plugin.ini'))

try:
	kafkahost = config.get('My Plugin', 'kafkahost')
except:
	kafkahost = "127.0.0.1"
try:
	kafkaport = config.get('My Plugin', 'kafkaport')
except:
	kafkaport = "9092"
try:
	alt_curr = config.get('My Plugin', 'altcurrency')
except:
	alt_curr = "EUR"
try:
	ip = port = config.get('My Plugin', 'nodeip')
except:
	ip = "localhost"
try:
	port = config.get('My Plugin', 'nodeport')
except:
	port = "5658"
try:
	doprice = config.get('My Plugin', 'doprice')
	if doprice.lower() == "true":
		do_cmc = True
	else:
		do_cmc = False
except:
	do_cmc = True
	
# Read config

from kafka import SimpleProducer, KafkaClient

#  connect to Kafka
kafka = KafkaClient('{}:{}'.format(kafkahost,kafkaport))
producer = SimpleProducer(kafka)
# Assign topics
topic1 = 'blocks'
topic2 = 'status'
topic3 = 'mempool'
topic4 = 'cmc'
topic5 = 'mpgetjson'
topic6 = 'wallet_servers'


def get_info():

	starting_up = True
	
	while starting_up:
		time.sleep(60)
		
		try:
			s = socks.socksocket()
			s.settimeout(10)
			s.connect((ip, int(port)))
			starting_up = False
		except:
			starting_up = True
	
	count = 0
	while True:

		if count == 0 or count % 30 == 0:
			if do_cmc:
			
				ch = alt_curr.lower()

				try:
					t = "https://api.coingecko.com/api/v3/coins/bismuth?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
					r = requests.get(t)
					x = r.text
					y = json.loads(x)
					try:
						c_btc = "{:.8f}".format(float(y['market_data']['current_price']['btc']))
						c_usd = "{:.3f}".format(float(y['market_data']['current_price']['usd']))
						c_cus = "{:.3f}".format(float(y['market_data']['current_price'][ch]))
						cmc = {'btc': c_btc, 'usd': c_usd, 'fiat': c_cus}
					except:
						cmc = {'btc': '0.0', 'usd': '0.0', 'fiat': '0.0'}
				except requests.exceptions.RequestException as e:
					print(e)
					cmc = {'btc': '0.0', 'usd': '0.0', 'fiat': '0.0'}
			else:
				cmc = {'btc': '0.0', 'usd': '0.0', 'fiat': '0.0'}
			
			c = (json.dumps(cmc)).encode('utf-8')
			producer.send_messages(topic4, c)
			
		if count == 0 or count % 12 == 0:
			
			rep = requests.get("http://api.bismuth.live/servers/wallet/legacy.json")
			if rep.status_code == 200:
				wallets = rep.json()
								
			sorted_wallets = sorted([wallet for wallet in wallets if wallet['active']], key=lambda k: (k['clients']+1)/(k['total_slots']+2))
			
			w = (json.dumps(sorted_wallets)).encode('utf-8')
		
			producer.send_messages(topic6, w)
		
		connections.send(s, "mpgetjson", 10)
		mempool = connections.receive(s, 10)
		
		#if mempool:			
		num_tx = str(len(mempool))
		if not num_tx:
			num_tx = "0"
		ml = (json.dumps(mempool)).encode('utf-8')
		m = num_tx.encode('utf-8')
		producer.send_messages(topic3, m)
		producer.send_messages(topic5, ml)
	
		time.sleep(10)
		if count == 359: # prevent counting forever
			count = 0
		else:
			count +=1

def action_init(params):
	print("Init Explorer data.... waiting a little for node to start")
	background_thread = threading.Thread(target=get_info)
	background_thread.daemon = True
	background_thread.start()


def action_block(block):
	
	#print("Got New Block {}".format(json.dumps(block)))
	b = (json.dumps(block)).encode('utf-8')
	producer.send_messages(topic1, b)
	
	
def action_status(status):

	#print("Got New Status: {}".format(json.dumps(status)))
	s = (json.dumps(status)).encode('utf-8')
	producer.send_messages(topic2, s)
	#curr_consensus = str(status['consensus'])
	#print(curr_consensus)
	
