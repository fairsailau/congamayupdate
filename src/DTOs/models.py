from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field

# --- 1. Schema Mapping Models (for schema_mapping.json) --- #

class NestedPathFieldMapping(BaseModel):
    """Defines field mappings within a nested path."""
    # Using Dict[str, str] for flexibility, e.g., "{{CongaTag}}": "box.field.path"
    fields: Dict[str, str] = Field(default_factory=dict)

class NestedPathDetail(BaseModel):
    """Details for a single nested path mapping."""
    source_path: str = Field(..., description="The Conga source path for the repeating section, e.g., a table row or loop.")
    fields: Dict[str, str] = Field(..., description="Mapping of Conga tags within the loop to Box fields.")

class SchemaMapping(BaseModel):
    """Represents the structure of schema_mapping.json."""
    direct_mappings: Dict[str, str] = Field(default_factory=dict, description="Direct 1:1 mappings from Conga tags to Box fields or special values.")
    type_rules: Dict[str, str] = Field(default_factory=dict, description="Rules for data type conversions, e.g., date formats, currency codes.")
    nested_paths: Dict[str, NestedPathDetail] = Field(default_factory=dict, description="Mappings for nested or repeating data structures.")


# --- 2. Query Context Models (for query_context.csv) --- #

class QueryContextRow(BaseModel):
    """Represents a single row from the query_context.csv file."""
    model_config = {"from_attributes": True}
    
    CongaField: str = Field(..., description="The field name in the Conga template")
    RelatedBoxField: Optional[str] = Field(None, description="The corresponding Box field name")
    DataType: Optional[str] = Field(None, description="The data type of the field")
    SourceTable: Optional[str] = Field(None, description="The source table for the field")


class SqlQueryContext(BaseModel):
    """Represents the extracted information from a query_context.sql file."""
    selected_fields: List[str] = Field(default_factory=list, description="List of field names extracted from the SQL SELECT statement.")


# --- 3. Conga Template Extracted Data Models --- #

class CongaTemplateElement(BaseModel):
    """Base model for any element extracted from a Conga template."""
    original_tag: str = Field(..., description="The full original tag found in the document, e.g., {{OpportunityName}} or {{TableStart:Contacts}}.")
    element_type: str # To be defined by subclasses, e.g., "merge_field", "control_tag"

class CongaMergeField(CongaTemplateElement):
    """Represents a standard Conga merge field."""
    element_type: Literal["merge_field"] = "merge_field"
    field_name: str = Field(..., description="The name of the field inside the Conga tag, e.g., OpportunityName.")

class CongaControlTag(CongaTemplateElement):
    """Represents a Conga control tag like TableStart, IF, etc."""
    element_type: Literal["control_tag"] = "control_tag"
    control_type: str = Field(..., description="The type of control, e.g., TableStart, TableEnd, IF, ENDIF.")
    parameter: Optional[str] = Field(None, description="The parameter associated with the control tag, e.g., dataset name for TableStart/End, condition for IF.")

class TextSegment(CongaTemplateElement):
    """Represents a segment of plain text in the document."""
    element_type: Literal["text"] = "text"
    content: str = Field(..., description="The plain text content of this segment.")

# This Union can be used for type hinting the output of the docx_parser
ParsedTemplateElement = Union[CongaMergeField, CongaControlTag, TextSegment]


# --- 4. Output Models (for the final JSON response) --- #

class MappingReportEntry(BaseModel):
    """An entry in the field-level conversion audit report."""
    conga_tag: str
    box_tag: Optional[str] = None
    conversion_method: str # e.g., "Direct Mapping", "Query Relationship", "AI Inference", "Unmapped"
    confidence_score: Optional[float] = None # For AI-inferred mappings or fallbacks
    notes: Optional[str] = None

class PerformanceMetrics(BaseModel):
    """Token usage and other performance statistics."""
    total_input_tokens: Optional[int] = None # If AI processing is involved for inference
    template_chunks_processed: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    # Add other relevant metrics

class ValidationError(BaseModel):
    """Details of an unresolved issue or unmapped field."""
    field_tag: Optional[str] = None # Original Conga tag if applicable
    issue_type: str # e.g., "Unmapped Field", "Type Conversion Failed", "Logic Error"
    message: str
    severity: str = Field("warning", description="Could be 'error' or 'warning'")
    original_conga_context: Optional[str] = None # e.g., the Conga tag as a comment

class ConvertedTemplate(BaseModel):
    """Structure for the converted Box DocGen template. 
       This might be a string (for simple cases) or a more complex structure if Box DocGen supports it.
       For now, assuming it could be a dictionary representing JSON structure.
    """
    # Option 1: Simple string (if output is just a text-based template with Box tags)
    # content: str
    
    # Option 2: More structured JSON object for Box DocGen (if applicable)
    # This is a placeholder, Box DocGen's actual schema would dictate this.
    version: str = "1.0"
    document: Dict[str, Any] # Placeholder for Box DocGen's specific JSON structure

class ConversionOutput(BaseModel):
    """The final JSON output structure for the conversion process."""
    # Using Any for converted_template initially. We'll refine this once Box DocGen's format is clearer.
    # It might be a string containing the new template, or a more structured JSON object for Box DocGen.
    converted_template: Any # This will likely be a JSON string or a Dict for Box DocGen
    mapping_report: List[MappingReportEntry] = []
    performance_metrics: PerformanceMetrics
    validation_errors: List[ValidationError] = []
    # Adding the Box JSON schema as per requirements
    box_json_schema_export: Optional[Dict[str, Any]] = Field(None, description="Exported Box JSON schema with conversion metadata")


if __name__ == '__main__':
    # Example usage for testing the models (optional)
    sample_schema_data = {
        "direct_mappings": {
            "{{DocumentDate}}": "current_date",
            "{{SenderName}}": "sender.full_name"
        },
        "type_rules": {
            "date": "YYYY-MM-DD"
        },
        "nested_paths": {
            "opportunity.line_items": {
                "source_path": "TableStart:LineItems",
                "fields": {
                    "{{ProductName}}": "name",
                    "{{Quantity}}": "quantity"
                }
            }
        }
    }
    schema = SchemaMapping(**sample_schema_data)
    print("SchemaMapping Example:", schema.model_dump_json(indent=2))

    sample_query_row_data = {
        "CongaField": "{{OpportunityName}}",
        "RelatedBoxField": "opportunity.name",
        "DataType": "string",
        "SourceTable": "Opportunity"
    }
    query_row = QueryContextRow(**sample_query_row_data)
    print("\nQueryContextRow Example:", query_row.model_dump_json(indent=2))

    sample_output_data = {
        "converted_template": {"document": {"title": "Converted Document", "content": "Hello {{box.name}}"}},
        "mapping_report": [
            {
                "conga_tag": "{{OpportunityName}}", 
                "box_tag": "opportunity.name", 
                "conversion_method": "Direct Mapping",
                "confidence_score": 1.0
            }
        ],
        "performance_metrics": {
            "template_chunks_processed": 10,
            "processing_time_seconds": 5.2
        },
        "validation_errors": [
            {
                "field_tag": "{{LegacyField}}",
                "issue_type": "Unmapped Field",
                "message": "No mapping rule found for this field.",
                "severity": "warning",
                "original_conga_context": "<!-- CongaTag: {{LegacyField}} -->"
            }
        ],
        "box_json_schema_export": {
            "schema_version": "v1", 
            "fields": [{"name": "opportunity.name", "type": "string"}]
        }
    }
    output = ConversionOutput(**sample_output_data)
    print("\nConversionOutput Example:", output.model_dump_json(indent=2))
