
import re
import os
import sys
import pandas as pd

def parse_subscriptions(file_path):
	# Define the columns in the required order
	columns = [
		'Node', 'Alias', 'CreationDate', 'Enable', 'ID', 'NotifExpiration',
		'NotifRetry', 'Persistent', 'Recipient', 'ReferenceList', 'TimeToLive'
	]
	# Map file keys to output columns
	key_map = {
		'Alias': 'Alias',
		'CreationDate': 'CreationDate',
		'Enable': 'Enable',
		'ID': 'ID',
		'NotifExpiration': 'NotifExpiration',
		'NotifRetry': 'NotifRetry',
		'Persistent': 'Persistent',
		'Recipient': 'Recipient',
		'ReferenceList': 'ReferenceList',
		'TimeToLive': 'TimeToLive',
	}
	# Parse the file
	subscriptions = {}
	with open(file_path, 'r') as f:
		for line in f:
			line = line.strip()
			if not line or '=>' not in line:
				continue
			left, right = line.split('=>', 1)
			left = left.strip()
			right = right.strip()
			# Match Device.LocalAgent.Subscription.{i}.<key>
			m = re.match(r'(Device\.LocalAgent\.Subscription\.(\d+))\.(\w+)', left)
			if not m:
				continue
			node, idx, key = m.groups()
			if node not in subscriptions:
				subscriptions[node] = {'Node': node}
			# Map file key to output column
			col = key_map.get(key)
			if col:
				subscriptions[node][col] = right
	# Prepare data for DataFrame
	data = []
	for node in sorted(subscriptions.keys(), key=lambda x: int(x.split('.')[-1])):
		row = [subscriptions[node].get(col, '') for col in columns]
		data.append(row)
	df = pd.DataFrame(data, columns=columns)
	return df

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser(description='Parse subscriptions.txt and generate Excel file.')
	parser.add_argument('input', help='Path to input subscriptions.txt')
	parser.add_argument('output', help='Path to output Excel file (.xlsx)')
	args = parser.parse_args()

	df = parse_subscriptions(args.input)
	df.to_excel(args.output, index=False)
	print(f"Excel file created: {args.output}")
