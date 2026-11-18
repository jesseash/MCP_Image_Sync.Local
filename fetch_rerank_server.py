import os
import json
import requests
import trafilatura
from flashrank import Ranker, RerankRequest
from mcp.server.mcpserver import MCPServer

# Endpoint for the local one-search-mcp Streamable HTTP proxy
MCP_URL = os.getenv(
    "ONESEARCH_MCP_URL", "http://localhost:3000/mcp"
)

# Initialize MCPServer (MCP SDK v2)
mcp = MCPServer("FetchReranker")

# Load pre-baked FlashRank cross-encoder model from local cache
ranker = Ranker(
    model_name="ms-marco-MiniLM-L-12-v2",
    cache_dir="/opt/flashrank",
)


def _parse_mcp_sse(resp: requests.Response) -> dict:
    """Extracts JSON payload from SSE event-stream or JSON."""
    text = resp.text.strip()
    ctype = resp.headers.get("Content-Type", "")
    if "text/event-stream" in ctype or text.startswith("event:"):
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return resp.json()


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

    data = _parse_mcp_sse(r_scrape)
    items = data.get("result", {}).get("content", [])
    return "\n".join(i.get("text", "") for i in items)


@mcp.tool()
def fetch(url: str, query: str = "", top_k: int = 5) -> str:
    """Scrapes via one_scrape, cleans HTML, and reranks."""
    try:
        raw_html = _scrape_via_onesearch(url)
    except Exception as e:
        return f"Error calling one_scrape for {url}: {e}"

    if not raw_html:
        return f"Error: Empty HTML returned from {url}"

    clean_md = trafilatura.extract(
        raw_html, output_format="markdown", include_links=True
    )
    if not clean_md:
        return f"Error: No readable text found at {url}"

    if not query.strip():
        return clean_md[:15000]

    #chunks = [
     #   c.strip()
      #  for c in clean_md.split("\n\n")
       # if len(c.strip()) > 40
    #]
    #if not chunks:
     #   return clean_md[:15000]

    
    # Group paragraphs under their Markdown headings into ~1,000-char sections
    # so FlashRank ranks complete instructions with context instead of isolated lines

    sections = []
    current = []
    current_len = 0

    for block in clean_md.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#") and current_len > 250:
            sections.append("\n\n".join(current))
            current = [block]
            current_len = len(block)
        else:
            current.append(block)
            current_len += len(block)
            if current_len >= 1000:
                sections.append("\n\n".join(current))
                current = []
                current_len = 0
    
    passages = [
        {"id": i, "text": t} for i, t in enumerate(sections)
    ]
        # Flush any remaining paragraphs left in 'current' after the loop ends
    # so the final section of the webpage is not dropped
    if current:
        sections.append("\n\n".join(current))

    # Safety fallback: if no sections were built, return raw clean Markdown
    # instead of passing an empty list to FlashRank
    if not sections:
        return clean_md[:15000]

    results = ranker.rerank(
        RerankRequest(query=query, passages=passages)
    )
    top_chunks = [r["text"] for r in results[:top_k]]
    return "\n\n---\n\n".join(top_chunks)


# Pass host and port directly to run() in MCP SDK v2
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=3001,
    )
