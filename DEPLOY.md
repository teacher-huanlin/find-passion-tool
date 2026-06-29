# 部署指南 — 三圈交集 · 职业探索工具

## 项目结构

```
find-passion-tool/
├── api/
│   └── index.py       ← Vercel 入口（Flask 应用）
├── templates/
│   └── index.html     ← 前端工具页面
├── app.py             ← 本地开发启动
├── vercel.json        ← Vercel 配置
├── requirements.txt   ← Python 依赖
└── .gitignore
```

## 部署步骤

### 1. 本地 Git 初始化

```bash
cd /Users/chao/WorkBuddy/2026-06-26-12-17-40
git init
git add .
git commit -m "init: 三圈交集职业探索工具"
```

### 2. 推送到 GitHub

在 GitHub 创建新仓库（例如 `find-passion-tool`），然后：

```bash
git remote add origin https://github.com/你的用户名/find-passion-tool.git
git branch -M main
git push -u origin main
```

### 3. 导入 Vercel

1. 打开 [vercel.com](https://vercel.com)，用 GitHub 登录
2. 点击 **Add New → Project**
3. 选择刚推送的 `find-passion-tool` 仓库
4. 框架选择 **Other**
5. 构建配置保持默认（会自动识别 `vercel.json`）
6. 点击 **Deploy**

✅ 此时你的工具已经可以通过 Vercel 分配的 `xxx.vercel.app` 域名访问了。

### 4. 配置数据库（重要）

Vercel 的 Serverless 环境**不支持 SQLite**（数据会丢失），所以需要换成 PostgreSQL。

**推荐：Neon（免费，无需信用卡）**

1. 打开 [neon.tech](https://neon.tech) → GitHub 注册
2. 创建项目 → 复制 `DATABASE_URL` 连接串（类似 `postgres://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb`）
3. 回到 Vercel 项目 → **Settings → Environment Variables**
4. 添加变量名 `DATABASE_URL`，值粘贴 Neon 的连接串
5. 重新部署（Deploy 页面 → Redeploy）

> **本地开发**不需要配数据库，自动使用 SQLite 存储在 `data/results.db`

### 5. 绑定自定义域名

1. Vercel 项目 → **Settings → Domains**
2. 输入 `xxx.teacher-huanlin.com`（替换 xxx 为你想用的子域名）
3. 按照 Vercel 提示，去阿里云 DNS 管理添加 CNAME 记录

**阿里云 DNS 配置：**
- 记录类型：`CNAME`
- 主机记录：`xxx`（你的子域名前缀）
- 记录值：`cname.vercel-dns.com`
- TTL：默认

配置好等几分钟 DNS 生效，就可以通过 `https://xxx.teacher-huanlin.com` 访问了。

### 6. 验证功能

1. 打开 `https://xxx.teacher-huanlin.com`（或你的 Vercel 域名）
2. 完成探索流程 → 在结果页点击 **🔗 保存并分享**
3. 确认能生成并复制分享链接
4. 用分享链接打开，验证数据加载正常

## 如何查看所有保存的数据？

如果你想看所有用户保存的结果，可以在 `api/index.py` 底部添加一个管理路由：

```python
@app.route('/admin')
def admin():
    is_pg = bool(DATABASE_URL)
    rows = []
    if is_pg:
        conn, _ = get_db()
        cur = conn.cursor()
        cur.execute('SELECT id, created_at, views FROM results ORDER BY created_at DESC')
        for r in cur.fetchall():
            rows.append(dict(r))
        cur.close()
        conn.close()
    else:
        conn, _ = get_db()
        cur = conn.execute('SELECT id, created_at, views FROM results ORDER BY created_at DESC')
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

    links = ''.join(
        f'<tr><td><a href="/r/{r["id"]}">{r["id"]}</a></td>'
        f'<td>{r["created_at"]}</td><td>{r["views"]}</td></tr>'
        for r in rows
    )
    return f'<table border="1" cellpadding="8">{links}</table>'
```

然后访问 `https://xxx.teacher-huanlin.com/admin` 即可。

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动（自动使用 SQLite）
python app.py

# 访问 http://localhost:8080
```
