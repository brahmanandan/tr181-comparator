#!/usr/bin/env python3
import sys
import json

def usage():
    print(f"Usage: {sys.argv[0]} <input.json> <output.txt>")
    sys.exit(1)

def extract_arrow_parameter_name(param_name):
    """Extract parameter name from arrow-prefixed parameter."""
    if param_name.startswith("=> "):
        return param_name[3:]  # Remove "=> " prefix
    elif param_name.startswith("⇒ "):
        return param_name[2:]  # Remove "⇒ " prefix
    elif param_name.startswith("\u21d2 "):
        return param_name[2:]  # Remove unicode arrow + space
    elif param_name.startswith("\u21d2\u00a0"):
        return param_name[2:]  # Remove unicode arrow + non-breaking space
    else:
        return param_name[1:]  # Fallback - remove first character

def extract_paths_from_json(data, parent_path=""):
    """Recursively extract flat paths from hierarchical JSON data."""
    paths = []
    
    for item in data:
        if item["type"] == "object":
            object_name = item["name"]
            
            # Skip invalid object names
            if not object_name or str(object_name).lower() == 'nan':
                continue
            
            # Add the object itself
            if parent_path:
                full_object_path = f"{parent_path}{object_name}"
            else:
                full_object_path = object_name
            
            paths.append(full_object_path)
            
            # Process parameters under this object
            if "parameters" in item and item["parameters"]:
                last_method = None  # Track the last method for input parameters
                
                last_event = None  # Track the last event for event arguments
                
                for param in item["parameters"]:
                    param_name = param["name"]
                    
                    # Skip invalid parameter names
                    if not param_name or str(param_name).lower() == 'nan':
                        continue
                    
                    # Get operation type to distinguish between method args and event args
                    operation = param.get("data", {}).get("Controller Possible Operation", "")
                    
                    # Remove trailing dot from object path for cleaner parameter paths
                    object_base = full_object_path
                    if object_base.endswith('.'):
                        object_base = object_base[:-1]
                    
                    # Handle method input/output parameters and event arguments
                    if param_name.startswith("=> ") or param_name.startswith("⇒") or param_name.startswith("\u21d2"):
                        # Input parameter or event argument - check the operation type
                        if "event arguments" in str(operation).lower():
                            # This is an event argument
                            if last_event:
                                input_name = extract_arrow_parameter_name(param_name)
                                param_path = f"{object_base}.{last_event} event_arg:{input_name}"
                            else:
                                param_path = f"{object_base}.{param_name}"
                        else:
                            # This is a method input parameter
                            if last_method:
                                input_name = extract_arrow_parameter_name(param_name)
                                param_path = f"{object_base}.{last_method} input:{input_name}"
                            else:
                                param_path = f"{object_base}.{param_name}"
                    elif param_name.startswith("<= "):
                        # Output parameter
                        if last_method:
                            # Format as: method() output:ParameterName
                            output_name = param_name[3:]  # Remove "<= " prefix
                            param_path = f"{object_base}.{last_method} output:{output_name}"
                        else:
                            # Fallback if no method found
                            param_path = f"{object_base}.{param_name}"
                    else:
                        # Regular parameter or method
                        param_path = f"{object_base}.{param_name}"
                        
                        # Track if this is a method (ends with parentheses) or event (ends with !)
                        if param_name.endswith("()"):
                            last_method = param_name
                            last_event = None  # Reset event tracking
                        elif param_name.endswith("!"):
                            last_event = param_name
                            last_method = None  # Reset method tracking
                        else:
                            # Reset tracking for non-method/event parameters that are not input/output/event args
                            is_method_param = (param_name.startswith("=> ") or 
                                             param_name.startswith("⇒") or 
                                             param_name.startswith("\u21d2") or 
                                             param_name.startswith("<= "))
                            if not is_method_param:
                                last_method = None
                                last_event = None
                    
                    paths.append(param_path)
        
        elif item["type"] == "parameter":
            # Standalone parameter
            param_name = item["name"]
            
            # Skip invalid parameter names
            if not param_name or str(param_name).lower() == 'nan':
                continue
            
            if parent_path:
                param_path = f"{parent_path}{param_name}"
            else:
                param_path = param_name
            paths.append(param_path)
    
    return paths

def convert_json_to_flat(input_file, output_file):
    """Convert hierarchical JSON format to flat format with full paths."""
def convert_json_to_flat(input_file, output_file):
    """Convert hierarchical JSON format to flat format with full paths."""
    
    # Read JSON file
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        raise Exception(f"Error reading JSON file: {e}")
    
    # Extract paths from hierarchical data
    paths = extract_paths_from_json(data)
    
    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        for path in paths:
            f.write(f"{path}\n")
    
    return len(paths)

def main():
    if len(sys.argv) != 3:
        usage()
    
    input_file, output_file = sys.argv[1], sys.argv[2]
    
    try:
        count = convert_json_to_flat(input_file, output_file)
        print(f"Converted {input_file} to {output_file}")
        print(f"Generated {count} paths")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main() 