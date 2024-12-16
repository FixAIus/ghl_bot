import json
from flask import Flask, jsonify, request


app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"okokok": "trainyuh🚅"})

def log(message, level="info", **kwargs):
    """
    Logs a structured message to Railway logs in JSON format.
    """
    log_entry = {"msg": message, "level": level}
    log_entry.update(kwargs)
    print(json.dumps(log_entry))


log(f"Hello fucker", variable='deez variable')


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
