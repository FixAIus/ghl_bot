from flask import Flask, jsonify, request
import os

app = Flask(__name__)

deez = os.getenv("tezt")

@app.route('/')
def index():
    return jsonify({"okokok": "trainyuh🚅"})


@app.route('/firstTest', methods=['POST'])
def test():
    data = request.json
    return jsonify({"the data": deez, "also": data})


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
