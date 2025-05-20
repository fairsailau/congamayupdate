import os
import sys
import streamlit as st

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# Custom module imports using absolute imports
from src.parsers.json_parser import parse_schema_mapping, SchemaParserError
from src.parsers.csv_parser import parse_query_context, CsvParserError
from src.parsers.docx_parser import extract_elements_from_docx, DocxParserError
from src.parsers.sql_parser import parse_sql_query_context, SqlParserError
from src.core.conversion_engine import convert_template, ConversionEngineError
from src.DTOs.models import (
    SchemaMapping,
    QueryContextRow,
    SqlQueryContext,
    ParsedTemplateElement,
    ConversionOutput
)

# Define project paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
INPUT_DATA_DIR = os.path.join(PROJECT_ROOT, "input_data")
OUTPUT_DATA_DIR = os.path.join(PROJECT_ROOT, "output_data")

# Ensure input and output directories exist
os.makedirs(INPUT_DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)

st.set_page_config(layout="wide", page_title="Conga to Box DocGen Converter")

st.title("Conga Template to Box DocGen Converter")

st.sidebar.header("Upload Input Files")

# --- 1. CONTEXT SOURCES --- #
st.sidebar.subheader("1. Template Analysis (DOCX)")
uploaded_conga_template = st.sidebar.file_uploader("Upload Conga Template (.docx)", type=["docx"])

st.sidebar.subheader("2. Query Context (CSV/SQL)")
uploaded_query_context = st.sidebar.file_uploader("Upload Query Context File (.csv or .sql)", type=["csv", "sql"])

st.sidebar.subheader("3. Schema Mapping (JSON)")
uploaded_schema_mapping = st.sidebar.file_uploader("Upload Schema Mapping File (.json)", type=["json"])

# --- Main Conversion Logic Area --- #
col1, col2 = st.columns(2)

with col1:
    st.header("Conversion Controls")
    if st.button("Start Conversion"): 
        if uploaded_conga_template and uploaded_query_context and uploaded_schema_mapping:
            st.info("Starting parsing process...")
            
            # Initialize results in session state
            st.session_state['parsed_schema_mapping'] = None
            st.session_state['parsed_query_context'] = None # For CSV
            st.session_state['parsed_sql_query_context'] = None # For SQL
            st.session_state['parsed_conga_template_elements'] = None
            st.session_state['conversion_output'] = None # For conversion engine results
            st.session_state['parsing_errors'] = []

            temp_files_to_delete = []

            try:
                # 1. Process Schema Mapping (JSON)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_schema:
                    tmp_schema.write(uploaded_schema_mapping.getvalue())
                    tmp_schema_path = tmp_schema.name
                    temp_files_to_delete.append(tmp_schema_path)
                st.session_state['parsed_schema_mapping'] = parse_schema_mapping(tmp_schema_path)
                st.write("✅ Schema Mapping parsed successfully.")

                # 2. Process Query Context (CSV/SQL)
                # For now, assuming CSV. SQL would need a different handling or parser branch.
                if uploaded_query_context.name.endswith('.csv'):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_query:
                        tmp_query.write(uploaded_query_context.getvalue())
                        tmp_query_path = tmp_query.name
                        temp_files_to_delete.append(tmp_query_path)
                    st.session_state['parsed_query_context'] = parse_query_context(tmp_query_path)
                    st.write("✅ Query Context (CSV) parsed successfully.")
                elif uploaded_query_context.name.endswith('.sql'):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as tmp_sql_query:
                        tmp_sql_query.write(uploaded_query_context.getvalue())
                        tmp_sql_query_path = tmp_sql_query.name
                        temp_files_to_delete.append(tmp_sql_query_path)
                    st.session_state['parsed_sql_query_context'] = parse_sql_query_context(tmp_sql_query_path)
                    st.write("✅ Query Context (SQL) parsed successfully.")
                else:
                    st.error("Unsupported file type for Query Context.")
                    st.session_state['parsing_errors'].append("Unsupported file type for Query Context.")

                # 3. Process Conga Template (DOCX)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_template:
                    tmp_template.write(uploaded_conga_template.getvalue())
                    tmp_template_path = tmp_template.name
                    temp_files_to_delete.append(tmp_template_path)
                st.session_state['parsed_conga_template_elements'] = extract_elements_from_docx(tmp_template_path)
                st.write("✅ Conga Template (DOCX) parsed successfully.")
                
                if not st.session_state['parsing_errors']:
                    st.success("All input files parsed successfully! Now attempting conversion...")
                    # Call the conversion engine
                    st.session_state['conversion_output'] = convert_template(
                        template_elements=st.session_state.get('parsed_conga_template_elements', []),
                        schema_mapping=st.session_state.get('parsed_schema_mapping'),
                        query_context_csv=st.session_state.get('parsed_query_context'),
                        query_context_sql=st.session_state.get('parsed_sql_query_context')
                    )
                    st.success("Conversion process completed!")
                    st.balloons() # Move balloons to after successful conversion
                else:
                    st.error("Some files parsed with issues or were unsupported.")

            except SchemaParserError as e:
                st.error(f"Schema Mapping Error: {e}")
                st.session_state['parsing_errors'].append(f"Schema Mapping: {e}")
            except CsvParserError as e:
                st.error(f"Query Context (CSV) Error: {e}")
                st.session_state['parsing_errors'].append(f"Query Context (CSV): {e}")
            except SqlParserError as e: # Added SQL parser error handling
                st.error(f"Query Context (SQL) Error: {e}")
                st.session_state['parsing_errors'].append(f"Query Context (SQL): {e}")
            except DocxParserError as e:
                st.error(f"Conga Template (DOCX) Error: {e}")
                st.session_state['parsing_errors'].append(f"Conga Template (DOCX): {e}")
            except ConversionEngineError as e: # Added Conversion Engine error handling
                st.error(f"Conversion Error: {e}")
                st.session_state['parsing_errors'].append(f"Conversion Engine: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred during parsing: {e}")
                st.session_state['parsing_errors'].append(f"Unexpected: {e}")
            finally:
                for f_path in temp_files_to_delete:
                    try:
                        os.remove(f_path)
                    except OSError:
                        st.warning(f"Could not delete temporary file: {f_path}")
        else:
            st.error("Please upload all three required files.")

