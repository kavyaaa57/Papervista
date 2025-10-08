import requests
import json
import argparse
from typing import Dict, Any

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"

# --- Placeholder Data Function ---
def get_paper_data(paper_id: str) -> Dict[str, Any]:
    """
    Simulates fetching a paper's structured metadata (from your original Explorer database).
    This uses the same data that successfully ran your API test.
    """
# --- Placeholder Data Function (UPDATED) ---
def get_paper_data(paper_id: str) -> Dict[str, Any]:
    """
    Simulates: Retrieving standardized CSL-JSON data from your project's internal database.
    (This function must contain ALL data that the CLI client can request.)
    """
    
    # Database containing the available papers:
    DATABASE = {
        # 1. YOUR ORIGINAL PROJECT PAPER
        "711722243044": {
            "id": "711722243044",
            "type": "article-journal",
            "title": "AI Research Paper Explorer: Leveraging RAG for Persistent Research Memory",
            "author": [
                { "family": "ANISHA", "given": "Z." },
                { "family": "JANANI", "given": "K." }
            ],
            "issued": { "date_parts": [[2025, 10, 8]] },
            "container_title": "Journal of Artificial Intelligence & Data Science",
            "volume": "10",
            "issue": "2",
            "page": "15-30",
            "URL": "http://example-kite.edu/paper-09"
        },
        
        # 2. THE REAL-WORLD ATTENTION PAPER (NIPS 2017)
        "VASWANI_2017": {
            "id": "VASWANI_2017",
            "type": "paper-conference",
            "title": "Attention Is All You Need",
            "author": [
                { "family": "Vaswani", "given": "Ashish" },
                { "family": "Shazeer", "given": "Noam M." },
                { "family": "Parmar", "given": "Niki" },
                { "family": "Uszkoreit", "given": "Jakob" },
                { "family": "Jones", "given": "Llion" },
                { "family": "Gomez", "given": "Aidan N." },
                { "family": "Kaiser", "given": "Łukasz" },
                { "family": "Polosukhin", "given": "Illia" }
            ],
            "issued": { "date_parts": [[2017]] },
            "container_title": "Advances in Neural Information Processing Systems 30 (NIPS 2017)",
            "page": "5998-6008",
            "URL": "https://arxiv.org/abs/1706.03762"
        }
    }
    
    # Look up the ID in the database
    if paper_id in DATABASE:
        return DATABASE[paper_id]
    else:
        raise ValueError(f"Paper ID {paper_id} not found in database.")

# --- Rest of the explorer_cli.py code remains the same ---

# --- Core CLI Functionality ---
def cite_paper_cli(paper_id: str, style: str):
    """
    Retrieves paper data and calls the local FastAPI endpoint for citation generation.
    """
    print(f"\n[Papervista Explorer] Requesting {style.upper()} citation for {paper_id}...")
    
    try:
        # 1. Get the standardized data
        paper_data = get_paper_data(paper_id)
        
        # 2. Configure the API call
        endpoint = f"{API_BASE_URL}/generate/citation"
        params = {"style": style}
        headers = {"Content-Type": "application/json"}
        
        # 3. Make the POST request
        response = requests.post(
            endpoint, 
            params=params, 
            headers=headers, 
            json=paper_data
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        
        result = response.json()
        
        # 4. Display the final result to the user
        print("-" * 50)
        print(f"STYLE: {result.get('style', 'N/A')}")
        print(f"SOURCE ENGINE: {result.get('source', 'N/A')}")
        print("-" * 50)
        print(result.get('citation', 'Error: Citation not found in response.'))
        print("-" * 50)
        
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] API Call Failed: {e.response.status_code}")
        # Display the error detail returned by the FastAPI server (e.g., the CSL/LLM fail message)
        try:
            print(f"Server Detail: {e.response.json().get('detail', 'Unknown error.')}")
        except json.JSONDecodeError:
            print("Details: Failed to decode error response.")
            
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Connection refused. Ensure your FastAPI server is running in another terminal.")
        print(f"Run: uvicorn main:app --reload")
    except ValueError as e:
        print(f"\n[ERROR] {e}")


# --- Command Line Interface Setup ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CLI client for the Papervista AI Research Explorer."
    )
    
    # This defines the command structure: python explorer_cli.py cite <paper_id> --style <style>
    parser.add_argument('command', choices=['cite'], help="Command to execute: 'cite'")
    parser.add_argument('paper_id', help="The ID of the paper to process (e.g., 711722243044)")
    parser.add_argument('--style', default='apa', help="The citation style (e.g., apa, mla, ieee). Default is apa.")
    
    args = parser.parse_args()
    
    if args.command == 'cite':
        cite_paper_cli(args.paper_id, args.style)