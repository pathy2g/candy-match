from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import psycopg2.errors
import os

DATABASE_URL = os.environ.get('DATABASE_URL')
app = Flask(__name__, static_folder='.')
app.config['MAX_CONTENT_LENGTH'] = 1_000_000


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''CREATE TABLE IF NOT EXISTS profiles (
            name       TEXT PRIMARY KEY,
            password   TEXT NOT NULL,
            high_score INTEGER DEFAULT 0,
            high_combo INTEGER DEFAULT 0
        )''')
    conn.commit()
    conn.close()


@app.route('/')
def index():
    return send_from_directory('.', 'candy.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


@app.route('/api/profiles', methods=['GET'])
def list_profiles():
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT name, high_score, high_combo FROM profiles ORDER BY high_score DESC')
        rows = cur.fetchall()
    conn.close()
    return jsonify([
        {'name': r['name'], 'highScore': r['high_score'], 'highCombo': r['high_combo']}
        for r in rows
    ])


@app.route('/api/profiles', methods=['POST'])
def create_profile():
    data = request.get_json()
    name = (data.get('name') or '').strip().lower()
    password = (data.get('password') or '').strip()
    if not name or not password:
        return jsonify({'ok': False, 'error': 'Name and password required'}), 400
    if len(name) > 16 or len(password) > 128:
        return jsonify({'ok': False, 'error': 'Input too long'}), 400
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO profiles (name, password) VALUES (%s, %s)',
                (name, generate_password_hash(password))
            )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except psycopg2.errors.UniqueViolation:
        return jsonify({'ok': False, 'error': 'Name already taken'}), 409


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    name = (data.get('name') or '').strip().lower()
    password = (data.get('password') or '').strip()
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT * FROM profiles WHERE name=%s', (name,))
        row = cur.fetchone()
    conn.close()
    if not row or not check_password_hash(row['password'], password):
        return jsonify({'ok': False, 'error': 'Wrong name or password'}), 401
    return jsonify({'ok': True, 'highScore': row['high_score'], 'highCombo': row['high_combo']})


@app.route('/api/save', methods=['POST'])
def save_profile():
    data = request.get_json()
    name = (data.get('name') or '').strip().lower()
    password = (data.get('password') or '').strip()
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT * FROM profiles WHERE name=%s', (name,))
        row = cur.fetchone()
    if not row or not check_password_hash(row['password'], password):
        conn.close()
        return jsonify({'ok': False, 'error': 'Auth failed'}), 401
    hs = int(data.get('highScore', 0))
    hc = int(data.get('highCombo', 0))
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE profiles SET high_score=%s, high_combo=%s WHERE name=%s',
            (hs, hc, name)
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