with col2:
    st.header("Output Preview")
    st.write("Converted template and reports will be shown here.")
    # Placeholder for diff view and manual overrides

# --- Placeholder for displaying results --- #
st.header("Results")
if 'parsing_errors' in st.session_state and st.session_state['parsing_errors']:
        st.subheader("Parsing Issues:")
        for error_msg in st.session_state['parsing_errors']:
            st.error(error_msg)

if 'parsed_schema_mapping' in st.session_state and st.session_state['parsed_schema_mapping']:
    st.subheader("Parsed Schema Mapping Summary:")
    schema_map = st.session_state['parsed_schema_mapping']
    st.json({
        "direct_mappings_count": len(schema_map.direct_mappings),
        "type_rules_count": len(schema_map.type_rules),
        "nested_paths_count": len(schema_map.nested_paths)
    })
    # st.write(schema_map) # Display full object if needed

if 'parsed_query_context' in st.session_state and st.session_state['parsed_query_context']:
    st.subheader("Parsed Query Context Summary:")
    query_ctx = st.session_state['parsed_query_context']
    st.write(f"Number of query context rows: {len(query_ctx)}")
    if query_ctx:
        st.write("First few rows (sample):")
        # Display a few rows as a sample, convert Pydantic models to dict for st.dataframe or st.json
        sample_data = [row.model_dump() for row in query_ctx[:min(5, len(query_ctx))]]
        st.dataframe(sample_data)
    # st.write(query_ctx) # Display full list if needed

# Display parsed SQL query context if available
if 'parsed_sql_query_context' in st.session_state and st.session_state['parsed_sql_query_context']:
    st.subheader("Parsed SQL Query Context Summary:")
    sql_ctx = st.session_state['parsed_sql_query_context']
    st.write(f"Number of selected fields found: {len(sql_ctx.selected_fields)}")
    if sql_ctx.selected_fields:
        st.write("Selected Fields (first 10 shown):")
        sample_data = sql_ctx.selected_fields[:min(10, len(sql_ctx.selected_fields))]
        st.json({"fields": sample_data})
    # st.write(sql_ctx) # Display full object if needed

if 'parsed_conga_template_elements' in st.session_state and st.session_state['parsed_conga_template_elements']:
    st.subheader("Parsed Conga Template Elements Summary:")
    template_elements = st.session_state['parsed_conga_template_elements']
    st.write(f"Total elements found: {len(template_elements)}")
    merge_fields_count = sum(1 for el in template_elements if el.element_type == 'merge_field')
    control_tags_count = sum(1 for el in template_elements if el.element_type == 'control_tag')
    st.write(f"Merge Fields: {merge_fields_count}, Control Tags: {control_tags_count}")
    # st.write(template_elements) # Display full list if needed

# --- Display Conversion Engine Results --- #
if 'conversion_output' in st.session_state and st.session_state['conversion_output']:
    output = st.session_state['conversion_output']
    
    st.markdown("--- ")
    st.header("Conversion Engine Output")

    st.subheader("Converted Template (Preview)")
    # For now, converted_template might be a string or dict. Adjust display as needed.
    if isinstance(output.converted_template, dict):
        st.json(output.converted_template)
    else:
        st.text_area("Box DocGen Content (Placeholder)", value=str(output.converted_template), height=200)

    if output.mapping_report:
        st.subheader("Mapping Report")
        # Convert list of Pydantic models to list of dicts for st.dataframe
        report_data = [entry.model_dump() for entry in output.mapping_report]
        st.dataframe(report_data)
    
    if output.validation_errors:
        st.subheader("Validation Issues from Conversion")
        for error in output.validation_errors:
            st.error(f"Field: {error.field_tag if error.field_tag else 'N/A'} - Issue: {error.issue_type} - {error.message} (Severity: {error.severity})")

    if output.performance_metrics:
        st.subheader("Performance Metrics")
        st.json(output.performance_metrics.model_dump())

# --- Footer or additional info ---
# st.markdown("--- ")
# st.markdown("Developed by [Your Name/Company]")

if __name__ == '__main__':
    # This is primarily for Streamlit to run. 
    # If you need to run some setup before Streamlit, it can go here, 
    # but usually, Streamlit handles its own execution flow.
    pass
