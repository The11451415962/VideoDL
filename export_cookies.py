#!/usr/bin/env python3
"""从 Chrome 加密数据库解密 cookies 并导出为 Netscape cookies.txt 格式。"""
import os, shutil, sqlite3, ctypes, ctypes.wintypes, sys

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

def decrypt(enc: bytes) -> str:
    if not enc:
        return ""
    # Chrome 新版前 3 字节是 "v10"/"v11" 前缀，后面才是 DPAPI 加密数据
    if enc[:3] in (b"v10", b"v11"):
        enc = enc[3:]
    blob_in = DATA_BLOB(len(enc), ctypes.cast(enc, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        return ""
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8", errors="replace")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)

def main():
    src = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Network\Cookies")
    if not os.path.exists(src):
        src = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Cookies")
    if not os.path.exists(src):
        print("找不到 Chrome cookies 数据库"); sys.exit(1)

    # 复制一份避免被 Chrome 锁住
    dst = os.path.join(os.environ.get("TEMP", "/tmp"), "chrome_cookies_copy.db")
    shutil.copy2(src, dst)

    conn = sqlite3.connect(dst)
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT host_key, path, is_secure, expires_utc, name, encrypted_value "
        "FROM cookies ORDER BY host_key"
    ).fetchall()
    conn.close()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    count = 0
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for host, path, secure, expires, name, enc in rows:
            val = decrypt(enc)
            if not val:
                continue
            domain = host if host.startswith(".") else "." + host
            flag = "TRUE" if host.startswith(".") else "FALSE"
            sec = "TRUE" if secure else "FALSE"
            exp = str(int(expires)) if expires else "0"
            f.write(f"{domain}\t{flag}\t{sec}\t{exp}\t{name}\t{val}\n")
            count += 1
    print(f"导出 {count} 条 cookies 到 {out}")

if __name__ == "__main__":
    main()
