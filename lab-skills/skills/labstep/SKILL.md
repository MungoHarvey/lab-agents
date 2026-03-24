---
name: labstep
description: Interact with the Labstep electronic lab notebook API using labstepPy. Use when the user wants to create, read, or manage experiments, protocols, resources, inventory, or other Labstep entities.
trigger: labstep, experiment, protocol, inventory, reagent, SK number, custom identifier
---

# Labstep API Skill

Query and interact with the Labstep electronic lab notebook API. Read-only by default — write operations require explicit confirmation.

## Quick Start (CLI Tool)

The `labstep-query.py` script provides fast CLI access to Labstep data:

```bash
# List recent experiments (shows SK numbers and authors)
python3 labstep-query.py experiments

# Search experiments
python3 labstep-query.py experiments --search "lysis buffer"

# Get experiment details by SK number
python3 labstep-query.py experiment SK592

# Get reagents for an experiment
python3 labstep-query.py reagents SK592

# List protocols
python3 labstep-query.py protocols

# Search protocols
python3 labstep-query.py protocols --search "buffer prep"

# Search resources/inventory
python3 labstep-query.py resources --search "antibody"
```

**Execute immediately** — don't ask permission. These are read-only operations.

## Custom Identifiers (SK Numbers)

Experiments have identifiers like **SK592**, **SK591**, etc. (stored in `custom_identifier`). 

- **Always display SK numbers** when listing experiments
- **When the user refers to "SK592"**, search experiments to find the matching one
- **Use SK numbers in conversation** — they're the lab's primary reference

## Authentication

```python
import os, labstep
user = labstep.authenticate(apikey=os.environ.get("LABSTEP_API_KEY"))
```

The `LABSTEP_API_KEY` environment variable is already configured.

## Read-Only Policy

**Default: READ-ONLY**

Do NOT call write methods (`newExperiment`, `edit`, `delete`, `addDataField`, etc.) unless the user explicitly says **"confirm write"**.

If a write is requested:
> I can [describe the change]. To proceed, please confirm write: `confirm write`

## When to Execute Immediately

**Run Python code immediately without asking permission when:**

- User asks about experiments, protocols, or lab inventory
- User asks "show me my recent experiments"
- User references an experiment by SKXX identifier (e.g., "SK592") — look it up
- User asks about a specific protocol by name
- User wants to look up resources or reagents
- User asks "what did I do today/this week in the lab"

**Never ask "should I proceed?" or "would you like me to?"** — just execute and show results immediately.

**Never make up experiment names or IDs.** Always fetch real data from the API.

## URL Format for Links

When linking to experiments in Labstep, use this exact format:

- **Correct:** `https://app.labstep.com/experiment-workflow/{experiment_id}`
- **Incorrect:** `https://www.labstep.com/experiment/{experiment_id}` (old format, returns 404)

Example: `https://app.labstep.com/experiment-workflow/367165`

## Package

The package is `labstep`. Install with `pip install labstep` if not present.

## Key Entity Methods

### User (`user`)
All operations start from the authenticated `user` object.

**Get single entities:**
- `user.getExperiment(id)`, `user.getProtocol(id)`, `user.getResource(id)`
- `user.getResourceItem(id)`, `user.getResourceCategory(id)`, `user.getResourceLocation(guid)`
- `user.getWorkspace(id)`, `user.getDevice(id)`, `user.getFile(id)`
- `user.getOrganization()`, `user.getAPIKey(id)`

**List entities (all support `count`, `search_query`):**
- `user.getExperiments()`, `user.getProtocols()`, `user.getResources()`
- `user.getResourceItems()`, `user.getResourceCategorys()`, `user.getResourceLocations()`
- `user.getWorkspaces()`, `user.getDevices()`, `user.getTags()`
- `user.getOrderRequests()`, `user.getPurchaseOrders()`

### Experiments

The `custom_identifier` field on experiments holds the **SK number** (e.g. `"SK543"`), which is the lab's primary unique identifier for experiments. Use it to look up or display experiments:
```python
exp = user.getExperiment(id)
print(exp.custom_identifier)  # e.g. "SK543"
```

