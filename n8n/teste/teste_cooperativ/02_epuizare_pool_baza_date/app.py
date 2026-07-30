from flask import Flask, request, jsonify
from psycopg2.pool import SimpleConnectionPool

app = Flask(__name__)

pool = SimpleConnectionPool(
    minconn=1,
    maxconn=5,
    dsn="postgresql://app:app@postgres/orders",
)

@app.post("/orders")
def create_order():
    connection = pool.getconn()
    cursor = connection.cursor()

    try:
        payload = request.get_json()
        amount = float(payload["amount"])

        cursor.execute(
            "INSERT INTO orders(customer, amount) VALUES (%s, %s)",
            (payload["customer"], amount),
        )

        connection.commit()
        pool.putconn(connection)

        return jsonify(status="created"), 201

    except Exception as exc:
        connection.rollback()

        return jsonify(
            error=str(exc)
        ), 400
