"""
三圈交集 · 职业探索工具 — Flask 后端
提供多用户存储、结果分享、URL 访问能力
"""

import json
import sqlite3
import uuid
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ── 数据库 ──
DB_DIR = Path(__file__).parent / 'data'
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / 'results.db'


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                views INTEGER DEFAULT 0
            )
        """)


init_db()


# ── 路由 ──

@app.route('/')
def index():
    """首页：呈现工具"""
    return render_template('index.html')


@app.route('/r/<result_id>')
def shared_result(result_id):
    """分享链接：加载已有结果"""
    return render_template('index.html', result_id=result_id)


@app.route('/api/save', methods=['POST'])
def save():
    """保存结果，返回唯一分享链接"""
    data = request.get_json(silent=True)
    if not data or 'state' not in data:
        return jsonify({'error': '缺少 state 数据'}), 400

    result_id = uuid.uuid4().hex[:8]
    payload = json.dumps(data['state'], ensure_ascii=False)

    with get_db() as conn:
        conn.execute(
            'INSERT INTO results (id, data, created_at) VALUES (?, ?, ?)',
            (result_id, payload, datetime.now().isoformat())
        )

    return jsonify({
        'id': result_id,
        'url': f'/r/{result_id}'
    })


@app.route('/api/load/<result_id>')
def load(result_id):
    """通过分享 ID 加载结果"""
    with get_db() as conn:
        row = conn.execute(
            'SELECT data, views FROM results WHERE id = ?', (result_id,)
        ).fetchone()

    if not row:
        return jsonify({'error': '未找到该结果'}), 404

    # 增加访问计数
    with get_db() as conn:
        conn.execute(
            'UPDATE results SET views = views + 1 WHERE id = ?', (result_id,)
        )

    return jsonify({
        'state': json.loads(row['data']),
        'views': row['views'] + 1
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
