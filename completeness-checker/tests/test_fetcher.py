from unittest.mock import MagicMock, patch
from fetcher import fetch_completed_experiments, get_experiment_state


def _mock_experiment(id, name, custom_id, author_name, created_at, ended_at, started_at=None):
    exp = MagicMock()
    exp.id = id
    exp.name = name
    exp.custom_identifier = custom_id
    exp.created_at = created_at
    exp.ended_at = ended_at
    exp.started_at = started_at
    exp.author = {"name": author_name}
    exp.getProtocols.return_value = []
    return exp


def test_fetch_completed_experiments_filters_incomplete():
    completed = _mock_experiment(1, "Done", "SK001", "Alice", "2026-01-01", "2026-01-10")
    in_progress = _mock_experiment(2, "WIP", "SK002", "Bob", "2026-01-01", None, "2026-01-01")
    unstarted = _mock_experiment(3, "New", "SK003", "Carol", "2026-01-01", None)

    mock_user = MagicMock()
    mock_user.getExperiments.return_value = [completed, in_progress, unstarted]

    results = fetch_completed_experiments(mock_user)
    assert len(results) == 1
    assert results[0]["id"] == "SK001"


def test_fetch_completed_experiments_extracts_fields():
    exp = _mock_experiment(42, "My Experiment", "SK042", "Alice", "2026-03-15T10:00:00", "2026-03-20")
    exp.getProtocols.return_value = [MagicMock(), MagicMock()]

    mock_user = MagicMock()
    mock_user.getExperiments.return_value = [exp]

    results = fetch_completed_experiments(mock_user)
    assert len(results) == 1
    r = results[0]
    assert r["id"] == "SK042"
    assert r["name"] == "My Experiment"
    assert r["author"] == "Alice"
    assert r["date"] == "2026-03-15"
    assert r["workflow_id"] == 42
    assert r["protocol_count"] == 2


@patch("fetcher.requests.get")
def test_get_experiment_state(mock_get):
    wf_response = MagicMock()
    wf_response.json.return_value = {"root_experiment": {"id": 99}}
    exp_response = MagicMock()
    exp_response.json.return_value = {"state": {"type": "doc", "content": []}}
    mock_get.side_effect = [wf_response, exp_response]

    state = get_experiment_state(1, "https://api.labstep.com", {"apikey": "test"})
    assert state == {"type": "doc", "content": []}


@patch("fetcher.requests.get")
def test_get_experiment_state_no_root(mock_get):
    wf_response = MagicMock()
    wf_response.json.return_value = {"root_experiment": None}
    mock_get.return_value = wf_response

    state = get_experiment_state(1, "https://api.labstep.com", {"apikey": "test"})
    assert state is None
