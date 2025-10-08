import requests
import json
import argparse 
from typing import Dict, Any

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"

# --- 1. Metadata Retrieval Function (FIXED FOR REAL-TIME ID MATCHING) ---
def get_metadata_for_citation(paper_id: str):
    """
    Retrieves the full paper metadata (CSL format) for a given ArXiv ID 
    by querying the FastAPI /search/papers endpoint.
    
    This function uses a robust check to match the base ID (ignoring the version).
    """
    print(f"\n[Papervista Explorer] Attempting to retrieve metadata for ID: {paper_id}...")
    
    endpoint = f"{API_BASE_URL}/search/papers"
    
    try:
        # Search using the ID as the exact query, limiting results to 1
        response = requests.get(
            endpoint, 
            params={"query": paper_id}, 
            timeout=10
        )
        response.raise_for_status()
        results = response.json()
        
        # --- ROBUST ID CHECK LOGIC ---
        matching_paper = None
        for paper in results:
            # 1. Extract the base ID from the result, discarding the version (e.g., '2510.06190v1' -> '2510.06190')
            full_arxiv_id = paper['id'].split('/')[-1]
            short_id_from_result = full_arxiv_id.split('v')[0] 
            
            # 2. Compare the short ID against the user's input ID
            if short_id_from_result == paper_id:
                matching_paper = paper
                break
        
        if matching_paper:
            # Found the matching paper, now format it for the citation endpoint
            citation_item = {
                "id": matching_paper['id'],
                "type": "article-journal", 
                "title": matching_paper['title'],
                "author": matching_paper['author'],
                "issued": matching_paper['issued'],
                "container_title": matching_paper['container_title'],
                "URL": matching_paper['url']
            }
            return citation_item
        else:
            print(f"[ERROR] Could not find paper ID {paper_id} via real-time lookup. (Ensure ArXiv ID is correct and use the base number)")
            return None
        # --- END ROBUST CHECK ---
        
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Connection refused. Ensure your FastAPI server is running.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] Retrieval Failed: {e}. Check server logs.")
        return None

# --- 2. Citation Generation Command (Handles the 'cite' command) ---
def cite_paper_cli(paper_id: str, style: str):
    """
    Orchestrates the citation process: gets data via API, then sends data 
    to the /generate/citation endpoint.
    """
    
    # 1. Get the real-time standardized data using the ID
    paper_data = get_metadata_for_citation(paper_id)
    
    if not paper_data:
        return
        
    print(f"[Papervista Explorer] Requesting {style.upper()} citation for {paper_id}...")
    
    # 2. Configure the API call to the hybrid citation generator
    endpoint = f"{API_BASE_URL}/generate/citation"
    params = {"style": style}
    headers = {"Content-Type": "application/json"}
    
    # 3. Make the POST request
    try:
        response = requests.post(
            endpoint, 
            params=params, 
            headers=headers, 
            json=paper_data
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 4. Display the result
        print("-" * 50)
        print(f"STYLE: {result.get('style', 'N/A')}")
        print(f"SOURCE ENGINE: {result.get('source', 'N/A')}")
        print("-" * 50)
        print(result.get('citation', 'Error: Citation not found in response.'))
        print("-" * 50)
        
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Connection refused. Ensure your FastAPI server is running.")
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] API Call Failed: {e.response.status_code}")


# --- 3. Search Command (Handles the 'search' command) ---
def search_cli(topic: str):
    """Calls the FastAPI search endpoint and prints the live results."""
    
    print(f"\n[Papervista Explorer] Searching ArXiv for: '{topic}'...")
    
    endpoint = f"{API_BASE_URL}/search/papers"
    
    try:
        response = requests.get(
            endpoint, 
            params={"query": topic}
        )
        response.raise_for_status() 
        results = response.json()
        
        if not results:
            print("No papers found for this topic.")
            return

        print("-" * 60)
        print(f"Found {len(results)} latest papers. Use 'cite <ID>' to format.")
        print("-" * 60)

        # Print results to user
        for i, paper in enumerate(results):
            authors = ", ".join([a['family'] for a in paper['author']])
            # Extract the ID without the version for the user to copy
            short_id = paper['id'].split('/')[-1].split('v')[0]
            
            # Print the key ID that the user needs for the next 'cite' command
            print(f"[{i+1}] ID: {short_id} (Year: {paper['issued']['date_parts'][0][0]})")
            print(f"    Title: {paper['title']}")
            print(f"    Authors: {authors[:50]}...")
            print("-" * 60)

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Connection refused. Ensure your FastAPI server is running.")
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] Search Failed: {e}. Check server logs for details.")


# --- Command Line Interface Setup (Execution Block) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CLI client for the Papervista AI Research Explorer. Provides real-time scholarly search and citation generation."
    )
    
    subparsers = parser.add_subparsers(dest='command', required=True)

    # 1. Define the 'cite' command
    cite_parser = subparsers.add_parser('cite', help="Generate citation for a paper using its ArXiv ID.")
    cite_parser.add_argument('paper_id', help="The ArXiv ID of the paper (e.g., 2501.12345, NO VERSION).")
    cite_parser.add_argument('--style', default='apa', help="The citation style (e.g., apa, mla, ieee). Default is apa.")
    
    # 2. Define the 'search' command
    search_parser = subparsers.add_parser('search', help="Search ArXiv for the latest papers based on a topic.")
    search_parser.add_argument('topic', help="The research topic to search for (e.g., 'Transformer model').")
    
    args = parser.parse_args()
    
    if args.command == 'cite':
        cite_paper_cli(args.paper_id, args.style)
        
    elif args.command == 'search':
        search_cli(args.topic)
