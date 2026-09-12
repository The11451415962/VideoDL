#!/usr/bin/env python3
"""从 Chrome 加密数据库解密 cookies 并导出为 Netscape cookies.txt 格式。

用法::

    python export_cookies.py douyin     # 只导出域名含 douyin 的（推荐）
    python export_cookies.py            # 导出全部（会把整个浏览器的 cookie 写进一个文件，慎用）

导出的文件可直接给 yt-dlp 用（`--yt-dlp --cookies cookies.txt`），
也可以拷到手机上在 VideoDL 安卓版的「设置 → Cookie 模式 → cookies.txt 文件」里选中。

**为什么必须带 path 字段**：Netscape 格式是 7 个 tab 分隔字段::

    domain  includeSubdomains  path  secure  expiry  name  value

早先这里写成了 6 个字段（漏了 path），yt-dlp 载入时直接报
`invalid length 6` 并把**每一条都跳过** —— 导出的文件等于空的，
表现就是"明明给了 cookie，还是说需要 cookie"。所以下面把格式化的部分单独抽成
函数，方便随时验证。
"""
import ctypes
import ctypes.wintypes
import os
import shutil
import sqlite3
import sys

# Chrome 的 expires_utc 是"1601-01-01 起的微秒数"，Netscape 要的是 Unix 秒
_CHROME_EPOCH_OFFSET_SEC = 11644473600


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def decrypt(enc: bytes) -> str:
    if not enc:
        return ""
    # Chrome 新版前 3 字节是 "v10"/"v11" 前缀，后面才是 DPAPI 加密数据
    if enc[:3] in (b"v10", b"v11"):
        enc = enc[3:]
    blob_in = DATA_BLOB(len(enc), ctypes.cast(enc, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0,
        ctypes.byref(blob_out),
    ):
        return ""
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8", errors="replace")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def netscape_line(host: str, path: str, secure, expires_utc, name: str, value: str) -> str:
    """把 Chrome cookies 表的一行转成 Netscape 格式的一行。

    7 个字段，顺序不能少也不能错 —— 少了 path，yt-dlp 会把整行当非法行丢掉。
    """
    domain = host if host.startswith(".") else "." + host
    include_sub = "TRUE" if host.startswith(".") else "FALSE"
    sec = "TRUE" if secure else "FALSE"
    # expires_utc == 0 表示会话 cookie，Netscape 里写 0
    exp = str(int(expires_utc) // 1_000_000 - _CHROME_EPOCH_OFFSET_SEC) if expires_utc else "0"
    # 值里理论上不会出现 tab/换行；保险起见换掉，否则会写坏整行
    safe_value = value.replace("\t", " ").replace("\r", "").replace("\n", "")
    return f"{domain}\t{include_sub}\t{path or '/'}\t{sec}\t{exp}\t{name}\t{safe_value}"


def chrome_cookie_db() -> str | None:
    for rel in (r"Google\Chrome\User Data\Default\Network\Cookies",
                r"Google\Chrome\User Data\Default\Cookies"):
        p = os.path.expanduser("~\\AppData\\Local\\" + rel)
        if os.path.exists(p):
            return p
    return None


def main() -> None:
    src = chrome_cookie_db()
    if not src:
        print("找不到 Chrome cookies 数据库")
        sys.exit(1)

    # 只导出指定域名（子串匹配）—— 不传就全导
    needle = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""

    # 复制一份避免被 Chrome 锁住
    dst = os.path.join(os.environ.get("TEMP", "/tmp"), "chrome_cookies_copy.db")
    shutil.copy2(src, dst)

    conn = sqlite3.connect(dst)
    try:
        rows = conn.execute(
            "SELECT host_key, path, is_secure, expires_utc, name, encrypted_value "
            "FROM cookies ORDER BY host_key"
        ).fetchall()
    finally:
        conn.close()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    count = 0
    skipped = 0
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for host, path, secure, expires, name, enc in rows:
            if needle and needle not in host.lower():
                continue
            val = decrypt(enc)
            if not val:
                skipped += 1
                continue
            f.write(netscape_line(host, path, secure, expires, name, val) + "\n")
            count += 1

    scope = f"域名含 {needle!r} 的" if needle else "全部"
    print(f"导出 {count} 条 cookies（{scope}）到 {out}")
    if skipped:
        print(f"（有 {skipped} 条解密失败已跳过 —— Chrome 新版有时需要先关掉浏览器）")


if __name__ == "__main__":
    main()