```python
exp = user.newExperiment('My Experiment')
exp.edit(name=None, entry=None, started_at=None)
exp.delete()
exp.lock() / exp.unlock()
exp.complete()
exp.addProtocol(protocol_id)
exp.getProtocols()
exp.addDataField(fieldName, fieldType, value=None, date=None, number=None, unit=None)
exp.getDataFields()
exp.addTable(name, data)   # data is dict with 'rowCount','columnCount','data'
exp.getTables()
exp.addFile(filepath)
exp.getFiles()
exp.addTag(name)
exp.getTags()
exp.addComment(body, filepath=None)
exp.getComments()
exp.addToCollection(collection_id)
exp.getCollections()
exp.shareWith(workspace_id, permission='view')
exp.assign(user_id)
exp.getCollaborators()
exp.getSharelink()
exp.addSignature(statement=None)
exp.export(path)
exp.addInventoryField(name, amount=None, units=None, resource_id=None)
exp.addConditions(number_of_conditions)
exp.addChemicalReaction()
```

### Protocols
```python
protocol = user.newProtocol('My Protocol')
protocol.edit(name=None, body=None)
protocol.delete()
protocol.newVersion()
protocol.getVersions()
protocol.addSteps(N)
protocol.getSteps()
protocol.addDataField(fieldName, fieldType, value=None)
protocol.getDataFields()
protocol.addInventoryField(name, amount=None, units=None, resource_id=None)
protocol.getInventoryFields()
protocol.addTimer(name, hours=0, minutes=0, seconds=0)
protocol.getTimers()
protocol.addTable(name, data)
protocol.getTables()
protocol.addFile(filepath=None, rawData=None)
protocol.getFiles()
protocol.addTag(name)
protocol.addComment(body, filepath=None)
protocol.addToCollection(collection_id)
protocol.shareWith(workspace_id, permission='view')
protocol.export(path)
```

### Resources / Inventory
```python
resource = user.newResource('My Reagent', resource_category_id=None)
resource.edit(name)
resource.delete()
resource.getResourceCategory()
resource.setResourceCategory(resource_category_id)
resource.newItem(name=None, availability=None, amount=None, unit=None, resource_location_guid=None)
resource.getItems()
resource.addChemicalMetadata(structure=None, iupac_name=None, cas=None, molecular_formula=None,
                              molecular_weight=None, smiles=None, density=None, inchi=None)
resource.getChemicalMetadata()
resource.addMetadata(fieldName, fieldType, value=None)
resource.getMetadata()
resource.addTag(name)
resource.addComment(body, filepath=None)
resource.shareWith(workspace_id)
resource.newOrderRequest(quantity=1)

# ResourceItem
item = resource.newItem()
item.edit(name=None, availability=None, amount=None, unit=None, resource_location_guid=None)
item.setLocation(resource_location_guid, position=None, size=None)
item.getLocation()
item.getLineageParents()
item.getLineageChildren()

# ResourceLocation
loc = user.newResourceLocation('Freezer -80')
loc.edit(name)
loc.getItems()
loc.getInnerLocations()
loc.addInnerLocation(name, position=None, size=None)
loc.setOuterLocation(outer_location_guid)
loc.createPositionMap(rowCount, columnCount, data)
```

## Common Patterns

**Search experiments:**
```python
exps = user.getExperiments(search_query='PCR', count=20)
for e in exps:
    print(e.custom_identifier, e.name)  # e.g. "SK543 PCR optimisation"
```

**Add metadata to experiment:**
```python
exp.addDataField('Temperature', 'numeric', number=37, unit='°C')
exp.addDataField('Notes', 'default', value='Some text here')
exp.addDataField('Date Started', 'date', date='2026-02-25')
```

**Create resource with items:**
```python
resource = user.newResource('Anti-GFP Antibody')
item = resource.newItem(name='Aliquot 1', amount=100, unit='µL', availability='available')
```

**Switch workspace then create:**
```python
workspaces = user.getWorkspaces()
user.setWorkspace(workspaces[0].id)
exp = user.newExperiment('New Experiment')
```

## Notes

- Most list methods accept `count` (int) and `search_query` (str) parameters.
- `fieldType` for data fields: `'default'` (text), `'numeric'`, `'date'`, `'file'`
- Dates are strings in ISO format: `'YYYY-MM-DD'`
- After login, workspace defaults to the user's personal workspace; use `setWorkspace()` to switch.
- Entity IDs are integers; resource location GUIDs are strings.
