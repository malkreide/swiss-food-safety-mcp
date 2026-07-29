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

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

try:
    # Read the version from the installed distribution metadata, which is built
    # from pyproject.toml. Hand-maintaining the literal here let the numbers
    # drift apart: pyproject said 1.1.3, this said 1.1.0. A value nobody
    # has to remember to bump cannot go stale.
    __version__ = _distribution_version("swiss-food-safety-mcp")
except PackageNotFoundError:
    # Running from the source tree without an install (e.g. a bare checkout).
    # Deliberately not a plausible-looking number: an obviously non-release
    # marker is better than a wrong version in the User-Agent.
    __version__ = "0.0.0+source"
__author__ = "malkreide"
__license__ = "MIT"

__all__ = ["__version__", "__author__", "__license__"]
