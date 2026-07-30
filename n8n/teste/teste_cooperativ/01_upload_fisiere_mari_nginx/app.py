from flask import Flask, request, jsonify

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

@app.post("/upload")
def upload():
    uploaded = request.files.get("file")

    if uploaded is None:
        return jsonify(error="missing file"), 400

    uploaded.save(f"/data/uploads/{uploaded.filename}")

    return jsonify(
        status="saved",
        filename=uploaded.filename,
    ), 201

app.run(host="0.0.0.0", port=5000)
