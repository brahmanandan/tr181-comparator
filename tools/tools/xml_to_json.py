#!/usr/bin/env python3
import sys
import json
import xml.etree.ElementTree as ET
from collections import defaultdict

def usage():
    print(f"Usage: {sys.argv[0]} <input.xml> <output.json>")
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

def print_table(model_dict):
    def format_access(access):
        if access == 'readOnly':
            return 'R'
        elif access == 'readWrite':
            return 'RW'
        return access

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
        print("\nModel Object Table:")
        print(tabulate(rows, headers=headers, tablefmt="github"))
    else:
        print("\nModel Object Table:")
        print(f"{headers[0]:<30} {headers[1]:<20}")
        print("-" * 50)
        for row in rows:
            print(f"{row[0]:<30} {row[1]:<20}")

    # Print all objects in the 'object' list with only Object Name and Read/Write, and their parameters indented
    objects = model_dict.get('object', [])
    if not isinstance(objects, list):
        objects = [objects]
    obj_headers = ["Object Name", "Read/Write"]
    if use_tabulate:
        print("\nObjects and Parameters:")
        obj_rows = []
        for obj in objects:
            name = obj.get('@name', obj.get('name', ''))
            access = format_access(obj.get('@access', obj.get('access', '')))
            obj_rows.append([name, access])
            # Print parameters indented
            params = obj.get('parameter', [])
            if not isinstance(params, list):
                params = [params]
            for param in params:
                pname = param.get('@name', param.get('name', ''))
                paccess = format_access(param.get('@access', param.get('access', '')))
                obj_rows.append([f"\t\t-> {pname}", paccess])
        print(tabulate(obj_rows, headers=obj_headers, tablefmt="github"))
    else:
        print("\nObjects and Parameters:")
        print(f"{obj_headers[0]:<40} {obj_headers[1]:<15}")
        print("-" * 55)
        for obj in objects:
            name = obj.get('@name', obj.get('name', ''))
            access = format_access(obj.get('@access', obj.get('access', '')))
            print(f"{name:<40} {access:<15}")
            # Print parameters indented
            params = obj.get('parameter', [])
            if not isinstance(params, list):
                params = [params]
            for param in params:
                pname = param.get('@name', param.get('name', ''))
                paccess = format_access(param.get('@access', param.get('access', '')))
                print(f"\t\t-> {pname:<37} {paccess:<15}")

def main():
    if len(sys.argv) != 3:
        usage()
    input_path, output_path = sys.argv[1], sys.argv[2]
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
        # Print table summary
        model_obj = data.get('model', {})
        print_table(model_obj)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main() 
