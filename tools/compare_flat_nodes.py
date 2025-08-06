#!/usr/bin/env python3
import sys
import argparse

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

def read_nodes(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def get_node_type(node):
    """Determine the type of a node based on its format"""
    if node.endswith('.'):
        return "-"
    elif '() input:' in node:
        return "FUNCTION INPUT"
    elif '() output:' in node:
        return "FUNCTION OUTPUT"
    elif node.endswith('()'):
        return "FUNCTION"
    elif '! event_arg:' in node:
        return "EVENT ARGUMENT"
    elif node.endswith('!'):
        return "EVENT"
    else:
        return ""

def write_output(text, output_file=None):
    """Write text to file or stdout"""
    if output_file:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        print(text)

def main():
    parser = argparse.ArgumentParser(description="Compare nodes between two text files")
    parser.add_argument("file1", help="First input file")
    parser.add_argument("file2", help="Second input file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    # Clear output file if it exists
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write("")  # Clear the file
    
    nodes1 = read_nodes(args.file1)
    nodes2 = read_nodes(args.file2)

    common = sorted(nodes1 & nodes2)
    only_in_1 = sorted(nodes1 - nodes2)
    only_in_2 = sorted(nodes2 - nodes1)

    if HAS_TABULATE:
        # Use tabulate for formatted output
        write_output('=== Common Nodes ===', args.output)
        if common:
            common_data = [[node, get_node_type(node), 'REQ PRESENT'] for node in common]
            table_output = tabulate(common_data, headers=['Node', 'Type', 'Status'], tablefmt='plain')
            write_output(table_output, args.output)
        write_output(f'\nTotal: {len(common)}', args.output)

        write_output(f'\n=== Nodes only in {args.file1} ===', args.output)
        if only_in_1:
            only_1_data = [[node, get_node_type(node), 'NO-REQ PRESENT'] for node in only_in_1]
            table_output = tabulate(only_1_data, headers=['Node', 'Type', 'Status'], tablefmt='plain')
            write_output(table_output, args.output)
        write_output(f'\nTotal: {len(only_in_1)}', args.output)

        write_output(f'\n=== Nodes only in {args.file2} ===', args.output)
        if only_in_2:
            only_2_data = [[node, get_node_type(node), 'REQ NOT-PRESENT'] for node in only_in_2]
            table_output = tabulate(only_2_data, headers=['Node', 'Type', 'Status'], tablefmt='plain')
            write_output(table_output, args.output)
        write_output(f'\nTotal: {len(only_in_2)}', args.output)
    else:
        # Fallback to original formatting if tabulate not available
        write_output('=== Common Nodes ===', args.output)
        for node in common:
            write_output(f'{node} | {get_node_type(node)} | REQ PRESENT', args.output)
        write_output(f'\nTotal: {len(common)}', args.output)

        write_output(f'\n=== Nodes only in {args.file1} ===', args.output)
        for node in only_in_1:
            write_output(f'{node} | {get_node_type(node)} | NO-REQ PRESENT', args.output)
        write_output(f'\nTotal: {len(only_in_1)}', args.output)

        write_output(f'\n=== Nodes only in {args.file2} ===', args.output)
        for node in only_in_2:
            write_output(f'{node} | {get_node_type(node)} | REQ NOT-PRESENT', args.output)
        write_output(f'\nTotal: {len(only_in_2)}', args.output)

if __name__ == '__main__':
    main() 
