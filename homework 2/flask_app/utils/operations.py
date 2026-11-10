import json

from flask_app.utils.embeddings import sync_embeddings

# The only database changes the agent may make. "destructive" is decided here,
# in code, never by the model.
ALLOWED_OPERATIONS = {
    'add_skill': {'params': ['skill_name', 'experience_name', 'skill_level'], 'destructive': False},
    'delete_skill': {'params': ['skill_name', 'experience_name'], 'destructive': True},
    'delete_all_skills': {'params': [], 'destructive': True},
}


class OperationError(Exception):
    pass


class ApprovalRequired(Exception):
    def __init__(self, operation):
        super().__init__(describe_operation(operation))
        self.operation = operation


def parse_operation(db, text):
    try:
        data = json.loads(text)
    except ValueError:
        raise OperationError(f"not valid JSON: {text!r}")
    if not isinstance(data, dict):
        raise OperationError("the operation must be a JSON object")

    name = data.get('operation')
    params = data.get('params', {})
    if name not in ALLOWED_OPERATIONS:
        raise OperationError(f"unknown operation {name!r}")
    if not isinstance(params, dict) or set(params) != set(ALLOWED_OPERATIONS[name]['params']):
        raise OperationError(f"{name} needs exactly these values: {ALLOWED_OPERATIONS[name]['params']}")

    for key in ('skill_name', 'experience_name'):
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise OperationError(f"{key} must be a non-empty text")
    if 'skill_level' in params:
        level = params['skill_level']
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 10:
            raise OperationError("skill_level must be a whole number from 1 to 10")
    if 'experience_name' in params and not _experience_id(db, params['experience_name']):
        raise OperationError(f"no experience named {params['experience_name']!r}")
    if name == 'delete_skill' and not _skill_ids(db, params['skill_name'], params['experience_name']):
        raise OperationError(f"{params['skill_name']!r} is not a skill of {params['experience_name']!r}")

    return {'operation': name, 'params': params}


def describe_operation(operation):
    params = operation['params']
    if operation['operation'] == 'add_skill':
        return (f"This will add skill '{params['skill_name']}' (level {params['skill_level']}) "
                f"to experience '{params['experience_name']}'.")
    if operation['operation'] == 'delete_skill':
        return f"This will delete skill '{params['skill_name']}' from experience '{params['experience_name']}'."
    return "This will delete ALL skills from the database."


def perform_operation(db, operation, approved=False):
    # The approval check lives here, in the only code that writes, so no expert
    # and no wording can delete anything without a matching "yes"
    if ALLOWED_OPERATIONS[operation['operation']]['destructive'] and not approved:
        raise ApprovalRequired(operation)

    params = operation['params']
    if operation['operation'] == 'add_skill':
        experience_id = _experience_id(db, params['experience_name'])
        if _skill_ids(db, params['skill_name'], params['experience_name']):
            return "Element already exists in the skills table."
        db.query(
            "INSERT INTO skills (experience_id, name, skill_level) VALUES (?, ?, ?)",
            (experience_id, params['skill_name'], params['skill_level']),
        )
        outcome = f"New {params['skill_name']} added to the skills table."
    elif operation['operation'] == 'delete_skill':
        for skill_id in _skill_ids(db, params['skill_name'], params['experience_name']):
            db.query("DELETE FROM skills WHERE skill_id = ?", (skill_id,))
        outcome = f"Deleted skill '{params['skill_name']}' from experience '{params['experience_name']}'."
    else:
        db.query("DELETE FROM skills")
        outcome = "Deleted all skills."

    sync_embeddings(db)
    return outcome


def _experience_id(db, experience_name):
    rows = db.query("SELECT experience_id FROM experiences WHERE name = ?", (experience_name,))
    return rows[0]['experience_id'] if rows else None


def _skill_ids(db, skill_name, experience_name):
    rows = db.query(
        "SELECT s.skill_id FROM skills s JOIN experiences e ON s.experience_id = e.experience_id "
        "WHERE s.name = ? AND e.name = ?",
        (skill_name, experience_name),
    )
    return [row['skill_id'] for row in rows]

