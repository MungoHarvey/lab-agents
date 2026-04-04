import json
import os
from unittest.mock import patch, MagicMock
from checker import run_check, load_notified, save_notified


def test_load_notified_empty(tmp_path):
    path = tmp_path / "last_checked.json"
    result = load_notified(str(path))
    assert result == set()


def test_load_notified_existing(tmp_path):
    path = tmp_path / "last_checked.json"
    path.write_text(json.dumps(["SK001", "SK002"]))
    result = load_notified(str(path))
    assert result == {"SK001", "SK002"}


def test_save_notified(tmp_path):
    path = tmp_path / "last_checked.json"
    save_notified(str(path), {"SK003", "SK001"})
    data = json.loads(path.read_text())
    assert sorted(data) == ["SK001", "SK003"]


@patch("checker.get_experiment_state")
@patch("checker.send_slack_notification")
def test_run_check_flags_incomplete(mock_notify, mock_state, tmp_path):
    notified_path = str(tmp_path / "last_checked.json")

    # ProseMirror doc with only introduction (other sections missing)
    mock_state.return_value = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "Introduction"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": " ".join(["word"] * 60)}]},
        ],
    }

    experiments = [
        {
            "id": "SK001",
            "workflow_id": 1,
            "name": "Test",
            "author": "Alice",
            "date": "2026-01-01",
            "protocol_count": 0,
        }
    ]

    flagged = run_check(
        experiments=experiments,
        base_url="https://api.labstep.com",
        headers={"apikey": "test"},
        webhook_url="https://hooks.slack.com/test",
        notified_path=notified_path,
    )

    assert len(flagged) == 1
    assert flagged[0]["id"] == "SK001"
    mock_notify.assert_called()


@patch("checker.get_experiment_state")
@patch("checker.send_slack_notification")
def test_run_check_skips_already_notified(mock_notify, mock_state, tmp_path):
    notified_path = str(tmp_path / "last_checked.json")
    # Pre-populate notified list
    with open(notified_path, "w") as f:
        json.dump(["SK001"], f)

    mock_state.return_value = {"type": "doc", "content": []}

    experiments = [
        {
            "id": "SK001",
            "workflow_id": 1,
            "name": "Test",
            "author": "Alice",
            "date": "2026-01-01",
            "protocol_count": 0,
        }
    ]

    flagged = run_check(
        experiments=experiments,
        base_url="https://api.labstep.com",
        headers={"apikey": "test"},
        webhook_url="https://hooks.slack.com/test",
        notified_path=notified_path,
    )

    assert len(flagged) == 0
    mock_notify.assert_not_called()
