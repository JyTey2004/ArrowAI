# perplexity_client.py
from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union, Literal

from perplexity import Perplexity

class PerplexityClient:
    """
    Thin, async-first wrapper around Perplexity's official SDK.

    Capabilities:
      - search(): calls Search API and returns ranked results
      
      
    """

    def __init__(self, api_key: Optional[str] = None, *, timeout: float = 60.0, max_retries: int = 3):
        # If api_key is None, SDK will read PERPLEXITY_API_KEY from env.
        self.client = Perplexity(api_key=api_key, timeout=timeout)
        self.max_retries = max_retries

    # ---------- Search API (ranked results) ----------
    def search(
        self,
        query: str | List[str],
        country: Optional[str] = None,
        max_results: int = 5,
        max_tokens: int = 1000,
        max_tokens_per_page: int = 300,
        search_mode: Optional[Union[str, Literal["web", "academic", "sec"]]] = None,
    ) -> Dict[str, Any]:
        """
        Calls the Search API and returns the ranked results.
        Execute multiple related queries in a single request for comprehensive research.
        
        Args:
            query: The search query string or list of strings.
            country: Optional country code to tailor search results.
            max_results: Maximum number of search results to return.
            max_tokens: Maximum number of tokens in the response.
            max_tokens_per_page: Maximum number of tokens per page in the response.
            search_mode: Optional search mode ("web", "academic", "sec").
            
        Returns:
            A dictionary containing the search results.
        """
        try:
            resp = self.client.search.create(
                    query=query,
                    country=country,
                    max_results=max_results,
                    max_tokens=max_tokens,
                    max_tokens_per_page=max_tokens_per_page,
                    search_mode=search_mode,
                )
            results  = getattr(resp, "results", []) or []

            return results
        except Exception as e:
            print(f"Error occurred during search: {e}")
            return {"text": "", "sources": [], "raw": None}
            
