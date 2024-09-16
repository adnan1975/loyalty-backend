from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import sql

app = Flask(__name__)

# Database connection parameters
DB_PARAMS = {
    'dbname': 'your_database_name',
    'user': 'your_username',
    'password': 'your_password',
    'host': 'your_host',
    'port': 'your_port'
}

def get_db_connection():
    conn = psycopg2.connect(**DB_PARAMS)
    return conn

@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')

    if not name or not phone:
        return jsonify({"error": "Name and phone number are required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, phone, email, points) VALUES (%s, %s, %s, %s) RETURNING id",
        (name, phone, email, 0)
    )
    user_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    # Generate a QR code for the user (implementation not shown here)
    qr_code = "generated_qr_code_url"

    return jsonify({"user_id": user_id, "qr_code": qr_code}), 201

@app.route('/add_points/<int:user_id>', methods=['POST'])
def add_points(user_id):
    data = request.json
    points = data.get('points', 0)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET points = points + %s WHERE id = %s",
        (points, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Points added successfully"}), 200

@app.route('/redeem_reward/<int:user_id>', methods=['POST'])
def redeem_reward(user_id):
    data = request.json
    points_needed = data.get('points_needed', 0)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT points FROM users WHERE id = %s",
        (user_id,)
    )
    user_points = cur.fetchone()[0]

    if user_points < points_needed:
        return jsonify({"error": "Not enough points"}), 400

    cur.execute(
        "UPDATE users SET points = points - %s WHERE id = %s",
        (points_needed, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Reward redeemed successfully"}), 200

if __name__ == '__main__':
    app.run(debug=True)
