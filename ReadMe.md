This repository is where I build and push images that will be used for my MCP-Server-Installation-Pipeline project. Some of the images are push as is and some  are built with the necessarcy installation dependencies. Here I make full use of my GHCR and elimanate all external dependnecies- so that the k3s server will be pulling soley from my GHRC without having to worry about having surprises a long the road- like a deleted or renamed image.



The repository contains two Dockerfiles: 
1. `Dockerfile.onesearch`: This Dockerfile builds an image for the OneSearch with mcp-proxy already installed and configured to run on port becuase the Onessearch is an stdio application it needs mcp-proxy be reachable in a k3s pod via streamable http. 

2. `Dockerfile.fetch`: This Dockerfile builds an image for the Fetch Reader with the MCP SDK and other dependencies installed. It also pre-downloads the FlashRank model , a reranker model that is used for ranking search results ro minimize token usage and improve the quality of the search results. The Fetch Reader image also includes the python script fetch_rerank_server.py which is built into the docker image. fetch_rerank_server.py's job is to fetch and rerank search results from the MCP API, where it calls onescrape to fetch the search results for Terafilatura to clean the HTML and FlashRank to rerank the results. The reranked results are then returned to the client for the LLM to consume. 

Below is a simple usecase that demonstrates how the fetch reader and onesearch work when an LLM request the content of a webpage:

![alt text](usecase_webscrape.png)

## License & Copyright

**Copyright (c) 2026 Jesse Ash. All Rights Reserved.**

This repository is made public solely for technical demonstration purposes top clients and collaborators I will working with to localize and adapt the code for their own business AI.
Copyright © 2026 [Your Name]. All rights reserved.

Permission is granted to view, download, and run this code strictly for personal, educational, and non-commercial evaluation. You may not copy, modify, redistribute, publish, or use this code in any public or commercial project without explicit written permission from the copyright holder.



THe code

* **Permitted:** Viewing and reviewing the source code on GitHub for personal reference or hiring/client evaluation.
* **Prohibited:** Copying, modifying, distributing, sublicensing, or using any part of this codebase in commercial or non-commercial projects without explicit written permission from the author.

For licensing inquiries or permission requests, please contact me via jash@stny.rr.com
