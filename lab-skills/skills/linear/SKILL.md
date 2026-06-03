---
name: linear
description: Manage issues, projects, and team workflows in the neurogenomics Linear workspace. Use for reading, creating, updating, and triaging issues across the Computational and Wet Lab teams.
trigger: linear, issue, ticket, task, project, COMP-, LAB-, backlog, sprint, triage, milestone, roadmap, track
---

# Linear — neurogenomics Workspace

Workspace: **neurogenomics** · `https://linear.app/neurogenomics`

Two tools are available. Use the MCP tools for most operations (fast, no boilerplate). Fall back to direct GraphQL via `curl` for complex filters, bulk ops, or anything the MCP tools don't expose.

---

## Tool 1 — MCP tools (prefer these)

The `linear` MCP server is pre-configured with `LINEAR_API_KEY`. Call these directly without confirmation for reads; confirm with the user before writes in interactive sessions.

**Read (no confirmation needed):**
- `linear_search_issues` — search by text, team, status, assignee, priority, labels
- `linear_get_user_issues` — all issues assigned to a specific user (up to 50)

**Write (confirm interactively; no confirmation needed in cron/automated runs):**
- `linear_create_issue` — create a new issue (requires title + team ID)
- `linear_update_issue` — update title, description, status, assignee, priority
- `linear_add_comment` — append a markdown comment to any issue

> `linear_search_issues` returns at most 10 results by default. For broader searches, use GraphQL.

---

## Tool 2 — Direct GraphQL (power operations)

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "QUERY_HERE"}' | python3 -m json.tool
```

No "Bearer" prefix. HTTP 200 can still carry errors — always check `response.errors`.

Python helper (zero deps, reads `$LINEAR_API_KEY`):
```bash
SCRIPT=$(find ~/.hermes -path '*/productivity/linear/scripts/linear_api.py' 2>/dev/null | head -1)
python3 "$SCRIPT" <subcommand> [args]
# subcommands: whoami, list-teams, list-projects, list-states, list-issues,
#   get-issue, search-issues, create-issue, update-issue, update-status,
#   add-comment, list-documents, get-document, search-documents, raw
```

---

## Neurogenomics workspace — known IDs

### Teams

| Team | Key | ID |
|------|-----|----|
| Computational | COMP | `533d8cb2-5891-47e3-8a21-925b8a1e9b19` |
| Wet Lab | LAB | `490c3c50-5efd-4653-9cf8-de480b1664e4` |

### Computational workflow states

| State | Type | ID |
|-------|------|----|
| Backlog | backlog | `523ae7c0-9d18-476b-83d3-b681f6160c77` |
| Scheduled | unstarted | `4ea3c25c-e001-43e2-aebd-69db0a25ca16` |
| Todo | unstarted | `79898a1b-2e83-42e9-8169-89c2078266c3` |
| In Progress | started | `1801ddbe-7b78-4a5d-8bc2-9eefa95a0f2c` |
| In Review | started | `06b75e78-670f-4006-8ce5-74d0978f38fa` |
| Done | completed | `65e07f9e-e109-460d-bd60-f85889124d0c` |
| Canceled | canceled | `0a993291-0535-4dbc-9b84-458d5537f6eb` |
| Duplicate | duplicate | `05b18cec-4751-46d3-9700-43ab0b43ddf5` |

> For Wet Lab states, query: `workflowStates(filter:{team:{key:{eq:"LAB"}}}) { nodes { id name type } }`

### Priority values
`0` = None · `1` = Urgent · `2` = High · `3` = Medium · `4` = Low

---

## Common operations (ready-to-run)

### List all open Computational issues
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ issues(filter:{team:{key:{eq:\"COMP\"}},state:{type:{nin:[\"completed\",\"canceled\"]}}},first:50,orderBy:updatedAt){nodes{identifier title priority state{name} assignee{name} dueDate url}pageInfo{hasNextPage endCursor}}}"}' \
  | python3 -m json.tool
```

### Get a single issue (COMP-123 or LAB-45)
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ issue(id:\"COMP-123\"){identifier title description priority state{id name type} assignee{id name} project{name} labels{nodes{name}} comments{nodes{body user{name} createdAt}} dueDate url}}"}' \
  | python3 -m json.tool
```

### List my assigned issues
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ viewer{assignedIssues(first:25,filter:{state:{type:{nin:[\"completed\",\"canceled\"]}}}){nodes{identifier title state{name type} priority dueDate url}}}}"}' \
  | python3 -m json.tool
```

### Search across issues
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ issueSearch(query:\"SEARCH_TERM\",first:20){nodes{identifier title state{name} assignee{name} team{key} url}}}"}' \
  | python3 -m json.tool
