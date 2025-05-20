import sqlparse
from typing import Optional, List
from ..DTOs.models import SqlQueryContext # Relative import

class SqlParserError(Exception):
    """Custom exception for SQL parsing errors."""
    pass

def parse_sql_query_context(file_path: str) -> Optional[SqlQueryContext]:
    """
    Parses a .sql file to extract selected field names from SELECT statements.

    Args:
        file_path: The absolute path to the .sql file.

    Returns:
        An SqlQueryContext object containing a list of selected fields, or None if parsing fails.

    Raises:
        SqlParserError: If the file cannot be read or if SQL parsing encounters an issue.
    """
    try:
        with open(file_path, 'r') as f:
            sql_content = f.read()
    except FileNotFoundError:
        raise SqlParserError(f"Error: SQL query file not found at {file_path}")
    except Exception as e:
        raise SqlParserError(f"Error: Could not read SQL query file {file_path}. Details: {e}")

    if not sql_content.strip():
        # Handle empty or whitespace-only files gracefully
        return SqlQueryContext(selected_fields=[])

    parsed_statements = sqlparse.parse(sql_content)
    selected_fields: List[str] = []

    for stmt in parsed_statements:
        if stmt.get_type() == 'SELECT':
            # Iterate through tokens to find identifiers (field names/aliases)
            # This is a simplified approach; complex queries might need more robust parsing
            is_select_clause = False
            for token in stmt.tokens:
                if token.is_keyword and token.normalized == 'SELECT':
                    is_select_clause = True
                    continue
                if token.is_keyword and token.normalized in ('FROM', 'WHERE', 'GROUP', 'ORDER', 'LIMIT'):
                    is_select_clause = False # Stop collecting fields once FROM or other clauses start
                    break # Exit this inner loop, process next statement if any
                
                if is_select_clause:
                    if isinstance(token, sqlparse.sql.IdentifierList):
                        for identifier in token.get_identifiers():
                            # For 'alias AS original' or 'original alias', get the alias part if present
                            # Otherwise, get the identifier name itself.
                            # sqlparse gives the full token, e.g., "field_name AS alias_name"
                            # or just "field_name". We can split by AS or take the last part.
                            name_part = str(identifier).split('AS')[-1].strip()
                            if ' ' in name_part: # Handle 'field_name alias_name' case
                                name_part = name_part.split(' ')[-1].strip()
                            selected_fields.append(name_part)
                    elif isinstance(token, sqlparse.sql.Identifier):
                        name_part = str(token).split('AS')[-1].strip()
                        if ' ' in name_part: # Handle 'field_name alias_name' case
                            name_part = name_part.split(' ')[-1].strip()
                        selected_fields.append(name_part)
                    # We are not collecting keywords, whitespace, or punctuation within the SELECT list here

    if not selected_fields and parsed_statements: # If statements were parsed but no fields found (e.g. non-SELECT)
        # This might indicate a query that doesn't fit the expected SELECT... pattern or an issue
        # For now, we return an empty list. Depending on requirements, this could be an error.
        # print(f"Warning: No selectable fields found in {file_path}, though SQL was parsed.")
        pass 

    return SqlQueryContext(selected_fields=list(set(selected_fields))) # Remove duplicates

if __name__ == '__main__':
    # Example Usage (for testing the parser directly)
    # Create a dummy SQL file for testing
    dummy_sql_content_simple = "SELECT Id, Name, Account.Name AS AccountName FROM Opportunity WHERE StageName = 'Closed Won';" 
    dummy_sql_content_complex = """
    SELECT 
        o.Id AS OpportunityId, 
        o.Name AS OpportunityName, 
        a.Name AS AccountName, 
        c.Email AS PrimaryContactEmail, 
        (SELECT COUNT(Id) FROM OpportunityLineItem WHERE OpportunityId = o.Id) AS NumberOfProducts
    FROM 
        Opportunity o
    JOIN 
        Account a ON o.AccountId = a.Id
    LEFT JOIN 
        Contact c ON o.Primary_Contact__c = c.Id
    WHERE 
        o.IsClosed = TRUE AND o.IsWon = TRUE;

    -- Another query just to test multiple statements
    SELECT UserId, Username FROM User WHERE IsActive = true;
    """
    
    test_file_path_simple = "temp_test_simple.sql"
    test_file_path_complex = "temp_test_complex.sql"

    with open(test_file_path_simple, 'w') as f:
        f.write(dummy_sql_content_simple)
    
    with open(test_file_path_complex, 'w') as f:
        f.write(dummy_sql_content_complex)

    print(f"--- Testing with '{test_file_path_simple}' ---")
    try:
        result_simple = parse_sql_query_context(test_file_path_simple)
        if result_simple:
            print("Parsed SQL Query Context (Simple):")
            print(result_simple.model_dump_json(indent=2))
        else:
            print("No result or error during simple parsing.")
    except SqlParserError as e:
        print(f"Error parsing simple SQL: {e}")
    except Exception as e:
        print(f"An unexpected error occurred (simple): {e}")

    print(f"\n--- Testing with '{test_file_path_complex}' ---")
    try:
        result_complex = parse_sql_query_context(test_file_path_complex)
        if result_complex:
            print("Parsed SQL Query Context (Complex):")
            print(result_complex.model_dump_json(indent=2))
        else:
            print("No result or error during complex parsing.")
    except SqlParserError as e:
        print(f"Error parsing complex SQL: {e}")
    except Exception as e:
        print(f"An unexpected error occurred (complex): {e}")

    # Clean up dummy files
    import os
    try:
        os.remove(test_file_path_simple)
        os.remove(test_file_path_complex)
    except OSError:
        pass
