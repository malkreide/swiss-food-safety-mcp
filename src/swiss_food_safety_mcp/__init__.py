"""
swiss-food-safety-mcp
=====================
MCP Server for Swiss Federal Food Safety and Veterinary Office (BLV) open data.

No authentication required. Data sources:
- opendata.swiss/BLV  (28 datasets: CSV, JSON, Parquet, XML)
- lindas.admin.ch      (SPARQL endpoint for linked data)
- news.admin.ch        (RSS feed for public warnings & recalls)

Part of the Swiss public sector MCP server portfolio.
Model-agnostic: works with Claude, GPT, Ollama, and any MCP-compatible client.
"""

__version__ = "1.0.0"
__author__ = "malkreide"
__license__ = "MIT"

__all__ = ["__version__", "__author__", "__license__"]
