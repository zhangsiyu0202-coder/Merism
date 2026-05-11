"""
Built-in IM recruitment message templates.

These are defined as code constants rather than seeded DB rows because
MessageTemplate is team-scoped (requires a team FK) and there is no
global/system team to attach them to.

Usage: present these to users as starting-point templates when they create
a new MessageTemplate for their team. The API layer can merge these into
the template list response with a synthetic `is_builtin=True` flag.
"""

from __future__ import annotations

from typing import Any

BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "简洁邀请",
        "content": (
            "您好！我们正在进行《{{study_name}}》研究，诚邀您参与。\n\n"
            "参与链接：{{study_link}}\n\n"
            "感谢您的支持！\n\n"
            "— {{researcher_name}}"
        ),
        "msg_format": "markdown",
    },
    {
        "name": "详细说明",
        "content": (
            "您好！\n\n"
            "我们正在开展《{{study_name}}》用户研究，希望了解您的真实使用体验。\n\n"
            "**研究内容：** 约15-20分钟的在线访谈\n"
            "**参与奖励：** {{reward}}\n"
            "**截止日期：** {{deadline}}\n\n"
            "参与链接：{{study_link}}\n\n"
            "如有疑问，欢迎联系 {{researcher_name}}。感谢您的参与！"
        ),
        "msg_format": "markdown",
    },
    {
        "name": "紧急招募",
        "content": (
            "⚡ 紧急招募！\n\n"
            "《{{study_name}}》研究名额即将截止（{{deadline}}），诚邀您参与！\n\n"
            "参与奖励：{{reward}}\n"
            "立即参与：{{study_link}}\n\n"
            "— {{researcher_name}}"
        ),
        "msg_format": "markdown",
    },
    {
        "name": "Email · Research invitation",
        "channel_type": "email",
        "content": (
            "<p>Hi{{ ' ' + name if name else '' }},</p>"
            "<p>We're running a short research study — "
            "<strong>{{study_name}}</strong> — and we think your perspective "
            "would be really valuable.</p>"
            "<ul>"
            "<li><strong>Format:</strong> 15–20 minute voice interview online</li>"
            "<li><strong>Reward:</strong> {{reward}}</li>"
            "<li><strong>Deadline:</strong> {{deadline}}</li>"
            "</ul>"
            "<p><a href=\"{{study_link}}\">Join the study →</a></p>"
            "<p>Questions? Reply to this email and {{researcher_name}} will "
            "get back to you.</p>"
            "<p>Thanks,<br/>The Merism research team</p>"
        ),
        "msg_format": "html",
        "subject": "You're invited: {{study_name}}",
    },
    {
        "name": "Email · Chinese short",
        "channel_type": "email",
        "content": (
            "<p>你好！</p>"
            "<p>我们正在进行《{{study_name}}》用户研究，"
            "想邀请你参与约 15–20 分钟的语音访谈。</p>"
            "<p><strong>参与奖励：</strong>{{reward}}<br/>"
            "<strong>截止日期：</strong>{{deadline}}</p>"
            "<p><a href=\"{{study_link}}\">点此参与研究 →</a></p>"
            "<p>感谢你！<br/>— {{researcher_name}}</p>"
        ),
        "msg_format": "html",
        "subject": "课题邀请：{{study_name}}",
    },
]
