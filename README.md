# Conga to Box DocGen Converter

This Streamlit application converts Conga templates to Box DocGen format based on provided context sources (template analysis, query context, and schema mapping).

## Project Structure

```
conga_to_box_converter/
├── app.py                   # Main Streamlit application file
├── requirements.txt         # Python dependencies
├── README.md                # Project overview and setup instructions
├── input_data/              # Directory for user-provided input files
│   ├── conga_template.docx  # Placeholder for Conga template
│   ├── query_context.csv    # Placeholder for Query context (CSV example)
│   └── schema_mapping.json  # Placeholder for Schema mapping
├── src/
│   ├── __init__.py
│   ├── parsers/             # Modules for parsing input files
│   │   ├── __init__.py
│   │   ├── docx_parser.py
│   │   ├── csv_parser.py
│   │   └── json_parser.py
│   ├── converter/           # Core conversion logic
│   │   ├── __init__.py
│   │   └── conga_to_box.py
│   ├── utils/               # Utility functions
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── DTOs/                # Data Transfer Objects / Pydantic Models
│       ├── __init__.py
│       └── models.py
└── output_data/             # Directory for generated output files
    ├── converted_template.json
    └── mapping_report.json
```

## Setup and Installation

1.  **Clone the repository (if applicable) or create the project directory.**

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Place your Conga template (`.docx`), query context (`.csv` or `.sql`), and schema mapping (`.json`) files into the `input_data/` directory or use the file uploaders in the application.
2.  Run the Streamlit application:
    ```bash
    streamlit run app.py
    ```
3.  Follow the instructions in the application to upload files and start the conversion process.

## Development

(Add notes here about development, testing, etc. as the project evolves)
