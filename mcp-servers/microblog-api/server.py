import os
from typing import Any, Optional

import httpx
from fastmcp import FastMCP

BASE_URL = "https://blog.zitek.cloud/api"
API_KEY_ENV = "MICROBLOG_API_KEY"
TIMEOUT = 30.0

mcp = FastMCP("microblog-api")


class MicroblogAPIError(Exception):
    """Raised when the microblog API returns an error."""


def _get_api_key() -> str:
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise MicroblogAPIError(
            f"Missing required environment variable {API_KEY_ENV}."
        )
    return api_key


def _build_headers(require_auth: bool = False) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if require_auth:
        api_key = _get_api_key()
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def _request(
    method: str,
    path: str,
    *,
    require_auth: bool = False,
    params: Optional[dict[str, Any]] = None,
    json_data: Optional[dict[str, Any]] = None,
) -> Any:
    url = f"{BASE_URL}{path}"
    headers = _build_headers(require_auth=require_auth)

    if json_data is not None:
        headers["Content-Type"] = "application/json"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
            )
        except httpx.HTTPError as exc:
            raise MicroblogAPIError(f"Request to microblog API failed: {exc}") from exc

    if response.is_success:
        if response.status_code == 204 or not response.content:
            return {"success": True}
        try:
            return response.json()
        except ValueError:
            return {"success": True, "text": response.text}

    detail = None
    try:
        body = response.json()
        detail = body.get("detail")
    except ValueError:
        detail = response.text.strip() or None

    message = f"Microblog API error {response.status_code}"
    if detail:
        message = f"{message}: {detail}"
    raise MicroblogAPIError(message)


@mcp.tool()
async def list_posts(
    page: int = 1,
    per_page: int = 20,
    tag: str = "",
    q: str = "",
    mine: bool = False,
) -> dict[str, Any]:
    """List posts. By default returns public posts; set mine=true to list your own posts (auth required)."""
    if page < 1:
        raise ValueError("page must be >= 1")
    if per_page < 1 or per_page > 100:
        raise ValueError("per_page must be between 1 and 100")
    if len(q) > 200:
        raise ValueError("q must be 200 characters or fewer")

    path = "/posts/mine" if mine else "/posts"
    params = {
        "page": page,
        "per_page": per_page,
    }

    if not mine:
        if tag:
            params["tag"] = tag
        if q:
            params["q"] = q

    return await _request("GET", path, require_auth=mine, params=params)


@mcp.tool()
async def get_post(post_id: int, include_private: bool = True) -> dict[str, Any]:
    """Get a single post by ID. Auth is included by default so private posts you can access also work."""
    if post_id < 1:
        raise ValueError("post_id must be >= 1")

    return await _request(
        "GET",
        f"/posts/{post_id}",
        require_auth=include_private,
    )


@mcp.tool()
async def create_post(content: str, visibility: str = "public") -> dict[str, Any]:
    """Create a new post. Content supports markdown and #hashtags."""
    if not content or not content.strip():
        raise ValueError("content is required")
    if len(content) > 5000:
        raise ValueError("content must be 5000 characters or fewer")
    if visibility not in {"public", "private"}:
        raise ValueError('visibility must be either "public" or "private"')

    payload = {
        "content": content,
        "visibility": visibility,
    }
    return await _request("POST", "/posts", require_auth=True, json_data=payload)


@mcp.tool()
async def edit_post(post_id: int, content: str, visibility: str = "public") -> dict[str, Any]:
    """Edit one of your posts."""
    if post_id < 1:
        raise ValueError("post_id must be >= 1")
    if not content or not content.strip():
        raise ValueError("content is required")
    if len(content) > 5000:
        raise ValueError("content must be 5000 characters or fewer")
    if visibility not in {"public", "private"}:
        raise ValueError('visibility must be either "public" or "private"')

    payload = {
        "content": content,
        "visibility": visibility,
    }
    return await _request(
        "PUT",
        f"/posts/{post_id}",
        require_auth=True,
        json_data=payload,
    )


@mcp.tool()
async def delete_post(post_id: int) -> dict[str, Any]:
    """Delete a post you own. Admins can delete any post."""
    if post_id < 1:
        raise ValueError("post_id must be >= 1")

    result = await _request("DELETE", f"/posts/{post_id}", require_auth=True)
    if result == {"success": True}:
        return {"success": True, "deleted_post_id": post_id}
    return result


@mcp.tool()
async def list_tags() -> dict[str, Any]:
    """List public tags with counts, sorted by popularity."""
    return await _request("GET", "/tags")


@mcp.tool()
async def get_profile() -> dict[str, Any]:
    """Get the authenticated user's profile."""
    return await _request("GET", "/profile", require_auth=True)


if __name__ == "__main__":
    mcp.run()
