"""
三圈交集 · 职业探索工具 — Vercel 入口
自动适配本地 SQLite 与生产 PostgreSQL
"""
import json, uuid, os, re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, request, jsonify, render_template

# 预导入，避免 Vercel 热加载时遗漏
try:
    if os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL'):
        import pg8000
except ImportError:
    pass

app = Flask(__name__)

# ── 模板路径（Vercel 下 api/ 文件夹比项目根深一层） ──
_here = Path(__file__).parent
app.template_folder = str(_here.parent / 'templates')

# ── 环境变量 ──
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')

# ── 数据库（惰性初始化，避免 Vercel 导入时因 /tmp 问题崩溃） ──
_DB_INITED = False


def _ensure_db():
    global _DB_INITED
    if _DB_INITED:
        return
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
    _DB_INITED = True


def get_db():
    if DATABASE_URL:
        import pg8000
        import ssl

        # 解析 DATABASE_URL，按参数传递给 pg8000（避免 DSN 兼容性问题）
        parsed = urlparse(DATABASE_URL)
        pg_kwargs = {
            'user': parsed.username,
            'password': parsed.password or '',
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/').split('?')[0],
            'ssl_context': ssl.create_default_context(),
        }
        conn = pg8000.connect(**pg_kwargs)
        conn.autocommit = False
        return conn, True  # (conn, is_pg)
    else:
        # 本地 SQLite
        # Vercel 环境只能写入 /tmp
        db_dir = Path('/tmp/find-passion-tool') if os.environ.get('VERCEL') else (_here.parent / 'data')
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / 'results.db'

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn, False


def _auth_required():
    """返回 401 响应，弹出浏览器登录框"""
    return jsonify({'error': '需要登录'}), 401, {
        'WWW-Authenticate': 'Basic realm="管理后台"'
    }


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


# ── 路由 ──

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/debug')
def debug():
    """调试信息（不需要密码）"""
    info = {
        'DATABASE_URL_set': bool(DATABASE_URL),
        'DATABASE_URL_prefix': (DATABASE_URL or '')[:20] + '...' if DATABASE_URL else '(not set)',
        'VERCEL': bool(os.environ.get('VERCEL')),
        'ADMIN_USER': ADMIN_USER,
        'DB_INITED': _DB_INITED,
    }
    # 尝试连接数据库
    try:
        _ensure_db()
        info['db_status'] = 'ok'
        # 统计条数
        is_pg = bool(DATABASE_URL)
        if is_pg:
            conn, _ = get_db()
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) AS c FROM results')
            info['record_count'] = cur.fetchone()[0]
            cur.close()
            conn.close()
        else:
            conn, _ = get_db()
            cur = conn.execute('SELECT COUNT(*) AS c FROM results')
            info['record_count'] = cur.fetchone()['c']
            conn.close()
    except Exception as e:
        info['db_status'] = 'error'
        info['db_error'] = str(e)

    return jsonify(info)


@app.route('/admin')
def admin():
    """管理页面：查看所有已保存的结果（需登录）"""
    # 基本认证
    auth = request.authorization
    if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
        return _auth_required()

    try:
        _ensure_db()
    except Exception as e:
        return f'<h2>数据库初始化失败</h2><p>{e}</p><p>请配置 DATABASE_URL 环境变量。</p>', 500

    is_pg = bool(DATABASE_URL)
    rows = []
    if is_pg:
        conn, _ = get_db()
        cur = conn.cursor()
        cur.execute('SELECT id, created_at, views FROM results ORDER BY created_at DESC LIMIT 200')
        for r in cur.fetchall():
            rows.append(dict(r))
        cur.close()
        conn.close()
    else:
        conn, _ = get_db()
        cur = conn.execute('SELECT id, created_at, views FROM results ORDER BY created_at DESC LIMIT 200')
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

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
    return render_template('index.html', result_id=result_id)


@app.route('/api/save', methods=['POST'])
def save():
    _ensure_db()
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
    _ensure_db()
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