```

### Mark an issue Done (Computational)
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{issueUpdate(id:\"COMP-123\",input:{stateId:\"65e07f9e-e109-460d-bd60-f85889124d0c\"}){success issue{identifier state{name}}}}"}' \
  | python3 -m json.tool
```

### Move to In Progress (Computational)
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{issueUpdate(id:\"COMP-123\",input:{stateId:\"1801ddbe-7b78-4a5d-8bc2-9eefa95a0f2c\"}){success issue{identifier state{name}}}}"}' \
  | python3 -m json.tool
```

### Create an issue in Computational
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation($i:IssueCreateInput!){issueCreate(input:$i){success issue{identifier title url}}}",
    "variables": {
      "i": {
        "teamId": "533d8cb2-5891-47e3-8a21-925b8a1e9b19",
        "title": "TITLE",
        "description": "MARKDOWN_DESCRIPTION",
        "priority": 3
      }
    }
  }' | python3 -m json.tool
```

### Add a comment
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{commentCreate(input:{issueId:\"ISSUE_UUID\",body:\"COMMENT\"}){success comment{id}}}"}' \
  | python3 -m json.tool
```

### Assign an issue
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{issueUpdate(id:\"COMP-123\",input:{assigneeId:\"USER_UUID\"}){success issue{identifier assignee{name}}}}"}' \
  | python3 -m json.tool
```

### List projects
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ projects(first:30,orderBy:updatedAt){nodes{id name description progress state lead{name} url}}}"}' \
  | python3 -m json.tool
```

### List recent documents
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ documents(first:25,orderBy:updatedAt){nodes{id title slugId url updatedAt project{name}}}}"}' \
  | python3 -m json.tool
```

### List workspace members
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ users{nodes{id name email active}}}"}' \
  | python3 -m json.tool
```

---

## Pagination

Linear uses Relay-style cursors. Always include `pageInfo { hasNextPage endCursor }` and page with `after: "CURSOR"`. Default: 50 results. Max: 250.

## Filter comparators

`eq` `neq` `in` `nin` `lt` `lte` `gt` `gte` `contains` `startsWith` `containsIgnoreCase`

Multiple fields in a filter are ANDed. Use `or: [...]` for OR logic.

---

## Practical workflows

### Triage new issues
1. `linear_search_issues` with `state: "backlog"` + `team: "COMP"`
2. Review each — set priority, assignee, project
3. Move actionable ones to `Todo`; cancel noise

### Sprint / week planning
1. Fetch all `Todo` + `Scheduled` issues for the team
2. Filter by priority (Urgent first), check due dates
3. Move top N to `In Progress`; balance across assignees

### Report what's blocking progress
```bash
# Issues marked as started but updated >7 days ago
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ issues(filter:{state:{type:{eq:\"started\"}},team:{key:{eq:\"COMP\"}},updatedAt:{lt:\"-P7D\"}},first:20){nodes{identifier title assignee{name} state{name} updatedAt url}}}"}' \
  | python3 -m json.tool
```

### Mark a batch of issues Done
Collect identifiers (e.g. COMP-34, COMP-35), then run for each:
```bash
for ID in COMP-34 COMP-35 COMP-39; do
  curl -s -X POST https://api.linear.app/graphql \
    -H "Authorization: $LINEAR_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"mutation{issueUpdate(id:\\\"$ID\\\",input:{stateId:\\\"65e07f9e-e109-460d-bd60-f85889124d0c\\\"}){success issue{identifier state{name}}}}\"}" \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['data']['issueUpdate']['issue']['identifier'], r['data']['issueUpdate']['issue']['state']['name'])"
done
```

### Document lookup (from URL)
Linear document URLs end in a hex slug: `.../document/some-title-38359beef67c` → slugId = `38359beef67c`
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"query($s:String!){documents(filter:{slugId:{eq:$s}},first:1){nodes{id title content slugId url}}}","variables":{"s":"SLUG_ID"}}' \
  | python3 -m json.tool
```
Note: `content` = Markdown body. `contentData` does not exist — use `contentState` for ProseMirror JSON.

---

## Rate limits

- 5,000 requests / hour per API key
- 3,000,000 complexity points / hour (each property = 0.1 pt, each object = 1 pt)
- Use `first: N` to signal expected volume and reduce complexity cost
- Check `X-RateLimit-Requests-Remaining` header on responses

---

## Rules

- **Read first, then write.** Fetch the issue before updating it; confirm the state ID exists before setting it.
- **Never invent identifiers.** Always look up team IDs, state IDs, and user IDs from the API.
- **Check `errors`.** HTTP 200 ≠ success in GraphQL.
- **Use `terminal`/`curl` for API calls** — not `web_extract` or `browser`.
- **Markdown is supported** in `description` and `body` fields.
- **Don't mark issues Done based on partial evidence.** Verify the completion criteria in the issue description first.
