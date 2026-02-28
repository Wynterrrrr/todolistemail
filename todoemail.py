import smtplib
import time
import os
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import requests
from urllib.parse import urlparse, unquote

MONITORED_FILES = [
    {
        "name": "Personal To-Do.md",
        "web_url": "https://github.com/Wynterrrrr/ObsdianDrive/blob/main/Todo/Personal%20To-Do.md",
        "api_url": "https://api.github.com/repos/Wynterrrrr/ObsdianDrive/contents/Todo/Personal%20To-Do.md",
    },
    {
        "name": "Temp.md",
        "web_url": "https://github.com/Wynterrrrr/ObsdianDrive/blob/main/Todo/Temp.md",
        "api_url": "https://api.github.com/repos/Wynterrrrr/ObsdianDrive/contents/Todo/Temp.md",
    }
]



def parse_github_web_url(url):
    # 解析格式: https://github.com/{owner}/{repo}/blob/{branch}/{path}
    p = urlparse(url)
    parts = p.path.strip("/").split("/")
    if len(parts) < 5 or parts[2] != "blob":
        return None
    owner = parts[0]
    repo = parts[1]
    branch = parts[3]
    path = "/".join(parts[4:])
    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "path": unquote(path)
    }
EMAIL_FROM = "1784151291@qq.com"
# 支持从环境变量读取敏感配置，避免将密码硬编码到仓库中
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "fdtbxvedkjwrfagf")
EMAIL_TO = "wenzhonghua163@163.com"
# SMTP 服务器可通过环境变量覆盖，否则根据发件人域名自动推断
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
if not SMTP_SERVER:
    domain = EMAIL_FROM.split("@")[-1].lower()
    if domain == "qq.com":
        SMTP_SERVER = "smtp.qq.com"
    elif domain == "163.com":
        SMTP_SERVER = "smtp.163.com"
    else:
        SMTP_SERVER = f"smtp.{domain}"
CHECK_INTERVAL = 6
STATE_FILE = "check_state.json"


def get_file_info(api_url, web_url):
    # 先尝试使用 GitHub API 获取文件元数据（包括 base64 编码的 content）
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return {
            "sha": data.get("sha"),
            "content": data.get("content"),
            "download_url": data.get("download_url"),
            "is_raw": False
        }
    except requests.exceptions.HTTPError as e:
        status = None
        try:
            status = e.response.status_code
        except Exception:
            pass
        if status == 404:
            parsed = parse_github_web_url(web_url)
            if not parsed:
                raise
            raw_url = f"https://raw.githubusercontent.com/{parsed['owner']}/{parsed['repo']}/{parsed['branch']}/{parsed['path']}"
            r2 = requests.get(raw_url)
            if r2.status_code == 200:
                return {
                    "sha": None,
                    "content": r2.text,
                    "download_url": raw_url,
                    "is_raw": True
                }
        raise


def get_raw_content(content, is_raw=False):
    if is_raw:
        return content or ""
    import base64
    if not content:
        return ""
    return base64.b64decode(content).decode("utf-8")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_email(subject, content):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    
    html_content = f"""
    <html>
    <body>
        <h2>GitHub文件更新提醒</h2>
        <p><strong>文件:</strong> Personal To-Do.md</p>
        <p><strong>更新时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <hr>
        <pre style="background-color:#f5f5f5;padding:10px;border-radius:5px;white-space:pre-wrap;word-wrap:break-word;">{content}</pre>
    </body>
    </html>
    """
    msg.attach(MIMEText(content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    except smtplib.SMTPAuthenticationError as e:
        # 更友好的认证错误提示，常见于使用了错误的密码/未开启 SMTP/使用了非授权密码
        print("邮件发送失败：SMTP 认证失败。请检查发件人邮箱、SMTP 服务器及密码/授权码是否正确。")
        print("如果是 QQ 邮箱，请使用邮箱设置中的 SMTP/授权码（不是登录密码）；确保已启用 SMTP 服务。")
        raise


def main():
    print(f"[{datetime.now()}] 检查GitHub文件更新...")
    
    state = load_state()
    
    try:
        updated_any = False
        for f in MONITORED_FILES:
            file_info = get_file_info(f["api_url"], f["web_url"])
            current_sha = file_info.get("sha")
            state_key = f.get("name")
            if state.get(state_key) != current_sha:
                print(f"检测到文件更新：{state_key}")
                content = get_raw_content(file_info.get("content"), file_info.get("is_raw", False))
                subject = f"GitHub文件更新提醒 - {state_key}"
                send_email(subject, content)
                state[state_key] = current_sha
                state["checked_at"] = datetime.now().isoformat()
                save_state(state)
                print("邮件已发送！")
                updated_any = True
            else:
                print(f"文件无更新：{state_key}")
                state["checked_at"] = datetime.now().isoformat()
                save_state(state)

        if not updated_any:
            print("所有文件无更新")

    except requests.exceptions.HTTPError as e:
        status = None
        try:
            status = e.response.status_code
        except Exception:
            pass
        if status == 404:
            print("检查失败: 404 未找到。请检查仓库名/路径/分支是否正确，或文件是否存在。")
        else:
            print(f"检查失败: {e}")
    except Exception as e:
        print(f"检查失败: {e}")


if __name__ == "__main__":
    main()
