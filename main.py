import os
import json
from typing import List, Optional, Dict, Any, Union
from dotenv import load_dotenv

# FastAPI components
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Real-Time Search Client
import arxiv 
from typing import List 

# CSL components
from citeproc import CitationStylesBibliography, CitationStylesStyle, Citation, CitationItem, formatter
from citeproc.source.json import CiteProcJSON

# LLM components (Using OpenAI SDK but pointing to Gemini API)
from openai import OpenAI 

# Load environment variables from .env file
# load_dotenv()
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_API_KEY="AIzaSyD6JS87tXziZvOSaSm93vtRph39-PIoIy8"

# --- Pydantic Schema Definitions ---
class CSLName(BaseModel):
    family: str = Field(..., description="Last name of the author.")
    given: Optional[str] = Field(None, description="First name(s) or initials.")

class CSLDate(BaseModel):
    date_parts: List[List[Union[int, str]]] 

class CitationItemSchema(BaseModel):
    """Schema for a single publication used for CSL formatting."""
    id: str = Field(..., description="Unique ID (e.g., ArXiv ID, DOI, or internal ID)")
    type: str = Field("article-journal", description="CSL type, e.g., 'article-journal', 'paper-conference'")
    title: str = Field(..., description="Title of the paper/article")
    author: List[CSLName]
    issued: CSLDate
    container_title: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    page: Optional[str] = None
    URL: Optional[str] = None

# Schema for the Search Results (Simplified CSL structure)
class PaperMetadata(BaseModel):
    id: str
    title: str
    author: List[CSLName]
    issued: CSLDate
    container_title: str
    url: str


# --- FastAPI Application Instance ---
app = FastAPI(title="Citation Generator API", version="0.1.0")


# --- Real-Time Search Endpoint (Fetches data from ArXiv) ---
@app.get("/search/papers", response_model=List[PaperMetadata], summary="Search ArXiv for papers based on a query.")
async def search_papers_endpoint(query: str):
    """Fetches the top 5 latest papers from ArXiv based on the topic query."""
    
    try:
        # NOTE: client is defined inside the function to ensure thread safety in FastAPI
        client = arxiv.Client(page_size=5, delay_seconds=1.0)
        search = arxiv.Search(
            query=query,
            max_results=5,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        results = []
        for r in client.results(search):
            
            # --- FIX FOR 'Author' object has no attribute 'last_name' ---
            authors_list = []
            for a in r.authors:
                # Safely get the full name string and split it
                name_parts = str(a).split(' ')
                authors_list.append({
                    "family": name_parts[-1], 
                    "given": ' '.join(name_parts[:-1]) if len(name_parts) > 1 else ''
                })
            # --- END FIX ---

            # 1. Map ArXiv data to your standardized CSL structure (PaperMetadata)
            paper_data = {
                "id": r.entry_id.split('/')[-1],
                "title": r.title,
                "author": authors_list, # Use the fixed authors list
                "issued": {"date_parts": [[r.published.year, r.published.month, r.published.day]]},
                "container_title": r.primary_category,
                "url": r.entry_id 
            }
            results.append(paper_data)
            
        return results
        
    except Exception as e:
        # Catch any errors during the external ArXiv API call
        print(f"FATAL ARXIV CRASH: {e}") 
        raise HTTPException(status_code=500, detail=f"ArXiv Search Failed: Check server logs for exact reason.")


# --- CSL Processing Logic (Used in Citation Fallback) ---
def generate_citation_csl(csl_data: CitationItemSchema, style_name: str) -> str:
    """Uses the CSL processor to generate a citation string (Rules-Based Core)."""
    
    # Critical data check
    if not csl_data.author or not csl_data.title or not csl_data.issued:
        return "CRITICAL_MISSING_DATA"

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
        return "CSL_PROCESSING_FAILED"


# --- LLM Fallback Logic (The Intelligent Fix) ---
def generate_citation_llm_fallback(data: Dict[str, Any], style: str) -> str:
    """Uses the Gemini LLM to generate a citation, handling missing/messy data."""
    if not GEMINI_API_KEY:
        return "LLM_ERROR: API key not configured."

    try:
        # Initialize the client, pointing the base_url to the Gemini endpoint
        client = OpenAI(
            api_key=GEMINI_API_KEY, 
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/" 
        )
        
        prompt = f"""
        You are an expert academic citation assistant. Your task is to generate a full reference list entry in the {style.upper()} format.
        The citation data provided below is messy or incomplete. Use academic best practices (e.g., 'n.d.' for no date, correctly format capitalization, use 'et al.' when appropriate) to complete and format the citation.
        
        **Data:** {json.dumps(data, indent=2)}
        
        **INSTRUCTIONS:** Generate ONLY the fully formatted, single-line reference list entry. Do not include any surrounding text, explanations, or markdown fences (e.g., ```).
        """
        
        response = client.chat.completions.create(
            model="gemini-2.5-flash", 
            messages=[
                {"role": "system", "content": "You are a specialized citation engine that formats references accurately."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        
        citation = response.choices[0].message.content.strip()
        return citation.replace("```", "").replace("json", "").replace("plaintext", "")

    except Exception as e:
        return f"LLM_ERROR: Could not generate citation. {e}"


# --- Citation Endpoint (The Hybrid Orchestrator) ---
@app.post("/generate/citation", summary="Generate a citation using a hybrid CSL/LLM approach.")
async def generate_citation_endpoint(
    item: CitationItemSchema, 
    style: str = "apa"
) -> Dict[str, Any]:
    
    # 1. Attempt CSL generation (Highest Accuracy)
    formatted_citation = generate_citation_csl(item, style.lower())
    
    # 2. Check for CSL Failure and Initiate LLM Fallback
    if "CRITICAL_MISSING_DATA" in formatted_citation or "FAILED" in formatted_citation or "NOT_FOUND" in formatted_citation:
        
        item_data = json.loads(item.json(exclude_none=True))
        fallback_citation = generate_citation_llm_fallback(item_data, style)
        
        if "LLM_ERROR" in fallback_citation:
            raise HTTPException(
                status_code=500,
                detail=f"Both CSL and LLM systems failed: {fallback_citation}"
            )
        
        return {
            "style": style.upper(),
            "citation": fallback_citation,
            "source": "LLM_FALLBACK (Intelligent Guess)",
            "source_id": item.id
        }

    # 3. Successful CSL run
    return {
        "style": style.upper(),
        "citation": formatted_citation,
        "source": "CSL_RULES (High Accuracy)",
        "source_id": item.id
    }

# This section is for local testing: runs the FastAPI app if you execute main.py directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
