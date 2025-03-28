from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'static/uploads')

# 添加静态文件路由
@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True,
        conditional=True
    )

# 初始化数据库
def init_db():
    with sqlite3.connect(os.getenv('DATABASE_PATH', 'versions.db')) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS versions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      system_type TEXT,
                      version TEXT,
                      file_path TEXT,
                      file_size INTEGER,
                      upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

@app.route('/api/versions')
def api_versions():
    with sqlite3.connect(os.getenv('DATABASE_PATH', 'versions.db')) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, system_type, version, file_path, file_size, upload_time FROM versions ORDER BY upload_time DESC")
        versions = [dict(row) for row in cursor.fetchall()]
    return jsonify(versions)

@app.route('/')
def index():
    with sqlite3.connect(os.getenv('DATABASE_PATH', 'versions.db')) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT system_type, version, file_path, file_size, upload_time FROM versions ORDER BY upload_time DESC")
        versions = cursor.fetchall()
    return render_template('index.html', versions=versions)

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    
    system_type = request.form['system_type']
    version = request.form['version']
    # 清理文件名中的特殊字符
    safe_filename = file.filename.replace(' ', '_').replace('(', '').replace(')', '')
    filename = f"{system_type}_{version}_{safe_filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    with sqlite3.connect(os.getenv('DATABASE_PATH', 'versions.db')) as conn:
        c = conn.cursor()
        # 检查是否存在相同版本
        c.execute("SELECT id, file_path FROM versions WHERE system_type = ? AND version = ?", (system_type, version))
        existing_version = c.fetchone()
        
        if existing_version:
            # 如果存在相同版本，删除旧文件
            old_file_path = existing_version[1]
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
            # 更新数据库记录
            file.save(filepath)
            file_size = os.path.getsize(filepath)
            c.execute("UPDATE versions SET file_path = ?, file_size = ? WHERE id = ?",
                      (filepath, file_size, existing_version[0]))
        else:
            # 如果不存在相同版本，创建新记录
            file.save(filepath)
            file_size = os.path.getsize(filepath)
            c.execute("INSERT INTO versions (system_type, version, file_path, file_size) VALUES (?, ?, ?, ?)",
                      (system_type, version, filepath, file_size))
        conn.commit()
    return 'File uploaded successfully'

@app.route('/api/delete_version/<int:version_id>', methods=['DELETE'])
def delete_version(version_id):
    with sqlite3.connect(os.getenv('DATABASE_PATH', 'versions.db')) as conn:
        c = conn.cursor()
        c.execute("SELECT file_path FROM versions WHERE id = ?", (version_id,))
        file_path = c.fetchone()[0]
        if os.path.exists(file_path):
            os.remove(file_path)
        c.execute("DELETE FROM versions WHERE id = ?", (version_id,))
        conn.commit()
    return jsonify({'status': 'success'})

@app.route('/api/update_version/<int:version_id>', methods=['PUT'])
def update_version(version_id):
    data = request.get_json()
    new_version = data.get('version')
    
    if not new_version:
        return jsonify({'status': 'error', 'message': '版本号不能为空'})
    
    with sqlite3.connect(os.getenv('DATABASE_PATH', 'versions.db')) as conn:
        c = conn.cursor()
        # 获取当前版本信息
        c.execute("SELECT system_type, file_path FROM versions WHERE id = ?", (version_id,))
        current = c.fetchone()
        if not current:
            return jsonify({'status': 'error', 'message': '版本不存在'})
            
        system_type, old_file_path = current
        
        # 检查新版本号是否已存在
        c.execute("SELECT id FROM versions WHERE system_type = ? AND version = ? AND id != ?",
                  (system_type, new_version, version_id))
        if c.fetchone():
            return jsonify({'status': 'error', 'message': '版本号已存在'})
        
        # 更新文件名和数据库记录
        new_filename = old_file_path.split('/')[-1].replace(old_file_path.split('_')[1], new_version)
        new_file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        
        if os.path.exists(old_file_path):
            os.rename(old_file_path, new_file_path)
            c.execute("UPDATE versions SET version = ?, file_path = ? WHERE id = ?",
                      (new_version, new_file_path, version_id))
            conn.commit()
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': '文件不存在'})

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(host='0.0.0.0', port=5002, debug=True)