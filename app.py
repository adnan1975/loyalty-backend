from flask import Flask, request, jsonify
import psycopg2
import secrets
import qrcode
from io import BytesIO
import base64
import json  # Ensure you import json for data serialization



app = Flask(__name__)

# Database connection parameters
DB_PARAMS = {
    'dbname': 'loyaltydb_uqqa',
    'user': 'appuser',
    'password': 'E6aWZbAlVha6VCfd0pBzNezR3bW8sAQP',
    'host': 'dpg-crjp5kjtq21c73a4kcm0-a',
    'port': '5432'
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
    placeholder_password = secrets.token_hex(16)

    if not name or not phone:
        return jsonify({"error": "Name and phone number are required"}), 400


    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, phone, email, points, password) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (name, phone, email, 100, placeholder_password)
        )
        result = cur.fetchone()
        if result is None:
            return jsonify({"error": "Failed to retrieve user ID"}), 500
        user_id = result[0]
        conn.commit()
        
        # Format data for QR code
        qr_data = {
            "user_id": user_id,
            "phone": phone,
            "email": email
        }
        
        # Convert dictionary to JSON string
        qr_data_json = json.dumps(qr_data)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data_json)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')

        # Convert QR code image to base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Store QR code in the database
        cur.execute(
            "UPDATE users SET qr_code = %s WHERE id = %s",
            (qr_code_base64, user_id)
        )
        conn.commit()
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    
    return jsonify({"user_id": user_id, "qr_code": f"data:image/png;base64,{qr_code_base64}"}), 201


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

@app.route('/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500



def drop_all_tables():
    drop_qrcodes_table = "DROP TABLE IF EXISTS qrcodes;"
    drop_users_table = "DROP TABLE IF EXISTS users;"
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(drop_qrcodes_table)
    cur.execute(drop_users_table)
    
    conn.commit()
    cur.close()
    conn.close()

def create_tables():
    create_users_table = """
    CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY,
      name VARCHAR(100),
      phone VARCHAR(20) UNIQUE NOT NULL,
      email VARCHAR(100),
      password VARCHAR(255) NOT NULL,
      points INTEGER DEFAULT 0,
      marketing_opt_in BOOLEAN DEFAULT FALSE,
      qr_code TEXT
    );
    """
    
    create_qrcodes_table = """
    CREATE TABLE IF NOT EXISTS qrcodes (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      qr_code_data TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(create_users_table)
    cur.execute(create_qrcodes_table)
    
    conn.commit()
    cur.close()
    conn.close()

@app.route('/reset-database', methods=['POST'])
def reset_database():
    try:
        drop_all_tables()
        create_tables()
        return jsonify({"message": "Database reset successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, phone, email, qr_code FROM users WHERE id = %s",
        (user_id,)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user is None:
        return jsonify({"error": "User not found"}), 404

    user_data = {
        "user_id": user[0],
        "name": user[1],
        "phone": user[2],
        "email": user[3],
        "qr_code": f"data:image/png;base64,{user[4]}"
    }

    return jsonify(user_data), 200

@app.route('/login', methods=['POST'])
def login_user():
    data = request.json
    phone = data.get('phone')
    if not phone :
        return jsonify({"error": "Phone number   is required"}), 400

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE phone = %s",
                (phone,)
            )
            result = cur.fetchone()
            if result is None:
                return jsonify({"error": "Invalid phone number"}), 401
            
            user_id = result

            
            # Fetch user data (e.g., points and QR code)
            cur.execute(
                "SELECT points, qr_code FROM users WHERE id = %s",
                (user_id)
            )
            user_data = cur.fetchone()
            if user_data is None:
                return jsonify({"error": "User data not found"}), 500

            points, qr_code = user_data

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    return jsonify({
        "user_id": user_id,
        "points": points,
        "qr_code": qr_code
    }), 200