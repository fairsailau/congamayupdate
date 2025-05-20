import json
from typing import Optional
from pydantic import ValidationError

from ..DTOs.models import SchemaMapping # Relative import from DTOs package

class SchemaParserError(Exception):
    """Custom exception for schema parsing errors."""
    pass

def parse_schema_mapping(file_path: str) -> Optional[SchemaMapping]:
    """
    Parses the schema mapping JSON file into a SchemaMapping Pydantic model.

    Args:
        file_path: The absolute path to the schema_mapping.json file.

    Returns:
        A SchemaMapping object if parsing is successful, None otherwise.
        
    Raises:
        SchemaParserError: If the file cannot be read or if JSON is malformed or invalid against the model.
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SchemaParserError(f"Error: Schema mapping file not found at {file_path}")
    except json.JSONDecodeError as e:
        raise SchemaParserError(f"Error: Malformed JSON in schema mapping file {file_path}. Details: {e}")
    except Exception as e: # Catch any other potential IO errors
        raise SchemaParserError(f"Error: Could not read schema mapping file {file_path}. Details: {e}")

    try:
        schema_map = SchemaMapping(**data)
        return schema_map
    except ValidationError as e:
        # Log the detailed validation error or handle it as needed
        error_details = e.errors()
        # You might want to log this to a file or a more sophisticated logging system
        print(f"Validation Error for {file_path}: {error_details}") 
        raise SchemaParserError(
            f"Error: Schema mapping file {file_path} is invalid. "
            f"Validation failed with {len(error_details)} error(s). Check logs for details."
        )
    except Exception as e:
        # Catch any other unexpected errors during model instantiation
        raise SchemaParserError(f"Error: Unexpected error parsing schema mapping data from {file_path}. Details: {e}")

if __name__ == '__main__':
    # Example usage (assuming this file is run directly from within the parsers directory for testing)
    # You'll need to adjust the path or run this from the project root with python -m src.parsers.json_parser
    
    # Create a dummy schema_mapping.json for testing in the parent of src (project root)
    # This is just for simple testing if you run this script directly.
    # In the actual app, app.py will provide the path from uploaded files.

    import os
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DUMMY_SCHEMA_FILE = os.path.join(PROJECT_ROOT, "input_data", "schema_mapping.json")

    print(f"Attempting to parse: {DUMMY_SCHEMA_FILE}")

    # Ensure the dummy file exists for the test or use the one we created earlier
    if not os.path.exists(DUMMY_SCHEMA_FILE):
        print(f"Test schema file {DUMMY_SCHEMA_FILE} not found. Please create it or ensure path is correct.")
    else:
        try:
            parsed_schema = parse_schema_mapping(DUMMY_SCHEMA_FILE)
            if parsed_schema:
                print("\nSuccessfully parsed schema_mapping.json:")
                print(parsed_schema.model_dump_json(indent=2))
                print(f"\nDirect mappings: {len(parsed_schema.direct_mappings)}")
                print(f"Type rules: {len(parsed_schema.type_rules)}")
                print(f"Nested paths: {len(parsed_schema.nested_paths)}")
                if parsed_schema.nested_paths:
                    for path_name, path_detail in parsed_schema.nested_paths.items():
                        print(f"  Nested path '{path_name}': maps to '{path_detail.source_path}' with {len(path_detail.fields)} field(s)")

        except SchemaParserError as e:
            print(f"Schema Parsing Test Failed: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during testing: {e}")

    # Test with a non-existent file
    print("\nAttempting to parse non_existent_schema.json:")
    try:
        parse_schema_mapping("non_existent_schema.json")
    except SchemaParserError as e:
        print(f"Successfully caught expected error: {e}")

    # Test with a malformed JSON file (create one temporarily for testing if needed)
    MALFORMED_JSON_PATH = os.path.join(PROJECT_ROOT, "input_data", "malformed_schema.json")
    with open(MALFORMED_JSON_PATH, 'w') as f:
        f.write('{"direct_mappings": {"key": "value"},, "type_rules": {}}') # Extra comma
    
    print(f"\nAttempting to parse {MALFORMED_JSON_PATH}:")
    try:
        parse_schema_mapping(MALFORMED_JSON_PATH)
    except SchemaParserError as e:
        print(f"Successfully caught expected error for malformed JSON: {e}")
    finally:
        if os.path.exists(MALFORMED_JSON_PATH):
            os.remove(MALFORMED_JSON_PATH)

    # Test with invalid data against the Pydantic model
    INVALID_DATA_PATH = os.path.join(PROJECT_ROOT, "input_data", "invalid_data_schema.json")
    with open(INVALID_DATA_PATH, 'w') as f:
        # 'direct_mappings' should be a dict, not a list
        f.write('{"direct_mappings": ["invalid"], "type_rules": {}}')

    print(f"\nAttempting to parse {INVALID_DATA_PATH}:")
    try:
        parse_schema_mapping(INVALID_DATA_PATH)
    except SchemaParserError as e:
        print(f"Successfully caught expected error for invalid data: {e}")
    finally:
        if os.path.exists(INVALID_DATA_PATH):
            os.remove(INVALID_DATA_PATH)
