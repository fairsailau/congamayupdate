from typing import List, Optional, Dict, Any
from ..DTOs.models import (
    SchemaMapping,
    QueryContextRow,
    SqlQueryContext,
    ParsedTemplateElement,
    CongaMergeField,
    CongaControlTag,
    TextSegment,
    ConversionOutput,
    MappingReportEntry,
    PerformanceMetrics,
    ValidationError
)

def convert_template(
    template_elements: List[ParsedTemplateElement],
    schema_mapping: Optional[SchemaMapping] = None,
    query_context_csv: Optional[List[QueryContextRow]] = None,
    query_context_sql: Optional[SqlQueryContext] = None
) -> ConversionOutput:
    """
    Converts a list of parsed template elements from Conga to Box DocGen format.
    
    Args:
        template_elements: List of parsed elements from the Conga template.
        schema_mapping: Optional schema mapping for direct field mappings.
        query_context_csv: Optional query context from CSV.
        query_context_sql: Optional query context from SQL.
        
    Returns:
        ConversionOutput object containing the converted template and metadata.
    """
    # Initialize data structures
    processed_tags_for_template_content = []
    mapping_report = []
    validation_errors = []
    open_block_parameters_stack = []  # To track nested blocks (TableStart/End, IF/ENDIF)
    
    # Process each element in the template
    for element in template_elements:
        box_tag_found: Optional[str] = None
        conversion_method: str = "Unmapped"
        notes: Optional[str] = None
        
        # Handle TextSegment (pass through directly)
        if isinstance(element, TextSegment):
            processed_tags_for_template_content.append(element.content)
            continue
            
        # Handle CongaMergeField
        elif isinstance(element, CongaMergeField):
            conga_tag = element.original_tag
            field_name = element.field_name
            
            # 1. Try Direct Mapping from schema_mapping.json
            if schema_mapping and schema_mapping.direct_mappings and field_name in schema_mapping.direct_mappings:
                box_tag = schema_mapping.direct_mappings[field_name]
                box_tag_found = f"{{{{{box_tag}}}}}"  # Wrap in Box mustache syntax
                conversion_method = "Direct Mapping"
                notes = f"Mapped from Conga field: {field_name}"
            
            # 2. Try to find in query context (CSV or SQL)
            elif query_context_csv:
                # Look for the field in the query context
                for row in query_context_csv:
                    if row.CongaField == field_name and row.RelatedBoxField:
                        box_tag = row.RelatedBoxField
                        box_tag_found = f"{{{{{box_tag}}}}}"  # Wrap in Box mustache syntax
                        conversion_method = "Query Context (CSV)"
                        notes = f"Mapped from query context CSV: {field_name} -> {box_tag}"
                        break
            
            # 3. If not found, keep the original tag but mark as unmapped
            if not box_tag_found:
                box_tag_found = conga_tag  # Keep original Conga tag
                conversion_method = "Unmapped"
                notes = f"No mapping found for field: {field_name}"
                validation_errors.append(
                    ValidationError(
                        field_tag=conga_tag,
                        issue_type="Unmapped Field",
                        message=f"No mapping found for field: {field_name}",
                        severity="warning"
                    )
                )
            
            # Add to the output
            processed_tags_for_template_content.append(box_tag_found)
            
            # Add to mapping report
            mapping_report.append(
                MappingReportEntry(
                    conga_tag=conga_tag,
                    box_tag=box_tag_found,
                    conversion_method=conversion_method,
                    notes=notes
                )
            )
        
        # Handle CongaControlTag
        elif isinstance(element, CongaControlTag):
            conga_tag = element.original_tag
            control_type = element.control_type
            parameter = element.parameter
            
            if control_type in ["TableStart", "IF"]:
                if not parameter:
                    validation_errors.append(
                        ValidationError(
                            field_tag=conga_tag,
                            issue_type="Missing Parameter",
                            message=f"Control tag {control_type} is missing a required parameter",
                            severity="error"
                        )
                                       )
                    processed_tags_for_template_content.append(conga_tag)
                    continue
                
                # Push to stack and add opening tag
                open_block_parameters_stack.append(parameter)
                box_tag = f"{{{{#{parameter}}}}}"  # Box opening tag
                conversion_method = f"Control Tag: {control_type}"
                notes = f"Opening block for {parameter}"
                
            elif control_type in ["TableEnd", "ENDIF"]:
                if not open_block_parameters_stack:
                    validation_errors.append(
                        ValidationError(
                            field_tag=conga_tag,
                            issue_type="Unexpected Block End",
                            message=f"Found {control_type} without matching opening tag",
                            severity="error"
                        )
                    )
                    processed_tags_for_template_content.append(conga_tag)
                    continue
                
                # Pop from stack and add closing tag
                expected_parameter = open_block_parameters_stack.pop()
                if parameter and parameter != expected_parameter:
                    notes = f"Parameter mismatch: expected {expected_parameter}, got {parameter}"
                    validation_errors.append(
                        ValidationError(
                            field_tag=conga_tag,
                            issue_type="Parameter Mismatch",
                            message=notes,
                            severity="warning"
                        )
                    )
                
                box_tag = f"{{{{/{expected_parameter or ''}}}}}"  # Box closing tag
                conversion_method = f"Control Tag: {control_type}"
                notes = f"Closing block for {expected_parameter}"
            else:
                # Unknown control tag type
                box_tag = conga_tag
                conversion_method = "Unhandled Control Tag"
                notes = f"Unhandled control tag type: {control_type}"
                validation_errors.append(
                    ValidationError(
                        field_tag=conga_tag,
                        issue_type="Unhandled Control Tag",
                        message=f"Unhandled control tag type: {control_type}",
                        severity="warning"
                    )
                )
            
            # Add to the output
            processed_tags_for_template_content.append(box_tag)
            
            # Add to mapping report
            mapping_report.append(
                MappingReportEntry(
                    conga_tag=conga_tag,
                    box_tag=box_tag,
                    conversion_method=conversion_method,
                    notes=notes
                )
            )
        
        # Handle unknown element types
        else:
            processed_tags_for_template_content.append(str(element))
            validation_errors.append(
                ValidationError(
                    field_tag=str(element),
                    issue_type="Unknown Element Type",
                    message=f"Element of type {type(element).__name__} is not supported",
                    severity="error"
                )
            )
    
    # Check for unclosed blocks
    for param in reversed(open_block_parameters_stack):
        validation_errors.append(
            ValidationError(
                field_tag=f"{{{{#TableStart:{param}}}}}",
                issue_type="Unclosed Block",
                message=f"Block for parameter '{param}' was never closed",
                severity="error"
            )
        )
    
    # Combine all processed tags into the final template
    converted_template = "".join(processed_tags_for_template_content)
    
    # Create and return the conversion output
    return ConversionOutput(
        converted_template=converted_template,
        mapping_report=mapping_report,
        validation_errors=validation_errors,
        performance_metrics=PerformanceMetrics()  # Add actual metrics if needed
    )
