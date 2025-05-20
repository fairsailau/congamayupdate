import pandas as pd
from typing import List, Optional
from pydantic import ValidationError

from ..DTOs.models import QueryContextRow # Relative import

class CsvParserError(Exception):
    """Custom exception for CSV parsing errors."""
    pass

def parse_query_context(file_path: str) -> Optional[List[QueryContextRow]]:
    """
    Parses the query context CSV file into a list of QueryContextRow Pydantic models.

    Args:
        file_path: The absolute path to the query_context.csv file.

    Returns:
        A list of QueryContextRow objects if parsing is successful, None otherwise.
        
    Raises:
        CsvParserError: If the file cannot be read, CSV is malformed, or data is invalid against the model.
    """
    try:
        # Read CSV, ensuring empty strings are treated as NaN, then convert to None for Pydantic
        df = pd.read_csv(file_path, keep_default_na=False, na_values=[''])
    except FileNotFoundError:
        raise CsvParserError(f"Error: Query context file not found at {file_path}")
    except pd.errors.EmptyDataError:
        # Handle empty CSV file - might return an empty list or raise error based on requirements
        return [] # Or raise CsvParserError(f"Error: Query context file {file_path} is empty.")
    except pd.errors.ParserError as e:
        raise CsvParserError(f"Error: Malformed CSV in query context file {file_path}. Details: {e}")
    except Exception as e:
        raise CsvParserError(f"Error: Could not read query context file {file_path}. Details: {e}")

    query_context_rows: List[QueryContextRow] = []
    errors_found = []

    for index, row in df.iterrows():
        try:
            # Convert row to dict, replacing NaN with None for Pydantic compatibility
            row_data = row.where(pd.notnull(row), None).to_dict()
            # Ensure all expected fields are present, even if None, before Pydantic validation
            # This handles cases where optional columns might be missing entirely from the CSV
            model_fields = QueryContextRow.model_fields.keys()
            sanitized_row_data = {field: row_data.get(field) for field in model_fields}
            
            query_row = QueryContextRow(**sanitized_row_data)
            query_context_rows.append(query_row)
        except ValidationError as e:
            errors_found.append(f"Row {index + 2}: {e.errors()}") # +2 because header is row 1, data starts row 2
        except Exception as e:
            errors_found.append(f"Row {index + 2}: Unexpected error - {str(e)}")

    if errors_found:
        error_messages = "\n".join(errors_found)
        # You might want to log this to a file or a more sophisticated logging system
        print(f"Validation Errors for {file_path}:\n{error_messages}")
        raise CsvParserError(
            f"Error: Query context file {file_path} contains invalid data. "
            f"{len(errors_found)} row(s) failed validation. Check logs for details."
        )

    return query_context_rows

if __name__ == '__main__':
    import os
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DUMMY_CSV_FILE = os.path.join(PROJECT_ROOT, "input_data", "query_context.csv")
    
    print(f"Attempting to parse: {DUMMY_CSV_FILE}")

    if not os.path.exists(DUMMY_CSV_FILE):
        print(f"Test CSV file {DUMMY_CSV_FILE} not found. Please create it.")
    else:
        try:
            parsed_rows = parse_query_context(DUMMY_CSV_FILE)
            if parsed_rows is not None:
                print(f"\nSuccessfully parsed {len(parsed_rows)} rows from query_context.csv:")
                for i, row_model in enumerate(parsed_rows):
                    print(f"  Row {i+1}: {row_model.model_dump_json()}")
        except CsvParserError as e:
            print(f"CSV Parsing Test Failed: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during testing: {e}")

    # Test with a non-existent file
    print("\nAttempting to parse non_existent_query.csv:")
    try:
        parse_query_context("non_existent_query.csv")
    except CsvParserError as e:
        print(f"Successfully caught expected error: {e}")

    # Test with a malformed CSV (e.g., inconsistent number of columns)
    MALFORMED_CSV_PATH = os.path.join(PROJECT_ROOT, "input_data", "malformed_query.csv")
    with open(MALFORMED_CSV_PATH, 'w') as f:
        f.write("CongaField,RelatedBoxField,DataType\nField1,Box1,Type1\nField2,Box2") # Missing DataType for second row
    
    print(f"\nAttempting to parse {MALFORMED_CSV_PATH}:")
    try:
        # Pandas might handle this gracefully by filling NaN, but Pydantic validation might catch issues if fields are required
        # Or, if column names are critical and missing, pandas might error directly.
        # Let's test a case where a required field for Pydantic is missing.
        pass # The current QueryContextRow has optional fields, so basic malformations might pass pandas
             # A more robust test would be to ensure required fields from Pydantic fail if missing in CSV
    except CsvParserError as e:
        print(f"Successfully caught expected error for malformed CSV: {e}")
    finally:
        if os.path.exists(MALFORMED_CSV_PATH):
            os.remove(MALFORMED_CSV_PATH)

    # Test with data that fails Pydantic validation (e.g., wrong data type if Pydantic model was stricter)
    # Current QueryContextRow is all strings/optional, so direct type validation is minimal from CSV to string.
    # If QueryContextRow had, e.g., an integer field, we could test 'abc' in that column.
    INVALID_DATA_CSV_PATH = os.path.join(PROJECT_ROOT, "input_data", "invalid_data_query.csv")
    # For QueryContextRow to fail validation, a required field would need to be missing AND not nullable.
    # Our current model has all fields as optional or string, so it's hard to make it fail Pydantic validation from a CSV that pandas can read.
    # Let's assume 'CongaField' was non-optional and we provide an empty one.
    with open(INVALID_DATA_CSV_PATH, 'w') as f:
        f.write("CongaField,RelatedBoxField,DataType,SourceTable\n,Box1,Type1,Table1") # Empty CongaField

    print(f"\nAttempting to parse {INVALID_DATA_CSV_PATH} (expecting Pydantic error on CongaField if it were strictly required and non-empty):")
    # Note: Pydantic treats empty string as valid for a string field. 
    # To make this fail, CongaField would need a `min_length=1` validator or similar in the model.
    # Since we don't have that, this particular test might pass. We will adjust the model if stricter validation is needed.
    try:
        rows = parse_query_context(INVALID_DATA_CSV_PATH)
        if rows and not rows[0].CongaField:
            print(f"CSV parsed, but CongaField is empty: '{rows[0].CongaField}'. Pydantic allows empty strings for str type by default.")
            # This isn't an error by current model; to make it an error, `CongaField: str = Field(..., min_length=1)`
    except CsvParserError as e:
        print(f"Successfully caught expected error for invalid data: {e}") # This might not be hit with current model
    finally:
        if os.path.exists(INVALID_DATA_CSV_PATH):
            os.remove(INVALID_DATA_CSV_PATH)
