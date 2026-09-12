"""Steam authentication bridge. Secrets only enter keyring or private child pipes."""
from __future__ import annotations

import base64
import ctypes
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import urllib.request

from steam_sources import AccountMismatchError

SERVICE = "steam-library-toolkit"
STAGES = {
    "starting": "正在启动客户端采集进程",
    "qr_login": "正在连接 Steam 扫码认证服务",
    "connecting_cm": "正在连接 Steam 客户端服务器（CM）",
    "authenticated": "已认证，正在读取许可与游玩记录",
    "reading_licenses": "正在读取许可与应用信息",
    "web_session_ready": "网页授权已就绪，等待其他来源",
    "reading_web_sources": "正在核验在线客户端与 Web API",
}
HELPER_ERRORS = {
    "CM_CONNECT_TIMEOUT": "连接 Steam 客户端服务器超过 60 秒；请检查当前终端的网络或代理",
    "WEB_SESSION_TIMEOUT": "客户端已认证，但未能取得网页授权；请检查 Steam 网络连接",
}


class AuthError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"{code}：{message}")


def token_claims(token):
    try:
        part = token.split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, IndexError, AttributeError):
        raise ValueError("Steam 凭据格式无效，请重新 --login") from None


def validate_token(token, account=None):
    data = token_claims(token)
    identity = data.get("sub")
    if not isinstance(identity, str) or not identity.isdigit() or len(identity) != 17:
        raise ValueError("Steam 凭据账号无效")
    if account and identity != account:
        raise AccountMismatchError("认证账号与指定 Steam ID 不一致")
    if type(data.get("exp")) not in (int, float) or data["exp"] <= time.time():
        raise ValueError("Steam 凭据已过期，请重新 --login")
    return identity


def secret_store():
    try:
        import keyring
        backend = keyring.get_keyring()
        secure_modules = {"keyring.backends.Windows", "keyring.backends.macOS",
                          "keyring.backends.SecretService", "keyring.backends.kwallet",
                          "keyring.backends.libsecret"}
        if type(backend).__module__ == "keyring.backends.chainer":
            backend = next((b for b in backend.backends if type(b).__module__ in secure_modules), None)
            if backend is not None:
                keyring.set_keyring(backend)
        if backend is None or type(backend).__module__ not in secure_modules or backend.priority <= 0:
            raise RuntimeError()
        return keyring
    except Exception:
        raise AuthError("KEYRING_UNAVAILABLE", "操作系统凭据存储不可用；请安装 keyring 并配置系统密钥环") from None


def saved_credentials(account=None):
    try:
        store = secret_store()
        account = account or store.get_password(SERVICE, "default_account")
        token = store.get_password(SERVICE, account) if account else None
    except Exception:
        return None
    if not token:
        return None
    return validate_token(token, account), token


def save_credentials(account, token):
    validate_token(token, account)
    store = secret_store()
    try:
        store.set_password(SERVICE, account, token)
        if store.get_password(SERVICE, account) != token:
            raise RuntimeError()
        store.set_password(SERVICE, "default_account", account)
    except Exception:
        raise AuthError("KEYRING_SAVE_FAILED", "Steam 授权成功，但凭据保存失败，请检查系统密钥环") from None


def local_credentials(steam_path=None, account=None):
    """Opt-in Windows DPAPI path. Never inspect process memory or browser cookies."""
    if os.name != "nt":
        raise AuthError("LOCAL_SESSION_UNSUPPORTED", "--local-session 目前仅支持 Windows；其他系统请使用 --login")
    import winreg
    try:
        import vdf
    except ImportError:
        raise AuthError("PYTHON_DEPENDENCY_MISSING", "本地会话缺少 vdf，请使用项目 .venv 的 Python 或执行 python -m pip install -r requirements.txt") from None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess") as key:
            active = winreg.QueryValueEx(key, "ActiveUser")[0]
        if not active:
            raise OSError()
        if not steam_path:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
        identity = str(76561197960265728 + active)
        if account and identity != account:
            raise AccountMismatchError("Steam 当前登录账号与指定账号不一致")
        users = vdf.loads((Path(steam_path) / "config/loginusers.vdf").read_text(encoding="utf-8"))["users"]
        name = users[identity]["AccountName"]
        data = vdf.loads((Path(os.environ["LOCALAPPDATA"]) / "Steam/local.vdf").read_text(encoding="utf-8"))
    except AccountMismatchError:
        raise
    except (OSError, KeyError, ValueError):
        raise AuthError("LOCAL_SESSION_UNAVAILABLE", "无法读取当前用户的 Steam 登录状态；请在登录 Steam 的 Windows 用户下运行，或使用 --login") from None

    def find_cache(node):
        for key, value in node.items():
            if key.lower() == "connectcache" and isinstance(value, dict):
                return value
            if isinstance(value, dict):
                found = find_cache(value)
                if found is not None:
                    return found
        return None

    class Blob(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("data", ctypes.c_void_p)]
    crypt = ctypes.WinDLL("crypt32").CryptUnprotectData
    crypt.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    crypt.restype = ctypes.c_int
    free = ctypes.WinDLL("kernel32").LocalFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_void_p
    entropy = ctypes.create_string_buffer(name.encode("utf-8"))
    extra = Blob(len(name.encode("utf-8")), ctypes.cast(entropy, ctypes.c_void_p))
    for value in (find_cache(data) or {}).values():
        try:
            encrypted = bytes.fromhex(value)
        except (TypeError, ValueError):
            continue
        buffer = ctypes.create_string_buffer(encrypted)
        incoming = Blob(len(encrypted), ctypes.cast(buffer, ctypes.c_void_p))
        outgoing = Blob()
        if not crypt(ctypes.byref(incoming), None, ctypes.byref(extra), None, None, 1, ctypes.byref(outgoing)):
            continue
        try:
            token = ctypes.string_at(outgoing.data, outgoing.length).decode("utf-8", errors="replace").rstrip("\x00")
        finally:
            ctypes.memset(outgoing.data, 0, outgoing.length)
            free(outgoing.data)
        try:
            validate_token(token, identity)
            audience = token_claims(token).get("aud", [])
            if "derive" in audience and "client" in audience:
                return identity, token
        except ValueError:
            continue
    raise AuthError("LOCAL_CREDENTIAL_UNAVAILABLE", "Steam 本地缓存没有可用凭据，请重新登录 Steam 或运行 --login")


