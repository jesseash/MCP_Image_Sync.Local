import os
import json
import requests
import trafilatura
from flashrank import Ranker, RerankRequest
from mcp.server.fastmcp import FastMCP

# Endpoint for the local one-search-mcp Streamable HTTP proxy
MCP_URL = os.getenv(
    "ONESEARCH_MCP_URL", "http://localhost:3000/mcp"
)

# Initialize FastMCP server on port 3001 (accessible externally)
mcp = FastMCP("FetchReranker", host="0.0.0.0", port=3001)

# Load pre-baked FlashRank cross-encoder model from local cache
ranker = Ranker(
    model_name="ms-marco-MiniLM-L-12-v2",
    cache_dir="/opt/flashrank",
)


def _parse_mcp_sse(resp: requests.Response) -> dict:
    """Extracts JSON payload from SSE event-stream or JSON."""
    text = resp.text.strip()
    ctype = resp.headers.get("Content-Type", "")
    # If mcp-proxy returns SSE lines, parse the 'data:' JSON line
    if "text/event-stream" in ctype or text.startswith("event:"):
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return resp.json()


# 'url' is received here when called by fetch(url, ...) below
def _scrape_via_onesearch(url: str) -> str:
    """Calls one_scrape over MCP to render JS-heavy pages."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    })

    # Step 1: Handshake with one-search-mcp to get a session ID
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {
                "name": "fetch-reranker",
                "version": "1.0",
            },
        },
    }
    r_init = session.post(MCP_URL, json=init_payload, timeout=10)
    r_init.raise_for_status()

    # Attach the returned mcp-session-id to subsequent requests
    sid = r_init.headers.get("mcp-session-id")
    if sid:
        session.headers.update({"mcp-session-id": sid})

    # Step 2: Invoke one_scrape with 'url' to get full raw HTML
    scrape_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "one_scrape",
            "arguments": {"url": url, "formats": ["rawHtml"]},
        },
    }
    r_scrape = session.post(
        MCP_URL, json=scrape_payload, timeout=30
    )
    r_scrape.raise_for_status()

    # Unpack the rendered HTML string from the MCP response
    data = _parse_mcp_sse(r_scrape)
    items = data.get("result", {}).get("content", [])
    return "\n".join(i.get("text", "") for i in items)


# FastMCP exposes 'url', 'query', and 'top_k' as MCP tool inputs
@mcp.tool()
def fetch(url: str, query: str = "", top_k: int = 5) -> str:
    """Scrapes via one_scrape, cleans HTML, and reranks."""
    # 1. Fetch browser-rendered HTML via one_scrape (port 3000)
    try:
        raw_html = _scrape_via_onesearch(url)
    except Exception as e:
        return f"Error calling one_scrape for {url}: {e}"

    if not raw_html:
        return f"Error: Empty HTML returned from {url}"

    # 2. Strip scripts, navbars, and HTML tags into clean Markdown
    clean_md = trafilatura.extract(
        raw_html, output_format="markdown", include_links=True
    )
    if not clean_md:
        return f"Error: No readable text found at {url}"

    # 3. If no search query is provided, return full clean text
    if not query.strip():
        return clean_md[:15000]

    # 4. Split Markdown into paragraph chunks (>40 chars) for ranking
    chunks = [
        c.strip()
        for c in clean_md.split("\n\n")
        if len(c.strip()) > 40
    ]
    if not chunks:
        return clean_md[:15000]

    # 5. Score chunks against 'query' and return top_k matches
    passages = [
        {"id": i, "text": t} for i, t in enumerate(chunks)
    ]
    results = ranker.rerank(
        RerankRequest(query=query, passages=passages)
    )
    top_chunks = [r["text"] for r in results[:top_k]]
    return "\n\n---\n\n".join(top_chunks)


# Start the MCP server using Streamable HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
