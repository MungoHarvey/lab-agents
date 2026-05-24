# Edison Tasks API

## Task dict schema

```python
{
    "name": JobNames.<TYPE>,
    "query": "<string>",
    "runtime_config": {"continued_job_id": "<prior_task_id>"},  # optional
}
```

## Client methods

Sync and async (`a`-prefixed) variants:

| Method | Purpose |
|---|---|
| `run_tasks_until_done(task_or_list)` | Submit + block until done; accepts single dict or list |
| `arun_tasks_until_done(...)` | Async variant |
| `create_task(dict)` | Submit, return task ID immediately |
| `acreate_task(dict)` | Async submit |
| `get_task(task_id)` | Poll status |
| `aget_task(task_id)` | Async poll |

## Batching

```python
resps = client.run_tasks_until_done([
    {"name": JobNames.LITERATURE, "query": q1},
    {"name": JobNames.PRECEDENT,  "query": q2},
])
```

Returns a list in order.

## Continuing a prior task

```python
{
    "name": JobNames.LITERATURE,
    "query": "Expand the third finding with trial-stage evidence.",
    "runtime_config": {"continued_job_id": prior_task_id},
}
```

## Response

Response schema is not formally documented. After a job completes, analysis/notebook artifacts are under:

```python
job_result.environment_frame["state"]["info"]["output_data"]
```

Inspect before asserting fields. Enumerate job types at runtime:

```python
python -c "from edison_client import JobNames; print([j.name for j in JobNames])"
```
