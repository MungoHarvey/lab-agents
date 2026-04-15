# Edison File Management

For ANALYSIS and other data-bearing jobs. Full-featured path is async.

## Upload a single file

```python
resp = await client.astore_file_content(
    name="brain size dataset",
    file_path="./datasets/brain_size_data.csv",
    description="Used by Edison Analysis",
)
```

## Upload a directory as a collection

```python
resp = await client.astore_file_content(
    name="scRNA project files",
    file_path="./datasets",
    description="Full project directory",
    as_collection=True,
)
```

## Retrieve outputs after a job

```python
output_data = job_result.environment_frame["state"]["info"]["output_data"]
for entry in output_data:
    await client.afetch_data_from_storage(data_storage_id=entry["entry_id"])
```

- Files ≳10 MB stream to disk automatically.
- Smaller payloads return a `RawFetchResponse` with raw content.

## Parameters

| Param | Meaning |
|---|---|
| `name` | Descriptive identifier |
| `file_path` | Local path to file or directory |
| `description` | Context for the data |
| `as_collection` | `True` for directory uploads |
