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


ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')


# ── 路由 ──

@app.route('/')
def index():
    """首页：呈现工具"""
    return render_template('index.html')


@app.route('/admin')
def admin():
    """管理页面：查看所有已保存的结果（需登录）"""
    auth = request.authorization
    if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
        return jsonify({'error': '需要登录'}), 401, {
            'WWW-Authenticate': 'Basic realm="管理后台"'
        }

    rows = []
    with get_db() as conn:
        cur = conn.execute('SELECT id, created_at, views FROM results ORDER BY created_at DESC LIMIT 200')
        rows = [dict(r) for r in cur.fetchall()]

    items = ''.join(
        f'<tr>'
        f'<td><a href="/r/{r["id"]}" target="_blank">{r["id"]}</a></td>'
        f'<td>{r["created_at"]}</td>'
        f'<td>{r["views"]}</td>'
        f'</tr>'
        for r in rows
    )
    if not items:
        items = '<tr><td colspan="3" style="text-align:center;color:#999;padding:40px;">暂无保存记录</td></tr>'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>管理后台 - 三圈交集</title>
<style>
  body {{ font-family: -apple-system, "PingFang SC", sans-serif; max-width: 800px; margin: 0 auto; padding: 40px 20px; background: #f8f9fa; }}
  h1 {{ font-size: 22px; color: #2D3436; margin-bottom: 8px; }}
  p {{ color: #999; font-size: 14px; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
  th {{ background: #2D3436; color: white; padding: 12px 16px; text-align: left; font-size: 13px; }}
  td {{ padding: 10px 16px; font-size: 13px; border-bottom: 1px solid #eee; }}
  td a {{ color: #5B8FB9; text-decoration: none; font-weight: 600; }}
  td a:hover {{ text-decoration: underline; }}
  tr:hover td {{ background: #f5f7fa; }}
  .count {{ margin-top: 16px; font-size: 13px; color: #999; }}
</style></head>
<body>
  <h1>📊 管理后台</h1>
  <p>所有保存的三圈交集结果</p>
  <table>
    <thead><tr><th>ID</th><th>保存时间</th><th>访问次数</th></tr></thead>
    <tbody>{items}</tbody>
  </table>
  <div class="count">共 {len(rows)} 条记录</div>
</body></html>'''


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
