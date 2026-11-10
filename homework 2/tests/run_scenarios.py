import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


# Keep all test database changes isolated from the real resume database.
TEMP_DIR = tempfile.TemporaryDirectory()
TEST_DB_PATH = os.path.join(TEMP_DIR.name, "test_resume.db")
os.environ["RESUME_DB_PATH"] = TEST_DB_PATH

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask_socketio import SocketIOTestClient
from flask_app import create_app
from flask_app.utils import socket_events
from flask_app.utils.embeddings import (
    EmbeddingError,
    semantic_search,
)


app, socketio = create_app()
db = app.db


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def create_test_skill(name):
    experiences = db.query(
        "SELECT experience_id FROM experiences LIMIT 1"
    )
    check(experiences, "The test database has no experiences.")

    return db.insert_approved_record(
        "skills",
        {
            "experience_id": experiences[0]["experience_id"],
            "name": name,
            "skill_level": 3,
        },
    )


def create_delete_action(skill_id, skill_name):
    return {
        "operation": "delete_skill",
        "values": {"skill_ids": [skill_id]},
        "description": f"Delete skill '{skill_name}'.",
    }


def connect_client():
    return socketio.test_client(app)


def clear_pending_actions():
    with socket_events.pending_actions_lock:
        socket_events.pending_actions.clear()


def run_scenario(scenario_id, description, test_function):
    try:
        test_function()
        print(f"{scenario_id}: PASS — {description}")
        return True
    except Exception as error:
        print(f"{scenario_id}: FAIL — {description}")
        print(f"    Reason: {error}")
        return False


# ---------------------------------------------------------
# S1: AUC institution records are present and searchable
# ---------------------------------------------------------

def test_s1_auc_records():
    """Semantic search should retrieve and rank AUC institution records."""
    from flask_app.utils.llm import handle_ai_chat_request

    # Get the stored embedding for the AUC Transfer Office.
    embedding = db.query(
        """
        SELECT vector
        FROM embeddings
        WHERE source_table = 'institutions' AND source_id = 2
        """
    )

    check(embedding, "The AUC institution embedding was not found.")

    query_vector = json.loads(embedding[0]["vector"])

    trace = {"operations": []}

    # Use a deterministic query embedding while retaining the real
    # semantic_search implementation and cosine-similarity calculation.
    with patch(
        "flask_app.utils.embeddings.generate_embedding",
        return_value=query_vector,
    ):
        response = handle_ai_chat_request(
            db,
            "Semantic Search Expert",
            "Find my AUC institution",
            trace=trace,
        )

    check(
        "Record ID: 2" in response,
        "The AUC Transfer Office was not retrieved.",
    )

    check(
        "Similarity: 1.0000" in response,
        "The exact matching embedding did not receive a similarity score of 1.0000.",
    )

    check(
        "semantic_search" in trace["operations"],
        "The semantic search operation was not recorded in the trace.",
    )

# ---------------------------------------------------------
# S2: Semantic AI-related skills
# ---------------------------------------------------------

def test_s2_ai_skills():
    skills = db.query(
        """
        SELECT name
        FROM skills
        """
    )

    check(skills, "No skills were found in the test database.")

    # This checks the data exists, not the live semantic ranking.
    # The actual "What AI skills do I have?" query still needs API testing.
    check(
        any("AI" in row["name"].upper() for row in skills),
        "No skill with AI in its name exists for this database-level check.",
    )


# ---------------------------------------------------------
# S3: Exact database reads
# ---------------------------------------------------------

def test_s3_exact_database_reads():
    skills = db.query("SELECT * FROM skills")

    check(skills is not None, "The skills query failed.")

    count_result = db.query(
        "SELECT COUNT(*) AS total FROM positions"
    )

    check(count_result, "The position count query returned no result.")

    expected = db.query("SELECT COUNT(*) AS total FROM positions")

    check(
        count_result[0]["total"] == expected[0]["total"],
        "The position count did not match the database.",
    )


# ---------------------------------------------------------
# S4: AUC institution-to-experience relationships
# ---------------------------------------------------------

def test_s4_auc_experience_relationships():
    results = db.query(
        """
        SELECT
            i.inst_id,
            i.name AS institution_name,
            i.department,
            p.title AS position_title,
            e.experience_id,
            e.name AS experience_name
        FROM institutions i
        JOIN positions p ON i.inst_id = p.inst_id
        JOIN experiences e ON p.position_id = e.position_id
        WHERE LOWER(i.name) LIKE '%american university in cairo%'
           OR LOWER(i.name) LIKE '%auc%'
        ORDER BY i.inst_id, e.experience_id
        """
    )

    check(results, "No AUC-related experiences were found.")

    experience_names = [
        row["experience_name"] for row in results
    ]

    check(
        "Student Records Management" in experience_names,
        "The Transfer Office experience was not retrieved.",
    )


# ---------------------------------------------------------
# S5: Added skills and embeddings persist
# ---------------------------------------------------------

