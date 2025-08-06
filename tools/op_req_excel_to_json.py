import pandas as pd
import xml.etree.ElementTree as ET
import json
import sys
import os
import argparse

def excel_to_json_xml(input_excel, json_only=False, xml_only=False):
    # Check if file exists
    if not os.path.isfile(input_excel):
        print(f"Error: File '{input_excel}' not found.")
        return

    # Load Excel file
    try:
        df = pd.read_excel(input_excel)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    base_name = os.path.splitext(input_excel)[0]
    output_xml = f"{base_name}.xml"
    output_json = f"{base_name}.json"

    # Get the first column name
    first_column = df.columns[0]
    
    # Organize data hierarchically
    hierarchical_data = []
    current_object = None
    
    for _, row in df.iterrows():
        first_col_value = str(row[first_column]).strip()
        
        if first_col_value.endswith('.'):
            # This is an object
            current_object = {
                "type": "object",
                "name": first_col_value,
                "data": dict(row),
                "parameters": []
            }
            hierarchical_data.append(current_object)
        else:
            # This is a parameter
            parameter = {
                "type": "parameter",
                "name": first_col_value,
                "data": dict(row)
            }
            
            if current_object is not None:
                current_object["parameters"].append(parameter)
            else:
                # Parameter without a parent object, add as standalone
                hierarchical_data.append(parameter)

    # ---- XML Conversion ----
    if not json_only:  # Generate XML unless json_only is True
        root = ET.Element("Workbook")

        for item in hierarchical_data:
            if item["type"] == "object":
                obj_elem = ET.SubElement(root, "Object")
                obj_elem.set("name", item["name"])
                
                # Add object data
                for col_name, value in item["data"].items():
                    tag_name = str(col_name).strip().replace(" ", "_")
                    data_elem = ET.SubElement(obj_elem, tag_name)
                    data_elem.text = str(value)
                
                # Add parameters
                if item["parameters"]:
                    params_elem = ET.SubElement(obj_elem, "Parameters")
                    for param in item["parameters"]:
                        param_elem = ET.SubElement(params_elem, "Parameter")
                        param_elem.set("name", param["name"])
                        
                        for col_name, value in param["data"].items():
                            tag_name = str(col_name).strip().replace(" ", "_")
                            param_data_elem = ET.SubElement(param_elem, tag_name)
                            param_data_elem.text = str(value)
            else:
                # Standalone parameter
                param_elem = ET.SubElement(root, "Parameter")
                param_elem.set("name", item["name"])
                
                for col_name, value in item["data"].items():
                    tag_name = str(col_name).strip().replace(" ", "_")
                    param_data_elem = ET.SubElement(param_elem, tag_name)
                    param_data_elem.text = str(value)

        try:
            tree = ET.ElementTree(root)
            tree.write(output_xml, encoding="utf-8", xml_declaration=True)
            print(f"✅ XML written to: {output_xml}")
        except Exception as e:
            print(f"Error writing XML file: {e}")

    # ---- JSON Conversion ----
    if not xml_only:  # Generate JSON unless xml_only is True
        try:
            with open(output_json, 'w') as f:
                json.dump(hierarchical_data, f, indent=4, default=str)
            print(f"✅ JSON written to: {output_json}")
        except Exception as e:
            print(f"Error writing JSON file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Excel file to JSON and/or XML format")
    parser.add_argument("input_file", help="Input Excel file path")
    parser.add_argument("--json-only", action="store_true", help="Generate only JSON output")
    parser.add_argument("--xml-only", action="store_true", help="Generate only XML output")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.json_only and args.xml_only:
        print("Error: Cannot specify both --json-only and --xml-only")
        sys.exit(1)
    
    excel_to_json_xml(args.input_file, json_only=args.json_only, xml_only=args.xml_only)
