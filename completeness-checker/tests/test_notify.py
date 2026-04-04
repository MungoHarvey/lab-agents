from unittest.mock import patch, MagicMock
from notify import format_experiment_message, format_summary_message, send_slack_notification


def test_format_experiment_message_with_flags():
    experiment = {
        "id": "SK543",
        "name": "My Experiment",
        "author": "Joe Bloggs",
        "date": "2026-03-15",
        "workflow_id": 12345,
    }
    flags = [
        {"section": "results", "score": "red", "word_count": 0},
        {"section": "discussion", "score": "red", "word_count": 3},
        {"section": "protocol", "score": "red", "word_count": 0},
    ]
    msg = format_experiment_message(experiment, flags)
    assert "SK543" in msg
    assert "My Experiment" in msg
    assert "Results" in msg or "results" in msg
    assert "Discussion" in msg or "discussion" in msg
    assert "protocol" in msg.lower()
    assert "Joe Bloggs" in msg
    assert "12345" in msg


def test_format_summary_message():
    msg = format_summary_message(15)
    assert "15" in msg


@patch("notify.requests.post")
def test_send_slack_notification(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    send_slack_notification("https://hooks.slack.com/test", "Hello")
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "Hello" in str(call_kwargs)
