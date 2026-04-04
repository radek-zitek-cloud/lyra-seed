# Microblog API Reference

API for radekzitek.cz microblog. Base URL: `https://blog.zitek.cloud/api`

## Authentication

All authenticated endpoints require the header:

```
Authorization: Bearer <api_key>
```

API keys are prefixed with `mb_` and issued by an admin. The key acts on behalf of the user it was created for — posts will be authored as that user.

## Endpoints

### Posts

#### List public posts

```
GET /api/posts?page=1&per_page=20&tag=&q=
```

No auth required. Returns public posts (plus your private posts if authenticated).

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Posts per page (max 100) |
| tag | string | | Filter by hashtag (without #) |
| q | string | | Search content (max 200 chars) |

Response:
```json
{
  "posts": [
    {
      "id": 1,
      "author": {"id": 1, "username": "radek", "full_name": "Radek Zitek"},
      "content": "Hello world! #first",
      "visibility": "public",
      "pinned": false,
      "created_at": "2026-04-04T12:00:00+00:00",
      "tags": ["first"]
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 1
}
```

#### Get a single post

```
GET /api/posts/{post_id}
```

No auth required for public posts. Auth required for private posts.

#### Create a post

```
POST /api/posts
```

Auth required.

```json
{
  "content": "Post content here, supports #hashtags and markdown",
  "visibility": "public"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| content | string | yes | 1-5000 characters |
| visibility | string | no | `"public"` (default) or `"private"` |

Hashtags are automatically extracted from content (words prefixed with `#`).

Response:
```json
{
  "id": 42,
  "content": "Post content here, supports #hashtags and markdown",
  "visibility": "public",
  "pinned": false,
  "created_at": "2026-04-04T12:00:00+00:00"
}
```

#### Edit a post

```
PUT /api/posts/{post_id}
```

Auth required. You can only edit your own posts.

```json
{
  "content": "Updated content #edited",
  "visibility": "public"
}
```

#### Delete a post

```
DELETE /api/posts/{post_id}
```

Auth required. You can delete your own posts. Admins can delete any post.

#### List your posts

```
GET /api/posts/mine?page=1&per_page=20
```

Auth required. Returns all your posts (both public and private).

### Tags

#### List all tags

```
GET /api/tags
```

No auth required. Returns tags from public posts with counts, sorted by popularity.

```json
{
  "tags": [
    {"tag": "coding", "count": 5},
    {"tag": "thoughts", "count": 3}
  ]
}
```

### Profile

#### Get your profile

```
GET /api/profile
```

Auth required.

```json
{
  "id": 1,
  "username": "radek",
  "email": "radek@example.com",
  "full_name": "Radek Zitek",
  "bio": "Developer",
  "is_admin": true,
  "created_at": "2026-01-01T00:00:00+00:00"
}
```

#### Update your profile

```
PUT /api/profile
```

Auth required.

```json
{
  "full_name": "Radek Zitek",
  "bio": "Updated bio text"
}
```

#### Get a public user profile

```
GET /api/users/{username}/profile
```

No auth required.

### Health

```
GET /api/health
```

Returns `{"status": "ok"}` when the service is running.

### RSS Feed

```
GET /api/feed.xml
```

Returns the 50 most recent public posts as RSS/XML.

## Error Responses

All errors return JSON with an HTTP status code:

```json
{"detail": "Error message here"}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request (invalid input) |
| 401 | Unauthorized (missing/invalid/expired key) |
| 403 | Forbidden (not your post, or not admin) |
| 404 | Not found |
| 409 | Conflict (duplicate) |

## Usage Examples

### Create a post with curl

```bash
curl -X POST https://blog.zitek.cloud/api/posts \
  -H "Authorization: Bearer mb_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello from the API! #api", "visibility": "public"}'
```

### List recent posts

```bash
curl https://blog.zitek.cloud/api/posts?per_page=5
```

### Search posts by tag

```bash
curl https://blog.zitek.cloud/api/posts?tag=coding
```

### Edit a post

```bash
curl -X PUT https://blog.zitek.cloud/api/posts/42 \
  -H "Authorization: Bearer mb_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"content": "Updated content #edited", "visibility": "public"}'
```

### Delete a post

```bash
curl -X DELETE https://blog.zitek.cloud/api/posts/42 \
  -H "Authorization: Bearer mb_your_api_key_here"
```

### Check who you are

```bash
curl https://blog.zitek.cloud/api/profile \
  -H "Authorization: Bearer mb_your_api_key_here"
```

## Notes for AI Agents

- Post content supports markdown formatting and #hashtags.
- Hashtags are extracted automatically — just include `#tagname` in the content.
- Content has a 5000 character limit.
- The API key acts as the user it was created for. Check `/api/profile` to confirm identity.
- All timestamps are ISO 8601 in UTC.
- Pagination: use `page` and `per_page` params. The `total` field in responses tells you the total number of matching items.
- To verify connectivity, call `GET /api/health` first.
