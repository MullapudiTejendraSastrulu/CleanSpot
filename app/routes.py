from flask import Blueprint, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
import datetime
import secrets
import os
from functools import wraps
from app.database import get_db

main = Blueprint('main', __name__)

# Configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = '1234'
active_tokens = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split(' ')[1]
        if token not in active_tokens:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

@main.route('/api/report', methods=['POST'])
def create_report():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    save_name = f"{timestamp}_{filename}"
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], save_name))

    location = request.form.get('location', '')
    category = request.form.get('category', '')
    description = request.form.get('description', '')
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reports (image_path, location, category, description, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (save_name, location, category, description, created_at))
    conn.commit()
    report_id = cur.lastrowid
    conn.close()

    return jsonify({'id': report_id, 'image_url': f'/uploads/{save_name}'}), 201

@main.route('/api/reports', methods=['GET'])
def list_reports():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, image_path, location, category, description, status, created_at
        FROM reports
        ORDER BY id DESC LIMIT 50
    """).fetchall()
    conn.close()

    reports = []
    for r in rows:
        reports.append({
            'id': r['id'],
            'image_url': f'/uploads/{r["image_path"]}',
            'location': r['location'],
            'category': r['category'],
            'description': r['description'],
            'status': r['status'],
            'created_at': r['created_at']
        })
    return jsonify(reports)

@main.route('/api/report/<int:report_id>', methods=['GET'])
def get_report(report_id):
    conn = get_db()
    r = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    conn.close()
    if not r:
        return jsonify({'error': 'Report not found'}), 404

    return jsonify({
        'id': r['id'],
        'image_url': f'/uploads/{r["image_path"]}',
        'location': r['location'],
        'category': r['category'],
        'description': r['description'],
        'status': r['status'],
        'created_at': r['created_at']
    })

@main.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@main.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@main.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = secrets.token_urlsafe(32)
        active_tokens[token] = {'username': username, 'created': datetime.datetime.utcnow()}
        return jsonify({'token': token})
    
    return jsonify({'error': 'Invalid credentials'}), 401

@main.route('/api/admin/reports', methods=['GET'])
@require_auth
def admin_list_reports():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, image_path, location, category, description, status, created_at
        FROM reports
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    reports = []
    for r in rows:
        reports.append({
            'id': r['id'],
            'image_url': f'/uploads/{r["image_path"]}',
            'location': r['location'],
            'category': r['category'],
            'description': r['description'],
            'status': r['status'],
            'created_at': r['created_at']
        })
    return jsonify(reports)

@main.route('/api/admin/report/<int:report_id>/status', methods=['PUT'])
@require_auth
def update_report_status(report_id):
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in ['pending', 'in-progress', 'resolved']:
        return jsonify({'error': 'Invalid status'}), 400
    
    conn = get_db()
    conn.execute("UPDATE reports SET status = ? WHERE id = ?", (new_status, report_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@main.route('/api/admin/report/<int:report_id>', methods=['DELETE'])
@require_auth
def delete_report(report_id):
    conn = get_db()
    r = conn.execute("SELECT image_path FROM reports WHERE id = ?", (report_id,)).fetchone()
    if r:
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], r['image_path'])
        if os.path.exists(image_path):
            os.remove(image_path)
    
    conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@main.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@main.route('/admin')
def admin():
    return send_from_directory('templates', 'admin.html')

@main.route('/db')
def view_db():
    conn = get_db()
    reports = conn.execute('SELECT * FROM reports ORDER BY id DESC').fetchall()
    conn.close()
    
    html = '''<html><head><title>CleanSpot Database</title><style>
    body{font-family:Arial,sans-serif;margin:20px;background:#f0fdf4}
    h1{color:#15803d;text-align:center}
    table{width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden}
    th,td{padding:12px;text-align:left;border-bottom:1px solid #d1fae5}
    th{background:#22c55e;color:white}
    tr:hover{background:#f0fdf4}
    </style></head><body>
    <h1>🌱 CleanSpot Database Contents</h1>
    <table><tr><th>ID</th><th>Image</th><th>Location</th><th>Category</th><th>Description</th><th>Status</th><th>Created</th></tr>'''
    for r in reports:
        html += f'<tr><td>{r["id"]}</td><td>{r["image_path"]}</td><td>{r["location"]}</td><td>{r["category"]}</td><td>{r["description"]}</td><td>{r["status"]}</td><td>{r["created_at"]}</td></tr>'
    html += '</table></body></html>'
    return html