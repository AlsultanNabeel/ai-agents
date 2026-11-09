import os
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch


# Keep all test database changes isolated from the real resume database.
TEMP_DIR = tempfile.TemporaryDirectory()
TEST_DB_PATH = os.path.join(TEMP_DIR.name, "test_resume.db")
os.environ["RESUME_DB_PATH"] = TEST_DB_PATH

from flask_socketio import SocketIOTestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask_app import create_app
from flask_app.utils import socket_events
from flask_app.utils.embeddings import (
    EmbeddingError,
    semantic_search,
)


app, socketio = create_app()
db = app.db


def check(condition, message):
    """Raise an assertion with a readable explanation."""
    if not condition:
        raise AssertionError(message)

def create_test_skill(name):
    """Create a test skill and return its database ID."""
    experiences = db.query(
        "SELECT experience_id FROM experiences LIMIT 1"
    )

    check(experiences, "The test database has no experiences.")

    experience_id = experiences[0]["experience_id"]

    skill_id = db.insert_approved_record(
        "skills",
        {
            "experience_id": experience_id,
            "name": name,
            "skill_level": 3,
        },
    )

    return skill_id


def create_delete_action(skill_id, skill_name):
    """Build a canonical deletion proposal for one skill."""
    return {
        "operation": "delete_skill",
        "values": {
            "skill_ids": [skill_id],
        },
        "description": f"Delete skill '{skill_name}'.",
    }


def connect_client():
    """Create a Socket.IO test client."""
    return socketio.test_client(app)


def clear_pending_actions():
    """Remove pending proposals between independent scenarios."""
    with socket_events.pending_actions_lock:
        socket_events.pending_actions.clear()


def run_scenario(scenario_id, description, test_function):
    """Run one scenario and print its result."""
    try:
        test_function()
        print(f"{scenario_id}: PASS — {description}")
        return True
    except Exception as error:
        print(f"{scenario_id}: FAIL — {description}")
        print(f"    Reason: {error}")
        return False


def test_s6_rejection():
    """A 'no' reply must leave the proposed skill unchanged."""
    clear_pending_actions()

    skill_name = "S6 Rejection Test"
    skill_id = create_test_skill(skill_name)
    action = create_delete_action(skill_id, skill_name)

    with patch.object(
        socket_events,
        "handle_ai_chat_request",
        return_value={
            "status": "pending_approval",
            "action": action,
        },
    ):
        client = connect_client()

        client.emit("send_message", {"message": "Delete this test skill"})
        events = client.get_received()

        approval = next(
            event for event in events
            if event["name"] == "write_approval_required"
        )

        check(
            approval["args"][0]["proposal"]["operation"] == "delete_skill",
            "The wrong operation was proposed.",
        )

        client.emit("send_message", {"message": "no"})
        events = client.get_received()

        skill = db.query(
            "SELECT skill_id FROM skills WHERE skill_id = ?",
            (skill_id,),
        )

        check(skill, "The skill was deleted after rejection.")
        check(
            any(
                event["name"] == "receive_message"
                and "No database changes were made"
                in event["args"][0]["response"]
                for event in events
            ),
            "The rejection response was not received.",
        )

        client.disconnect()

    clear_pending_actions()


def test_s7_approval():
    """A 'yes' reply must execute exactly the proposed deletion."""
    clear_pending_actions()

    skill_name = "S7 Approval Test"
    skill_id = create_test_skill(skill_name)
    action = create_delete_action(skill_id, skill_name)

    with patch.object(
        socket_events,
        "handle_ai_chat_request",
        return_value={
            "status": "pending_approval",
            "action": action,
        },
    ):
        client = connect_client()

        client.emit("send_message", {"message": "Delete this test skill"})
        events = client.get_received()

        approval = next(
            event for event in events
            if event["name"] == "write_approval_required"
        )

        client.emit("send_message", {"message": "yes"})
        events = client.get_received()

        skill = db.query(
            "SELECT skill_id FROM skills WHERE skill_id = ?",
            (skill_id,),
        )

        check(not skill, "The approved skill was not deleted.")

        check(
            any(
                event["name"] == "receive_message"
                for event in events
            ),
            "No result was returned after approval.",
        )

        client.disconnect()

    clear_pending_actions()


def test_s8_ambiguous_and_invalidation():
    """Ambiguous replies do nothing; a new request invalidates approval."""
    clear_pending_actions()

    skill_name = "S8 Invalidation Test"
    skill_id = create_test_skill(skill_name)
    action = create_delete_action(skill_id, skill_name)

    def mocked_handler(db, role, message, trace=None):
        if message == "Delete this test skill":
            return {
                "status": "pending_approval",
                "action": action,
            }

        return "This is a separate request."

    with patch.object(
        socket_events,
        "handle_ai_chat_request",
        side_effect=mocked_handler,
    ):
        client = connect_client()

        client.emit("send_message", {"message": "Delete this test skill"})
        client.get_received()

        client.emit("send_message", {"message": "maybe"})
        events = client.get_received()

        check(
            any(
                event["name"] == "receive_message"
                and "no changes have been made"
                in event["args"][0]["response"].lower()
                for event in events
            ),
            "The ambiguous reply was not handled correctly.",
        )

        check(
            bool(socket_events.pending_actions),
            "The pending proposal disappeared after 'maybe'.",
        )

        client.emit("send_message", {"message": "Tell me something else"})
        client.get_received()

        check(
            not socket_events.pending_actions,
            "The old proposal was not invalidated.",
        )

        client.emit("send_message", {"message": "yes"})
        client.get_received()

        skill = db.query(
            "SELECT skill_id FROM skills WHERE skill_id = ?",
            (skill_id,),
        )

        check(
            skill,
            "The invalidated proposal was executed.",
        )

        client.disconnect()

    clear_pending_actions()


def test_s10_embedding_failure():
    """Embedding API failure must be reported without breaking database access."""
    with patch(
        "flask_app.utils.embeddings.generate_embedding",
        side_effect=EmbeddingError("Simulated embedding API failure"),
    ):
        try:
            semantic_search(db, "test query")
        except EmbeddingError as error:
            check(
                "Simulated embedding API failure" in str(error),
                "The wrong embedding error was returned.",
            )
        else:
            raise AssertionError(
                "Semantic search did not report the embedding failure."
            )

    # The database must remain usable after the failure.
    result = db.query("SELECT COUNT(*) FROM skills")

    check(result is not None, "Database access failed after the embedding error.")


def main():
    results = []

    print("\n--- Homework 2 scenario tests ---\n")

    results.append(run_scenario(
        "S6",
        "Rejecting a proposed deletion leaves the database unchanged",
        test_s6_rejection,
    ))

    results.append(run_scenario(
        "S7",
        "Approving a proposed deletion executes the exact action",
        test_s7_approval,
    ))

    results.append(run_scenario(
        "S8",
        "Ambiguous replies do nothing and new requests invalidate proposals",
        test_s8_ambiguous_and_invalidation,
    ))

    results.append(run_scenario(
        "S10",
        "Embedding failure is reported and the database remains usable",
        test_s10_embedding_failure,
    ))

    print("\n--- API-dependent scenarios ---")
    for scenario_id in ("S1", "S2", "S3", "S4", "S5", "S9", "S11"):
        print(f"{scenario_id}: API REQUIRED")

    passed = sum(results)
    failed = len(results) - passed

    print("\n--- Summary ---")
    print(f"Local scenarios passed: {passed}")
    print(f"Local scenarios failed: {failed}")
    print("API-dependent scenarios: 7")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()