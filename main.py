from flask import Flask, jsonify
import os

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({"okokok": "train🚅"})



@app.route('/firstTest')
def test():
    data = request.json
    return jsonify({"the data": data})


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
