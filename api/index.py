"""
三圈交集 · 职业探索工具 — Vercel 入口
自动适配本地 SQLite 与生产 PostgreSQL
"""
import json, uuid, os
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ── 模板路径（Vercel 下 api/ 文件夹比项目根深一层） ──
_here = Path(__file__).parent
app.template_folder = str(_here.parent / 'templates')

# ── 数据库 ──

# 环境变量: Vercel Postgres / Neon 连接串
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')


def get_db():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn, True  # (conn, is_pg)
    else:
        # 本地 SQLite
        db_dir = _here.parent / 'data'
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / 'results.db'

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn, False


def init_db():
    conn, is_pg = get_db()
    try:
        if is_pg:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    views INTEGER DEFAULT 0
                )
            """)
            conn.commit()
            cur.close()
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    views INTEGER DEFAULT 0
                )
            """)
            conn.commit()
    finally:
        conn.close()


# ── 统一查询辅助 ──

def query_one(sql, params, is_pg):
    """返回 dict（或 None）"""
    conn, _ = get_db()
    try:
        cur = conn.cursor()
        if is_pg:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
            return None
        else:
            cur.execute(sql.replace('%s', '?'), params)
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def execute(sql, params, is_pg):
    conn, _ = get_db()
    try:
        cur = conn.cursor()
        if is_pg:
            cur.execute(sql, params)
            conn.commit()
        else:
            cur.execute(sql.replace('%s', '?'), params)
            conn.commit()
    finally:
        conn.close()


# ── 启动时建表 ──
init_db()


# ── 路由 ──

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/r/<result_id>')
def shared_result(result_id):
    return render_template('index.html', result_id=result_id)


@app.route('/api/save', methods=['POST'])
def save():
    data = request.get_json(silent=True)
    if not data or 'state' not in data:
        return jsonify({'error': '缺少 state 数据'}), 400

    result_id = uuid.uuid4().hex[:8]
    payload = json.dumps(data['state'], ensure_ascii=False)
    now = datetime.now().isoformat()
    is_pg = bool(DATABASE_URL)

    if is_pg:
        execute(
            'INSERT INTO results (id, data, created_at) VALUES (%s, %s, %s)',
            (result_id, payload, now), is_pg
        )
    else:
        execute(
            'INSERT INTO results (id, data, created_at) VALUES (?, ?, ?)',
            (result_id, payload, now), is_pg
        )

    return jsonify({'id': result_id, 'url': f'/r/{result_id}'})


@app.route('/api/load/<result_id>')
def load(result_id):
    is_pg = bool(DATABASE_URL)
    row = query_one(
        'SELECT data, views FROM results WHERE id = %s' if is_pg else
        'SELECT data, views FROM results WHERE id = ?',
        (result_id,), is_pg
    )

    if not row:
        return jsonify({'error': '未找到该结果'}), 404

    # 增加访问计数
    if is_pg:
        execute('UPDATE results SET views = views + 1 WHERE id = %s', (result_id,), is_pg)
    else:
        execute('UPDATE results SET views = views + 1 WHERE id = ?', (result_id,), is_pg)

    return jsonify({
        'state': json.loads(row['data']),
        'views': row['views'] + 1
    })


# ── Vercel 导出（必须） ──
handler = app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
