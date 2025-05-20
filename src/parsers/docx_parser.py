import re
from typing import List, Union, BinaryIO
from docx import Document

# Assuming DTOs.models is in ..DTOs.models relative to src.parsers.docx_parser
from ..DTOs.models import CongaMergeField, CongaControlTag, TextSegment, ParsedTemplateElement 

class DocxParserError(Exception):
    """Custom exception for DOCX parsing errors."""
    pass

# Regex to find Conga tags: {{...}}
# It captures the content inside the double curly braces.
CONGA_TAG_REGEX = r"\{\{([^}]+)\}\}"  # For python: r"{{([^}]+)}}"

def _parse_tag_content(full_tag: str, inner_content: str) -> ParsedTemplateElement:
    """
    Parses the inner content of a Conga tag to determine if it's a merge field or control tag.
    """
    inner_content_stripped = inner_content.strip()
    if ":" in inner_content_stripped:
        parts = inner_content_stripped.split(":", 1)
        control_type = parts[0].strip()
        parameter = parts[1].strip() if len(parts) > 1 else None
        return CongaControlTag(
            original_tag=full_tag,
            control_type=control_type,
            parameter=parameter
        )
    else:
        return CongaMergeField(
            original_tag=full_tag,
            field_name=inner_content_stripped
        )

def _extract_elements_from_text(text: str) -> List[ParsedTemplateElement]:
    """
    Extracts all Conga tags and text segments from a given string of text.
    """
    elements: List[ParsedTemplateElement] = []
    last_end = 0
    
    # Find all tag matches in the text
    for match in re.finditer(CONGA_TAG_REGEX, text):
        # Add any text before the current tag as a TextSegment
        if match.start() > last_end:
            text_before = text[last_end:match.start()]
            if text_before.strip():  # Only add non-whitespace text segments
                elements.append(TextSegment(
                    original_tag=text_before,
                    content=text_before
                ))
        
        # Process the tag itself
        full_tag = match.group(0)      # e.g., {{FieldName}} or {{TableStart:Contacts}}
        inner_content = match.group(1)  # e.g., FieldName or TableStart:Contacts
        
        try:
            element = _parse_tag_content(full_tag, inner_content)
            elements.append(element)
        except Exception as e: 
            print(f"Warning: Could not parse tag content for '{full_tag}'. Error: {e}")
            # If parsing fails, keep the original tag as a text segment
            elements.append(TextSegment(
                original_tag=full_tag,
                content=full_tag
            ))
        
        last_end = match.end()
    
    # Add any remaining text after the last tag
    if last_end < len(text):
        remaining_text = text[last_end:]
        if remaining_text.strip():  # Only add non-whitespace text segments
            elements.append(TextSegment(
                original_tag=remaining_text,
                content=remaining_text
            ))
    
    return elements

def extract_elements_from_docx(file_path_or_uploaded_file: Union[str, BinaryIO]) -> List[ParsedTemplateElement]:
    """
    Parses a .docx Conga template to extract merge fields and control tags.

    Args:
        file_path_or_uploaded_file: Either a file path (str) or a file-like object (e.g., from Streamlit file_uploader).

    Returns:
        A list of ParsedTemplateElement objects (CongaMergeField or CongaControlTag or TextSegment).
        Returns an empty list if no tags are found or if the document is empty.
        
    Raises:
        DocxParserError: If the file cannot be read or if there's an issue with the docx format.
    """
    try:
        # Handle both file path strings and file-like objects (e.g., from Streamlit file_uploader)
        if isinstance(file_path_or_uploaded_file, str):
            # It's a file path
            document = Document(file_path_or_uploaded_file)
        else:
            # It's a file-like object (e.g., from Streamlit file_uploader)
            # Save to a temporary file and then open it
            import tempfile
            import os
            import io
            
            # For file-like objects, we need to handle both BytesIO and other file-like objects
            if hasattr(file_path_or_uploaded_file, 'read'):
                # If it's a file-like object, read its content
                file_content = file_path_or_uploaded_file.read()
                if hasattr(file_path_or_uploaded_file, 'seek'):
                    file_path_or_uploaded_file.seek(0)  # Reset file pointer if possible
            else:
                raise DocxParserError("Unsupported file input type")
            
            # Create a temporary file with the correct extension
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                # Write the uploaded file's content to the temporary file
                if isinstance(file_content, str):
                    tmp.write(file_content.encode('utf-8'))
                else:
                    tmp.write(file_content)
                tmp_path = tmp.name
                
            try:
                # Open the temporary file
                document = Document(tmp_path)
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass  # Ignore errors during cleanup
                    
    except FileNotFoundError:
        raise DocxParserError(f"Error: DOCX template file not found at {file_path_or_uploaded_file}")
    except Exception as e:  # Catches other errors from python-docx like bad format
        raise DocxParserError(f"Error: Could not read or open DOCX template. Details: {e}")

    all_elements: List[ParsedTemplateElement] = []

    # Process paragraphs
    for para in document.paragraphs:
        if para.text.strip():  # Only process non-empty paragraphs
            all_elements.extend(_extract_elements_from_text(para.text))
            # Add a newline to separate paragraphs
            all_elements.append(TextSegment(
                original_tag="\n",
                content="\n"
            ))

    # Process tables
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                # Each cell can contain multiple paragraphs
                for para_in_cell in cell.paragraphs:
                    if para_in_cell.text.strip():
                        all_elements.extend(_extract_elements_from_text(para_in_cell.text))
                # Add a tab or other separator between cells
                all_elements.append(TextSegment(
                    original_tag="\t",
                    content="\t"
                ))
            # Add a newline after each row
            all_elements.append(TextSegment(
                original_tag="\n",
                content="\n"
            ))
    
    return all_elements

if __name__ == '__main__':
    import os
    import sys
    from pprint import pprint
    
    # Simple test if run directly
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            try:
                elements = extract_elements_from_docx(file_path)
                print(f"Extracted {len(elements)} elements:")
                for elem in elements:
                    if isinstance(elem, TextSegment):
                        print(f"Text: {repr(elem.content)}")
                    else:
                        print(f"Tag: {elem.original_tag} (Type: {type(elem).__name__})")
            except Exception as e:
                print(f"Error: {e}")
        else:
            print(f"File not found: {file_path}")
    else:
        print("Usage: python docx_parser.py <path_to_docx_file>")
