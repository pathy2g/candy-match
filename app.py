from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

DB = 'candy_profiles.db'
app = Flask(__name__, static_folder='.')
app.config['MAX_CONTENT_LENGTH'] = 1_000_000


def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with get_db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS profiles (
            name       TEXT PRIMARY KEY,
            password   TEXT NOT NULL,
            high_score INTEGER DEFAULT 0,
            high_combo INTEGER DEFAULT 0
        )''')


@app.route('/')
def index():
    return send_from_directory('.', 'candy.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


@app.route('/api/profiles', methods=['GET'])
def list_profiles():
    with get_db() as db:
        rows = db.execute(
            'SELECT name, high_score, high_combo FROM profiles ORDER BY high_score DESC'
        ).fetchall()
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
        with get_db() as db:
            db.execute(
                'INSERT INTO profiles (name, password) VALUES (?, ?)',
                (name, generate_password_hash(password))
            )
        return jsonify({'ok': True})
    except sqlite3.IntegrityError:
        return jsonify({'ok': False, 'error': 'Name already taken'}), 409


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    name = (data.get('name') or '').strip().lower()
    password = (data.get('password') or '').strip()
    with get_db() as db:
        row = db.execute('SELECT * FROM profiles WHERE name=?', (name,)).fetchone()
    if not row or not check_password_hash(row['password'], password):
        return jsonify({'ok': False, 'error': 'Wrong name or password'}), 401
    return jsonify({'ok': True, 'highScore': row['high_score'], 'highCombo': row['high_combo']})


@app.route('/api/save', methods=['POST'])
def save_profile():
    data = request.get_json()
    name = (data.get('name') or '').strip().lower()
    password = (data.get('password') or '').strip()
    with get_db() as db:
        row = db.execute('SELECT * FROM profiles WHERE name=?', (name,)).fetchone()
    if not row or not check_password_hash(row['password'], password):
        return jsonify({'ok': False, 'error': 'Auth failed'}), 401
    hs = int(data.get('highScore', 0))
    hc = int(data.get('highCombo', 0))
    with get_db() as db:
        db.execute(
            'UPDATE profiles SET high_score=?, high_combo=? WHERE name=?',
            (hs, hc, name)
        )
    return jsonify({'ok': True})


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
