# -*- coding: utf-8 -*-
"""
yt-dlp 下载失败诊断模块

分析 yt-dlp 的输出行，匹配常见错误模式，返回用户友好的诊断报告。
"""

import re

# ============================================================
# 错误规则表
# 每条规则: (正则, 错误分类, 原因说明, 解决建议)
# 按优先级从上到下匹配，首个命中即返回。
# ============================================================
ERROR_RULES: list[tuple[str, str, str, str]] = [
    # ---- 网络 / DNS ----
    (
        r"getaddrinfo failed|Name or service not known|could not resolve|unable to resolve",
        "DNS 解析失败",
        "无法解析视频服务器域名，说明当前网络无法访问目标站点。",
        "检查网络连接是否正常；尝试更换 DNS（如 223.5.5.5 / 8.8.8.8）；确认代理是否正常运行。",
    ),
    (
        r"Connection refused",
        "连接被拒绝",
        "服务器主动拒绝了连接请求。",
        "视频可能已下架；若使用代理，检查代理服务是否正常运行。",
    ),
    (
        r"Connection timed out|timed out|TimeoutError",
        "连接超时",
        "连接服务器超时，网络太慢或服务器无响应。",
        "检查网络状况；尝试切换代理模式（自动 / 强制代理 / 强制直连）。",
    ),
    # ---- HTTP 状态码 ----
    (
        r"HTTP Error 403",
        "访问被拒绝 (403)",
        "服务器拒绝了访问请求，通常因为缺少登录凭证或被反爬。",
        "尝试在浏览器登录后，使用「浏览器 Cookie」模式；或更换代理地址。",
    ),
    (
        r"HTTP Error 404",
        "视频不存在 (404)",
        "服务器返回 404，找不到该视频资源。",
        "视频可能已被删除，或链接本身有误。请核对链接是否正确。",
    ),
    (
        r"HTTP Error 429",
        "请求过于频繁 (429)",
        "被服务器限流，短时间内请求过多。",
        "稍后再试；避免短时间内大量下载同一平台。",
    ),
    # ---- 视频状态 ----
    (
        r"Private video|private",
        "私人视频",
        "该视频为私有内容，需要登录原作者账号才能观看。",
        "无法直接下载他人私人视频。如为自己视频，请在浏览器登录后使用「浏览器 Cookie」模式。",
    ),
    (
        r"not available in your country|region|地理限制|restricted",
        "地区限制",
        "该视频在您所在地区不可用（地理封锁）。",
        "尝试使用代理，并切换代理地区后重试。",
    ),
    (
        r"removed by the uploader|video is unavailable|This video is not available|"
        r"Video unavailable|deleted",
        "视频已删除 / 不可用",
        "视频已被作者删除、下架或从未存在过。",
        "无法恢复，该视频已不存在。请确认链接是否正确。",
    ),
    (
        r"requires payment|premiere|membership|paid",
        "付费 / 会员视频",
        "该视频需要付费购买或开通会员才能观看。",
        "无法直接下载付费内容。请支持原作者。",
    ),
    # ---- 登录 / 验证 ----
    (
        r"Sign in to confirm|Sign in to verify|bot|captcha|CAPTCHA",
        "需要登录验证",
        "平台要求登录或人机验证才能访问该视频。",
        "在浏览器登录该平台后，使用「浏览器 Cookie」模式下载。",
    ),
    # ---- 提取 / 格式 ----
    (
        r"Unable to extract video data|extractor|ExtractorError",
        "无法提取视频数据",
        "yt-dlp 无法解析该页面，可能页面结构已变。",
        "尝试点击右上角「更新核心」按钮，将 yt-dlp 更新到最新版本。",
    ),
    (
        r"No video formats found|no formats|no format",
        "找不到视频格式",
        "没有可下载的视频流（可能因为画质/格式选择不匹配）。",
        "尝试切换「格式」或「画质」选项后重试；或更新 yt-dlp。",
    ),
    # ---- SSL / 证书 ----
    (
        r"SSL:|certificate|TLS|ssl",
        "SSL 证书错误",
        "HTTPS 证书验证失败，无法建立安全连接。",
        "检查系统时间是否正确；尝试更新 Python 或 yt-dlp 到最新版本。",
    ),
    # ---- 通用网页抓取 ----
    (
        r"Unable to download webpage",
        "无法下载网页",
        "抓取视频信息页面失败。",
        "检查网络 / 代理设置；可能需要启用 Cookie 才能访问。",
    ),
]


def diagnose(lines: list[str]) -> dict:
    """
    分析 yt-dlp 输出行，返回诊断报告字典。

    Args:
        lines: yt-dlp 的所有输出行（已 strip）。

    Returns:
        {
            "category": str,      # 错误分类（标题）
            "reason": str,        # 原因说明
            "solution": str,      # 解决建议
            "matched_line": str,  # 匹配到的原始行
            "all_lines": list,    # 全部输出行
        }
        未匹配任何规则时返回通用报告。
    """
    # 合并所有行用于匹配（优先匹配 ERROR / WARNING 行）
    error_lines = [l for l in lines if l.startswith("[错误]") or l.startswith("ERROR")]
    warning_lines = [l for l in lines if l.startswith("[警告]") or l.startswith("WARNING")]
    search_lines = error_lines + warning_lines + lines

    for line in search_lines:
        for pattern, category, reason, solution in ERROR_RULES:
            if re.search(pattern, line, re.IGNORECASE):
                return {
                    "category": category,
                    "reason": reason,
                    "solution": solution,
                    "matched_line": line,
                    "all_lines": list(lines),
                }

    # 兜底：未匹配任何规则
    return {
        "category": "未知错误",
        "reason": "yt-dlp 返回了非零退出码，但未能识别具体原因。",
        "solution": (
            "请查看下方「技术详情」中的原始日志；"
            "尝试更新 yt-dlp 核心（右上角「更新核心」按钮）；"
            "或检查网络 / 代理 / Cookie 设置后重试。"
        ),
        "matched_line": "",
        "all_lines": list(lines),
    }
