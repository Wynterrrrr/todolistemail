"""
监控 GitHub 文件夹新增文件，发送邮件通知
功能：检测 https://github.com/Wynterrrrr/ObsdianDrive/tree/main/hotnews 文件夹是否有新增文件
"""

import smtplib
import os
import json
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import requests

# ==================== 配置区域 ====================
REPO_OWNER = "Wynterrrrr"
REPO_NAME = "ObsdianDrive"
FOLDER_PATH = "hotnews"
BRANCH = "main"

# 文件夹 API URL
FOLDER_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FOLDER_PATH}?ref={BRANCH}"

# 邮件配置（复用现有配置）
EMAIL_FROM = "1784151291@qq.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "fdtbxvedkjwrfagf")
EMAIL_TO = "wenzhonghua163@163.com"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

# 状态文件
STATE_FILE = "hotnews_state.json"


# ==================== GitHub API 相关 ====================


def get_github_headers():
    """构建 GitHub API 请求头"""
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def get_folder_contents():
    """
    获取文件夹内容列表
    返回：文件信息列表 [{name, sha, download_url, ...}, ...]
    """
    headers = get_github_headers()
    try:
        response = requests.get(FOLDER_API_URL, headers=headers)
        response.raise_for_status()
        contents = response.json()

        # 只返回文件（排除子文件夹）
        files = [item for item in contents if item.get("type") == "file"]
        return files
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"文件夹不存在或为空: {FOLDER_PATH}")
            return []
        raise


def get_file_content(download_url, max_retries=3):
    """通过 download_url 获取文件原始内容（带重试）"""
    for attempt in range(max_retries):
        try:
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"获取文件内容失败（第{attempt + 1}次），重试中...")
                import time

                time.sleep(2)
            else:
                print(f"获取文件内容失败: {e}")
                return None


# ==================== 状态管理 ====================


def load_state():
    """加载已知文件状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"known_files": {}, "checked_at": None}


def save_state(state):
    """保存状态"""
    state["checked_at"] = datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ==================== 邮件发送 ====================


def send_email(file_name, file_content, file_url):
    """发送邮件通知"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[HotNews] 新文件通知 - {file_name}"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    # 构建纯文本内容
    text_content = f"""
HotNews 文件夹新增文件通知

文件名: {file_name}
时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
链接: {file_url}

{"=" * 50}
文件内容:
{"=" * 50}

{file_content}
"""

    # 构建 HTML 内容
    html_content = f"""
    <html>
    <body>
        <h2>HotNews 文件夹新增文件通知</h2>
        <p><strong>文件名:</strong> {file_name}</p>
        <p><strong>时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p><strong>链接:</strong> <a href="{file_url}">{file_url}</a></p>
        <hr>
        <h3>文件内容:</h3>
        <pre style="background-color:#f5f5f5;padding:15px;border-radius:5px;white-space:pre-wrap;word-wrap:break-word;">{file_content}</pre>
    </body>
    </html>
    """

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"邮件已发送: {file_name}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print("邮件发送失败：SMTP 认证失败。请检查邮箱配置。")
        raise


# ==================== 主逻辑 ====================


def main():
    print(f"[{datetime.now()}] 检查 HotNews 文件夹更新...")

    # 加载已知文件状态
    state = load_state()
    known_files = state.get("known_files", {})

    # 获取当前文件夹内容
    current_files = get_folder_contents()

    if not current_files:
        print("文件夹为空或无法访问")
        return

    # 检测新增文件
    new_files_found = []
    for file_info in current_files:
        file_name = file_info.get("name")
        file_sha = file_info.get("sha")

        if file_name not in known_files:
            # 发现新文件
            new_files_found.append(file_info)

    # 处理新增文件
    if new_files_found:
        print(f"发现 {len(new_files_found)} 个新文件:")

        for file_info in new_files_found:
            file_name = file_info.get("name")
            file_sha = file_info.get("sha")
            download_url = file_info.get("download_url")

            # 构建网页链接
            file_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/blob/{BRANCH}/{FOLDER_PATH}/{file_name}"

            print(f"  - {file_name}")

            # 获取文件内容
            content = get_file_content(download_url)
            if content:
                # 发送邮件
                try:
                    send_email(file_name, content, file_url)
                except Exception as e:
                    print(f"发送邮件失败: {e}")
                    continue

            # 更新已知文件列表
            known_files[file_name] = {
                "sha": file_sha,
                "first_seen": datetime.now().isoformat(),
            }

        # 保存更新后的状态
        state["known_files"] = known_files
        save_state(state)
        print("状态已更新")
    else:
        print("无新增文件")
        # 更新检查时间
        save_state(state)


if __name__ == "__main__":
    main()
