from typing import List, Dict, Any, Optional
from ..DTOs.models import (
    SchemaMapping,
    QueryContextRow,
    SqlQueryContext,
    ParsedTemplateElement,
    CongaMergeField, # Explicitly import for isinstance checks
    CongaControlTag, # Explicitly import for isinstance checks
    TextSegment,     # Explicitly import for isinstance checks
    ConversionOutput,
    MappingReportEntry,
    PerformanceMetrics,
    ValidationError
)

class ConversionEngineError(Exception):
    """Custom exception for conversion engine errors."""
    pass

def convert_template(
    template_elements: List[ParsedTemplateElement],
    schema_mapping: Optional[SchemaMapping],
    query_context_csv: Optional[List[QueryContextRow]],
    query_context_sql: Optional[SqlQueryContext]
) -> ConversionOutput:
    """
    Main function to convert Conga template elements to Box DocGen format.

    Args:
        template_elements: A list of parsed elements from the Conga template.
        schema_mapping: The parsed schema mapping rules.
        query_context_csv: Parsed data from a CSV query context file.
        query_context_sql: Parsed data from an SQL query context file.

    Returns:
        A ConversionOutput object containing the converted template, reports, and metrics.
    """
    # Initialize output components
    processed_tags_for_template_content: List[str] = []
    mapping_report: List[MappingReportEntry] = []
    validation_errors: List[ValidationError] = []
    performance_metrics = PerformanceMetrics(processing_time_seconds=0.0) # Basic initialization
    open_block_parameters_stack: List[str] = []

    if not template_elements:
        validation_errors.append(
            ValidationError(
                issue_type="No Template Content",
                message="The uploaded Conga template appears to be empty or no elements were extracted.",
                severity="warning"
            )
        )
        # Early exit if no elements to process
        return ConversionOutput(
            converted_template="", # Empty template
            mapping_report=mapping_report,
            performance_metrics=performance_metrics,
            validation_errors=validation_errors
        )

    # --- Core conversion logic --- 
    for element in template_elements:
        box_tag_found: Optional[str] = None
        conversion_method: str = "Unmapped"
        notes: Optional[str] = None

        # Handle TextSegment (pass through directly)
        if isinstance(element, TextSegment):
            processed_tags_for_template_content.append(element.content)
            # No need to add to mapping report for plain text
            continue
            
        # Handle CongaMergeField
        elif isinstance(element, CongaMergeField):
            conga_tag = element.original_tag
            # 1. Try Direct Mapping from schema_mapping.json
            if schema_mapping and schema_mapping.direct_mappings and conga_tag in schema_mapping.direct_mappings:
                box_tag_found = schema_mapping.direct_mappings[conga_tag]
                conversion_method = "Direct Mapping (Schema)"
            
            # 2. Try Query Context (CSV) if not found by direct mapping
            elif query_context_csv:
                for qc_row in query_context_csv:
                    if qc_row.CongaField == conga_tag and qc_row.RelatedBoxField:
                        box_tag_found = qc_row.RelatedBoxField
                        conversion_method = "Query Context (CSV)"
                        notes = f"Data Type: {qc_row.DataType or 'N/A'}, Source: {qc_row.SourceTable or 'N/A'}"
                        break # Found in CSV context
            
            # 3. Handle SQL Query Context (Placeholder for future enhancement)
            # elif query_context_sql and conga_tag in query_context_sql.selected_fields:
            # This comparison is too simplistic. SQL context needs more sophisticated handling.
            # For now, we'll rely on schema or CSV for merge fields.

            if box_tag_found:
                # Ensure the Box tag is in {{FieldName}} format.
                # Check if it's already a fully formed tag (e.g., a special value from schema like 'current_date')
                # or if it's a field path that needs wrapping.
                # For simplicity, we assume schema_mapping might provide field paths or special keywords.
                # Special keywords like 'current_date' usually aren't tags themselves but values.
                # So, generally, we wrap the box_tag_found unless it's a pre-formatted tag.
                if box_tag_found.startswith("{{") and box_tag_found.endswith("}}"):
                    processed_tags_for_template_content.append(box_tag_found)
                else:
                    processed_tags_for_template_content.append(f"{{{{{box_tag_found}}}}}") # Wrap in {{ }}
            else:
                processed_tags_for_template_content.append(conga_tag) # Keep original if unmapped (already in {{CongaTag}} format)
                validation_errors.append(
                    ValidationError(
                        field_tag=conga_tag,
                        issue_type="Unmapped Merge Field",
                        message=f"Merge field '{conga_tag}' could not be mapped using available rules.",
                        severity="warning"
                    )
                )
            
            mapping_report.append(
                MappingReportEntry(
                    conga_tag=conga_tag,
                    box_tag=box_tag_found,
                    conversion_method=conversion_method,
                    notes=notes
                )
            )

        elif isinstance(element, CongaControlTag):
            conga_tag = element.original_tag
            box_equivalent_tag: Optional[str] = None
            current_conversion_method = "Control Tag (Unhandled)"
            current_notes = f"Control Type: {element.control_type}, Param: {element.parameter or 'N/A'}. This type is not yet fully handled."

            parameter_name = element.parameter # For TableStart, IF, and potentially TableEnd

            if element.control_type == "TableStart" or element.control_type == "IF":
                if parameter_name:
                    open_block_parameters_stack.append(parameter_name)
                    box_equivalent_tag = f"{{{{#{parameter_name}}}}}"
                    block_type_text = "Table Section Start" if element.control_type == "TableStart" else "Conditional Block Start"
                    current_conversion_method = f"{element.control_type} to Box {block_type_text}"
                    current_notes = f"Maps to Box {block_type_text} for '{parameter_name}'."
                    processed_tags_for_template_content.append(box_equivalent_tag)
                else:
                    validation_errors.append(ValidationError(
                        field_tag=conga_tag,
                        issue_type="Missing Parameter",
                        message=f"{element.control_type} tag '{conga_tag}' is missing its required parameter.",
                        severity="error"
                    ))
                    processed_tags_for_template_content.append(conga_tag) # Fallback
                    current_notes = f"Missing parameter for {element.control_type} tag."
            
            elif element.control_type == "TableEnd" or element.control_type == "ENDIF":
                expected_block_type = "Table" if element.control_type == "TableEnd" else "IF"
                if open_block_parameters_stack:
                    popped_parameter = open_block_parameters_stack.pop()
                    # Conga's TableEnd often has a parameter, ENDIF usually doesn't.
                    # For TableEnd, optionally validate if element.parameter matches popped_parameter
                    if element.control_type == "TableEnd" and parameter_name and parameter_name != popped_parameter:
                        validation_errors.append(ValidationError(
                            field_tag=conga_tag,
                            issue_type="Mismatched Block End",
                            message=f"{element.control_type} tag '{conga_tag}' parameter '{parameter_name}' does not match open block '{popped_parameter}'. Using '{popped_parameter}'.",
                            severity="warning"
                        ))
                        current_notes = f"Mismatched {expected_block_type} end parameter. Expected '{popped_parameter}', got '{parameter_name}'. Closed '{popped_parameter}'."
                    else:
                        current_notes = f"Closes {expected_block_type} block for '{popped_parameter}'."
                    
                    box_equivalent_tag = f"{{{{/{popped_parameter}}}}}"
                    current_conversion_method = f"{element.control_type} to Box Block End"
                    processed_tags_for_template_content.append(box_equivalent_tag)
                else:
                    validation_errors.append(ValidationError(
                        field_tag=conga_tag,
                        issue_type="Unexpected Block End",
                        message=f"{element.control_type} tag '{conga_tag}' found without a matching open block.",
                        severity="error"
                    ))
                    processed_tags_for_template_content.append(conga_tag) # Fallback
                    current_notes = f"Unexpected {expected_block_type} end tag."
            
            else:
                # Default handling for other/unknown control tags
                # Keep original tag but log it as unhandled
                processed_tags_for_template_content.append(conga_tag)
                current_notes = f"Unhandled control tag type: {element.control_type}"

            mapping_report.append(
                MappingReportEntry(
                    conga_tag=conga_tag,
                    box_tag=box_equivalent_tag,
                    conversion_method=current_conversion_method,
                    notes=current_notes
                )
            )
        else:
            # Unknown element type (shouldn't happen with current implementation)
            processed_tags_for_template_content.append(element.original_tag) # Keep original tag
            mapping_report.append(
                MappingReportEntry(
                    conga_tag=element.original_tag,
                    box_tag=None,
                    conversion_method="Unknown Element Type",
                    notes=f"This element type is not explicitly handled: {element.element_type}"
                )
            )
            validation_errors.append(
                ValidationError(
                    field_tag=element.original_tag,
                    issue_type="Unknown Element",
                    message=f"Element '{element.original_tag}' has an unhandled type: {element.element_type}",
                    severity="error"
                )
            )

    # After processing all elements, check for unclosed blocks
    if open_block_parameters_stack:
        for unclosed_param in open_block_parameters_stack:
            validation_errors.append(ValidationError(
                field_tag=f"(Unclosed Block: {unclosed_param})",
                issue_type="Unclosed Block",
                message=f"Block '{unclosed_param}' was opened (TableStart or IF) but never closed with a corresponding TableEnd or ENDIF.",
                severity="error"
            ))

    converted_template_content = " ".join(processed_tags_for_template_content)
    
    # Simulate some processing time
    import time
    start_time = time.time()
    # Simulate work
    time.sleep(0.1) 
    end_time = time.time()
    performance_metrics.processing_time_seconds = round(end_time - start_time, 3)

    return ConversionOutput(
        converted_template=converted_template_content,
        mapping_report=mapping_report,
        performance_metrics=performance_metrics,
        validation_errors=validation_errors,
        # box_json_schema_export will be handled later
    )

if __name__ == '__main__':
    # Example usage for testing the conversion engine directly (highly simplified)
    from ..DTOs.models import CongaMergeField # For creating dummy data

    print("--- Testing Conversion Engine (Placeholder) ---")
    dummy_elements = [
        CongaMergeField(original_tag="{{OpportunityName}}", field_name="OpportunityName"),
        CongaMergeField(original_tag="{{ContactEmail}}", field_name="ContactEmail")
    ]
    # Create minimal dummy data for other inputs if needed for basic testing
    dummy_schema = SchemaMapping(direct_mappings={"{{OpportunityName}}": "opportunity.name"})

    try:
        output = convert_template(
            template_elements=dummy_elements, 
            schema_mapping=dummy_schema, 
            query_context_csv=None, 
            query_context_sql=None
        )
        print("Conversion Output:")
        print(output.model_dump_json(indent=2))
    except ConversionEngineError as e:
        print(f"Conversion Engine Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