def collect_client(account=None, *, login=False, local_session=False, steam_path=None,
                   machine=None, timeout=300, on_progress=print, use_api=True, expanded=True):
    credentials = local_credentials(steam_path, account) if local_session else (None if login else saved_credentials(account))
    if login:
        secret_store()  # Fail before asking the user to scan if secure persistence is unavailable.
    if not login and not credentials:
        raise AuthError("AUTH_REQUIRED", "未配置客户端授权；首次运行 --login，或在 Windows 使用 --local-session")
    if credentials:
        account, token = credentials
    else:
        token = None
    node = shutil.which("node")
    if not node:
        raise AuthError("NODE_NOT_FOUND", "客户端采集需要 Node.js 和 npm ci")
    helper = Path(__file__).parent / "tools/steam_client_collect.cjs"
    on_progress("Steam 客户端：本地凭据已读取，准备连接（尚未完成服务器认证）" if local_session
                else "Steam 客户端：准备启动认证与采集")
    events = queue.Queue()
    process = subprocess.Popen(
        [node, str(helper)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", env={**os.environ, "DEBUG": "", "NODE_DEBUG": ""},
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    def read_events():
        try:
            for line in process.stdout:
                events.put(line)
        finally:
            events.put(None)
    reader = threading.Thread(target=read_events, daemon=True)
    reader.start()
    try:
        proxy = None if urllib.request.proxy_bypass("api.steampowered.com") else urllib.request.getproxies().get("https")
        on_progress("Steam 网络：使用已配置的 HTTP(S) 代理" if proxy else "Steam 网络：直连（未检测到适用的 HTTP(S) 代理）")
        process.stdin.write(json.dumps({"refresh_token": token, "steam_id": account, "login": login,
                                       "use_api": use_api, "expanded": expanded,
                                       "https_proxy": proxy,
                                       "machine": machine or os.environ.get("COMPUTERNAME") or __import__("socket").gethostname()}))
        process.stdin.close()
        started = time.monotonic()
        deadline = started + timeout + (120 if login else 0)
        next_notice = started + 10
        stage = "starting"
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_notice:
                on_progress(f"Steam 客户端：{STAGES[stage]}；已等待 {int(now - started)} 秒")
                next_notice = now + 10
            try:
                line = events.get(timeout=min(1, max(.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                event = json.loads(line)
            except ValueError:
                raise AuthError("HELPER_PROTOCOL_INVALID", "客户端 helper 返回无效数据") from None
            kind = event.get("event")
            if kind == "qr":
                on_progress("请用 Steam 手机 App 扫码并确认：\n" + event["qr"])
            elif kind == "credentials":
                identity = validate_token(event["refresh_token"], account)
                if not login:
                    raise RuntimeError("非登录操作不能更新持久凭据")
                save_credentials(identity, event["refresh_token"])
                account = identity
                on_progress("Steam 授权已保存至系统凭据存储")
            elif kind == "progress":
                if event.get("stage") in STAGES:
                    stage = event["stage"]
                    on_progress("Steam 客户端：" + STAGES[stage])
            elif kind == "error":
                if event.get("code") == "ACCOUNT_MISMATCH":
                    raise AccountMismatchError("ACCOUNT_MISMATCH：客户端认证账号不一致")
                if event.get("code") in HELPER_ERRORS:
                    code = event["code"]
                    raise AuthError(code, HELPER_ERRORS[code])
                eresult = event.get("eresult")
                detail = f"（Steam EResult={eresult}）" if type(eresult) is int else ""
                raise AuthError("CM_UNAVAILABLE", "Steam 客户端采集失败" + detail)
            elif kind == "result":
                if account and event.get("steam_id") != account:
                    raise AccountMismatchError("客户端返回账号不一致")
                if not account or event.get("steam_id") != account:
                    raise AccountMismatchError("ACCOUNT_MISMATCH：缺少已验证账号")
                if "access_token" in event:
                    raise AuthError("HELPER_PROTOCOL_INVALID", "helper 不应返回访问令牌")
                process.wait(timeout=5)
                if process.returncode:
                    raise AuthError("HELPER_EXIT_FAILED", "客户端 helper 未正常退出")
                return event
        if process.poll() is not None:
            raise AuthError("HELPER_START_FAILED", "客户端 helper 提前退出；请确认 Node.js 18+ 并运行 npm ci")
        raise AuthError("CLIENT_TIMEOUT", f"客户端采集超时；最后阶段：{STAGES[stage]}。请检查 Steam 网络连接")
    finally:
        if not process.stdin.closed:
            process.stdin.close()
        if process.poll() is None:
            process.kill()
        process.wait()
        reader.join(timeout=2)
        process.stdout.close()
