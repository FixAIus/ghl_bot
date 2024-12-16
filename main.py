import json


def log(message, level="info", **kwargs):
    """
    Logs a structured message to Railway logs in JSON format.
    """
    log_entry = {"msg": message, "level": level}
    log_entry.update(kwargs)
    print(json.dumps(log_entry))


log(f"Hello fucker", variable='deez variable')
