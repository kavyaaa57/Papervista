import os
import json
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# FastAPI and Pydantic components
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# CSL components
from citeproc import CitationStylesBibliography, CitationStylesStyle, Citation, CitationItem, formatter
from citeproc.source.json import CiteProcJSON

# LLM components (Using OpenAI SDK but pointing to Gemini API)
from openai import OpenAI 

# Load environment variables from .env file
# This loads your GEMINI_API_KEY
# load_dotenv()
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_API_KEY="AIzaSyD6JS87tXziZvOSaSm93vtRph39-PIoIy8"

print(f"DEBUG: Key status (First 5 chars): {GEMINI_API_KEY[:5]}")



app = FastAPI(title="Citation Generator API")

# --- Pydantic Schema (Input Validation) ---
# This ensures that data coming in from the Explorer is structured.
class CSLName(BaseModel):
    family: str = Field(..., description="Last name of the author.")
    given: Optional[str] = Field(None, description="First name(s) or initials.")

class CSLDate(BaseModel):
    date_parts: List[List[int]]

class CitationItemSchema(BaseModel):
    id: str = Field(..., description="Unique ID (e.g., DOI or internal ID)")
    type: str = Field("article-journal", description="CSL type, e.g., 'article-journal', 'book', 'webpage'")
    title: str = Field(..., description="Title of the paper/article")
    author: List[CSLName]
    issued: CSLDate
    container_title: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    page: Optional[str] = None
    URL: Optional[str] = None


# --- Core Citation Generation Logic (CSL Rules) ---
def generate_citation_csl(csl_data: CitationItemSchema, style_name: str) -> str:
    """Uses the CSL processor to generate a citation string."""
    
    # Check for critical missing data that even CSL might struggle with
    if not csl_data.author or not csl_data.title or not csl_data.issued:
        return "CRITICAL_MISSING_DATA"

    # Convert Pydantic model to a dict list required by CiteProc
    data_dict = [json.loads(csl_data.json(exclude_none=True))]
    style_path = os.path.join("csl_styles", f"{style_name}.csl")
    
    if not os.path.exists(style_path):
        return f"CSL_STYLE_NOT_FOUND"

    try:
        source = CiteProcJSON(data_dict)
        style = CitationStylesStyle(style_path, validate=False)
        bib = CitationStylesBibliography(style, source, formatter.html) 

        bib.register(Citation([CitationItem(csl_data.id)]))
        
        bibliography_output = list(bib.bibliography())
        
        if bibliography_output:
            return str(bibliography_output[0])
        
        return "CSL_PROCESSING_FAILED"

    except Exception:
        # Catch any structural errors during CSL processing
        return "CSL_PROCESSING_FAILED"


# --- Agentic AI / LLM Fallback Function (Gemini) ---
def generate_citation_llm_fallback(data: Dict[str, Any], style: str) -> str:
    """Uses the Gemini LLM to generate a citation, handling missing/messy data."""
    if not GEMINI_API_KEY:
        # This will happen if you did not paste your key into .env
        return "LLM_ERROR: API key not configured."

    try:
        # Initialize the client, pointing the base_url to the Gemini endpoint
        client = OpenAI(
            api_key=GEMINI_API_KEY, 
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/" 
        )
        
        # This prompt is the intelligence layer
        prompt = f"""
        You are an expert academic citation assistant. Your task is to generate a full reference list entry in the {style.upper()} format.
        The citation data provided below is messy or incomplete. Use academic best practices (e.g., 'n.d.' for no date, correctly format capitalization, use 'et al.' when appropriate) to complete and format the citation.
        
        **Data:** {json.dumps(data, indent=2)}
        
        **INSTRUCTIONS:** Generate ONLY the fully formatted, single-line reference list entry. Do not include any surrounding text, explanations, or markdown fences (e.g., ```).
        """
        
        response = client.chat.completions.create(
            # Use a fast, free-tier model suitable for structured text generation
            model="gemini-2.5-flash", 
            messages=[
                {"role": "system", "content": "You are a specialized citation engine that formats references accurately."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0 # Set to 0.0 for deterministic, factual output (no creativity)
        )
        
        # Clean up the output to remove potential markdown artifacts
        citation = response.choices[0].message.content.strip()
        return citation.replace("```", "").replace("json", "").replace("plaintext", "")

    except Exception as e:
        return f"LLM_ERROR: Could not generate citation. {e}"


# --- FastAPI Endpoint: The Hybrid Orchestrator ---
@app.post("/generate/citation", summary="Generate a citation using a hybrid CSL/LLM approach.")
async def generate_citation_endpoint(
    item: CitationItemSchema, 
    style: str = "apa"
) -> Dict[str, Any]:
    
    # 1. Attempt CSL generation (Highest Accuracy)
    formatted_citation = generate_citation_csl(item, style.lower())
    
    # 2. Check for CSL Failure
    if "CRITICAL_MISSING_DATA" in formatted_citation or "FAILED" in formatted_citation or "NOT_FOUND" in formatted_citation:
        
        # Prepare the data dictionary for the LLM
        item_data = json.loads(item.json(exclude_none=True))
        
        # Initiate LLM Fallback
        fallback_citation = generate_citation_llm_fallback(item_data, style)
        
        if "LLM_ERROR" in fallback_citation:
            # Both systems failed; return a detailed error
            raise HTTPException(
                status_code=500,
                detail=f"Both CSL and LLM systems failed: {fallback_citation}"
            )
        
        # Return the LLM's fallback result
        return {
            "style": style.upper(),
            "citation": fallback_citation,
            "source": "LLM_FALLBACK (Intelligent Guess)",
            "source_id": item.id
        }

    # 3. Successful CSL run (Best outcome)
    return {
        "style": style.upper(),
        "citation": formatted_citation,
        "source": "CSL_RULES (High Accuracy)",
        "source_id": item.id
    }

# Run the app directly for testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)