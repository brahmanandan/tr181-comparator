#!/usr/bin/env python3
import sys
import json
import xml.etree.ElementTree as ET
from collections import defaultdict

def usage():
    print(f"Usage: {sys.argv[0]} <input.xml> <output.json> <output.txt>")
    sys.exit(1)

def etree_to_dict(t):
    # Skip 'description' and 'profile' elements entirely
    if t.tag == 'description' or t.tag == 'profile':
        return {}
    d = {t.tag: {}}
    children = [child for child in t if child.tag not in ('description', 'profile')]
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                if v != {}:  # skip empty dicts from skipped descriptions/profiles
                    dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v for k, v in dd.items()}}
    if t.attrib:
        for k, v in t.attrib.items():
            if k == '{urn:broadband-forum-org:cwmp:datamodel-report-0-1}version':
                continue
            d[t.tag][f"@{k}"] = v
    if t.text and t.text.strip():
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[t.tag]["#text"] = text
        else:
            d[t.tag] = text
    return d

def print_table(model_dict, output_file=None):
    def format_access(access):
        if access == 'readOnly':
            return 'R'
        elif access == 'readWrite':
            return 'RW'
        return access

    # Determine where to write output
    output_lines = []
    
    def write_line(line=""):
        if output_file:
            output_lines.append(line)
        else:
            print(line)

    try:
        from tabulate import tabulate
        use_tabulate = True
    except ImportError:
        use_tabulate = False
    rows = []
    for k, v in model_dict.items():
        if isinstance(v, list):
            vtype = f"list[{len(v)}]"
        elif isinstance(v, dict):
            vtype = f"dict[{len(v)}]"
        else:
            vtype = type(v).__name__
        rows.append([k, vtype])
    headers = ["Key", "Type/Length"]
    if use_tabulate:
        write_line("\nModel Object Table:")
        table_output = tabulate(rows, headers=headers, tablefmt="github")
        write_line(table_output)
    else:
        write_line("\nModel Object Table:")
        write_line(f"{headers[0]:<30} {headers[1]:<20}")
        write_line("-" * 50)
        for row in rows:
            write_line(f"{row[0]:<30} {row[1]:<20}")

    # Print all objects in the 'object' list with only Object Name and Read/Write, and their parameters indented
    objects = model_dict.get('object', [])
    if not isinstance(objects, list):
        objects = [objects]
    obj_headers = ["Object/Parameter Name"]
    if use_tabulate:
        write_line("\nObjects and Parameters:")
        obj_rows = []
        for obj in objects:
            name = obj.get('@name', obj.get('name', ''))
            obj_rows.append([name])
            # Print parameters with object prefix
            params = obj.get('parameter', [])
            if not isinstance(params, list):
                params = [params]
            for param in params:
                pname = param.get('@name', param.get('name', ''))
                full_pname = f"{name}{pname}" if name and pname else pname
                obj_rows.append([f"{full_pname}"])
        table_output = tabulate(obj_rows, headers=obj_headers, tablefmt="plain")
        write_line(table_output)
        # write_line(tabulate(obj_rows, headers=obj_headers, tablefmt="github"))
    else:
        write_line("\nObjects and Parameters:")
        write_line(f"{obj_headers[0]:<40}")
        write_line("-" * 40)
        for obj in objects:
            name = obj.get('@name', obj.get('name', ''))
            write_line(f"{name:<40}")
            # Print parameters with object prefix
            params = obj.get('parameter', [])
            if not isinstance(params, list):
                params = [params]
            for param in params:
                pname = param.get('@name', param.get('name', ''))
                full_pname = f"{name}{pname}" if name and pname else pname
                write_line(f"{full_pname:<37}")

    # Write to file if output_file is specified
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in output_lines:
                f.write(line + '\n')

def main():
    if len(sys.argv) != 4:
        usage()
    input_path, output_path, text_output_path = sys.argv[1], sys.argv[2], sys.argv[3]
    try:
        tree = ET.parse(input_path)
        root = tree.getroot()
        # Find the 'model' element anywhere under the root
        model_elem = None
        for child in root.iter():
            if child.tag == 'model':
                model_elem = child
                break
        if model_elem is None:
            print("Error: No 'model' element found in the XML.")
            sys.exit(3)
        data = etree_to_dict(model_elem)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Converted {input_path} to {output_path} (model only)")
        # Print table summary to file
        model_obj = data.get('model', {})
        print_table(model_obj, text_output_path)
        print(f"Table summary written to {text_output_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main() 