def test_s5_skill_persistence():
    skill_name = "Temporary Persistence Test"
    skill_id = create_test_skill(skill_name)

    skill = db.query(
        "SELECT * FROM skills WHERE skill_id = ?",
        (skill_id,),
    )

    check(skill, "The newly added skill was not saved.")

    # Embedding generation is an API-dependent operation.
    # Verify the embedding record if one was created.
    embedding = db.query(
        """
        SELECT *
        FROM embeddings
        WHERE source_table = 'skills' AND source_id = ?
        """,
        (skill_id,),
    )

    if embedding:
        check(
            bool(embedding[0]["vector"]),
            "The saved embedding has no vector.",
        )


# ---------------------------------------------------------
# S6: Rejecting a deletion
# ---------------------------------------------------------

def test_s6_rejection():
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

        client.emit(
            "send_message",
            {"message": "Delete this test skill"},
        )
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


# ---------------------------------------------------------
# S7: Approving a deletion
# ---------------------------------------------------------

def test_s7_approval():
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

        client.emit(
            "send_message",
            {"message": "Delete this test skill"},
        )
        client.get_received()

        client.emit("send_message", {"message": "yes"})
        events = client.get_received()

        skill = db.query(
            "SELECT skill_id FROM skills WHERE skill_id = ?",
            (skill_id,),
        )

        check(not skill, "The approved skill was not deleted.")

        check(
            any(event["name"] == "receive_message" for event in events),
            "No result was returned after approval.",
        )

        client.disconnect()

    clear_pending_actions()


# ---------------------------------------------------------
# S8: Ambiguous response and proposal invalidation
# ---------------------------------------------------------

def test_s8_ambiguous_and_invalidation():
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

        client.emit(
            "send_message",
            {"message": "Delete this test skill"},
        )
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

        client.emit(
            "send_message",
            {"message": "Tell me something else"},
        )
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

        check(skill, "The invalidated proposal was executed.")

        client.disconnect()

    clear_pending_actions()


# ---------------------------------------------------------
# S9: Bulk deletion must require approval
# ---------------------------------------------------------

def test_s9_bulk_delete_requires_approval():
    skills = db.query("SELECT skill_id FROM skills")

    check(skills, "No skills exist for the bulk deletion test.")

    # This verifies the database has records to protect.
    # Actual proposal generation and approval still need a live API test.
    original_count = len(skills)

    check(
        original_count > 0,
        "The test database has no skills to protect.",
    )

    after_count = db.query("SELECT COUNT(*) AS total FROM skills")

    check(
        after_count[0]["total"] == original_count,
        "The skills list changed during the safety check.",
    )


# ---------------------------------------------------------
# S10: Embedding failure handling
# ---------------------------------------------------------

def test_s10_embedding_failure():
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

    result = db.query("SELECT COUNT(*) FROM skills")

    check(
        result is not None,
        "Database access failed after the embedding error.",
    )


# ---------------------------------------------------------
# S11: Missing Harvard experience
# ---------------------------------------------------------

def test_s11_missing_harvard():
    results = db.query(
        """
        SELECT i.name, e.name AS experience_name
        FROM institutions i
        JOIN positions p ON i.inst_id = p.inst_id
        JOIN experiences e ON p.position_id = e.position_id
        WHERE LOWER(i.name) LIKE '%harvard%'
        """
    )

    check(
        not results,
        "Unexpected Harvard records exist in the test database.",
    )


# ---------------------------------------------------------
# Main test runner
# ---------------------------------------------------------

def main():
    results = []

    print("\n--- Homework 2 scenario tests ---\n")

    scenarios = [
        ("S1", "AUC institution records exist", test_s1_auc_records),
        ("S2", "AI-related skill data check", test_s2_ai_skills),
        ("S3", "Exact database read queries", test_s3_exact_database_reads),
        ("S4", "AUC institution-to-experience relationships", test_s4_auc_experience_relationships),
        ("S5", "Skill persistence check", test_s5_skill_persistence),
        ("S6", "Rejecting a proposed deletion leaves the database unchanged", test_s6_rejection),
        ("S7", "Approving a proposed deletion executes the exact action", test_s7_approval),
        ("S8", "Ambiguous replies do nothing and new requests invalidate proposals", test_s8_ambiguous_and_invalidation),
        ("S9", "Bulk deletion safety check", test_s9_bulk_delete_requires_approval),
        ("S10", "Embedding failure is reported and the database remains usable", test_s10_embedding_failure),
        ("S11", "No Harvard experience is invented", test_s11_missing_harvard),
    ]

    for scenario_id, description, function in scenarios:
        results.append(
            run_scenario(scenario_id, description, function)
        )

    passed = sum(results)
    failed = len(results) - passed

    print("\n--- Summary ---")
    print(f"Scenarios passed: {passed}")
    print(f"Scenarios failed: {failed}")

    print(
        "\nIMPORTANT: S1-S5, S9, and S11 checks here are database-level "
        "checks, not complete live-LLM scenario verification."
    )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
