from __future__ import annotations

import ast
import math
import operator
from urllib.parse import urlparse

import requests
from crewai.tools import tool
from ddgs import DDGS

REQUEST_TIMEOUT = 12

# Restricted public JSON API hosts. This is deliberately not an open SSRF proxy.
ALLOWED_API_HOSTS = {
    "remoteok.com",
    "www.remoteok.com",
}


@tool("wikipedia_search")
def wikipedia_search(query: str) -> str:
    """Search Wikipedia's public API for background information."""
    q = str(query).strip()[:200]
    if not q:
        return "No search query supplied."

    params = {
        "action": "query",
        "list": "search",
        "srsearch": q,
        "format": "json",
        "utf8": 1,
        "srlimit": 5,
    }
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "AuraCareerNavigator/1.0"},
    )
    response.raise_for_status()
    data = response.json()

    items = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        clean = snippet.replace("<span class=\"searchmatch\">", "").replace("</span>", "")
        items.append(f"- {title}: {clean}")

    return "\n".join(items) if items else "No Wikipedia results found."


@tool("duckduckgo_search")
def duckduckgo_search(query: str) -> str:
    """Search the public web with DuckDuckGo for current information."""
    q = str(query).strip()[:300]
    if not q:
        return "No search query supplied."

    results = []
    with DDGS(timeout=REQUEST_TIMEOUT) as ddgs:
        for item in ddgs.text(q, max_results=6):
            title = str(item.get("title", ""))[:200]
            body = str(item.get("body", ""))[:700]
            href = str(item.get("href", ""))[:500]
            results.append(f"- {title}\n  {body}\n  URL: {href}")

    return "\n".join(results) if results else "No DuckDuckGo results found."


def _validate_public_api_url(raw_url: str) -> str:
    url = str(raw_url).strip()
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS URLs are permitted.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are not permitted.")
    if parsed.hostname not in ALLOWED_API_HOSTS:
        raise ValueError("This public API host is not allowlisted.")
    if parsed.port not in (None, 443):
        raise ValueError("Non-standard ports are not permitted.")
    return url


@tool("requests_get")
def requests_get(url: str) -> str:
    """Fetch JSON from an allowlisted public HTTPS API such as RemoteOK."""
    safe_url = _validate_public_api_url(url)
    response = requests.get(
        safe_url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "AuraCareerNavigator/1.0", "Accept": "application/json"},
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        raise ValueError("The endpoint did not return JSON.")

    data = response.json()
    text = str(data)
    return text[:12000]


_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if not math.isfinite(float(node.value)):
            raise ValueError("Non-finite numbers are not allowed.")
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 10:
            raise ValueError("Exponent too large.")
        value = _ALLOWED_BINOPS[type(node.op)](left, right)
        if not math.isfinite(float(value)):
            raise ValueError("Result is not finite.")
        return float(value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return float(_ALLOWED_UNARYOPS[type(node.op)](_safe_eval(node.operand)))
    raise ValueError("Only basic arithmetic is allowed.")


@tool("calculate")
def calculate(expression: str) -> str:
    """Calculate safe basic arithmetic without executing arbitrary Python."""
    expression = str(expression).strip()[:200]
    if not expression:
        return "No expression supplied."
    tree = ast.parse(expression, mode="eval")
    result = _safe_eval(tree)
    return str(int(result) if result.is_integer() else result)


def build_tools():
    # Exactly four external tools are exposed to the CrewAI agent.
    return [
        wikipedia_search,
        duckduckgo_search,
        requests_get,
        calculate,
    ]
