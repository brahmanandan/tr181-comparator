import os
import sys
import pandas as pd
import re

def parse_bulk(file_path):
	# Each line is assumed to be in the format: <Node> => <Reference>
	data = []
	with open(file_path, 'r') as f:
		for line in f:
			line = line.strip()
			if not line or '=>' not in line:
				continue
			left, right = line.split('=>', 1)
			node = left.strip()
			value = right.strip()
			# Extract node prefix and property name
			m = re.match(r'(Device\.BulkData\.Profile\.\d+\.Parameter\.\d+)\.(\w+)', node)
			if m:
				node_prefix, prop = m.groups()
				node_full = node_prefix + '.'
			else:
				node_prefix, prop = node, ''
				node_full = node_prefix
			# Store values by node
			if prop == 'Name':
				current = {'Node': node_full, 'Name': value, 'Reference': ''}
				data.append(current)
			elif prop == 'Reference':
				# Try to find the last entry for this node and fill Reference
				for entry in reversed(data):
					if entry['Node'] == node_full:
						entry['Reference'] = value
						break
				else:
					# If not found, create a new entry
					data.append({'Node': node_full, 'Name': '', 'Reference': value})
	df = pd.DataFrame(data, columns=['Node', 'Name', 'Reference'])
	# Sort by Node numerically
	def node_sort_key(node):
		# Extract numbers from Device.BulkData.Profile.{i}.Parameter.{j}.
		m = re.match(r'Device\.BulkData\.Profile\.(\d+)\.Parameter\.(\d+)\.', node)
		if m:
			return (int(m.group(1)), int(m.group(2)))
		return (float('inf'), float('inf'))
	df = df.sort_values(by='Node', key=lambda col: col.map(node_sort_key)).reset_index(drop=True)
	return df

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser(description='Parse bulk-data.txt and generate Excel file.')
	parser.add_argument('input', help='Path to input bulk-data.txt')
	parser.add_argument('output', help='Path to output Excel file (.xlsx)')
	args = parser.parse_args()

	df = parse_bulk(args.input)
	df.to_excel(args.output, index=False)
	print(f"Excel file created: {args.output}")
