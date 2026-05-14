"""Chinese verbose_name for all Merism models (Django Admin display)."""

MODEL_VERBOSE_NAMES: dict[str, tuple[str, str]] = {
    # (verbose_name, verbose_name_plural)
    "Organization": ("组织", "组织"),
    "OrganizationMembership": ("组织成员", "组织成员"),
    "Team": ("团队", "团队"),
    "Study": ("研究项目", "研究项目"),
    "StudyLink": ("研究链接", "研究链接"),
    "StudyTemplate": ("研究模板", "研究模板"),
    "StudyTrigger": ("研究触发器", "研究触发器"),
    "InterviewGuide": ("访谈大纲", "访谈大纲"),
    "InterviewSession": ("访谈会话", "访谈会话"),
    "InterviewRecording": ("访谈录音", "访谈录音"),
    "Participant": ("参与者", "参与者"),
    "Participation": ("参与记录", "参与记录"),
    "SessionEvent": ("会话事件", "会话事件"),
    "SessionInsight": ("会话洞察", "会话洞察"),
    "SessionQuote": ("会话引用", "会话引用"),
    "Screener": ("筛选问卷", "筛选问卷"),
    "Stimulus": ("刺激物", "刺激物"),
    "Concept": ("概念", "概念"),
    "ConceptBlock": ("概念组", "概念组"),
    "ChannelConfig": ("渠道配置", "渠道配置"),
    "ChannelTarget": ("渠道目标", "渠道目标"),
    "ChannelHealthCheck": ("渠道健康检查", "渠道健康检查"),
    "MessageTemplate": ("消息模板", "消息模板"),
    "RecruitmentBroadcast": ("招募广播", "招募广播"),
    "DeliveryRecord": ("投递记录", "投递记录"),
    "Invitation": ("邀请", "邀请"),
    "InboxItem": ("收件箱消息", "收件箱消息"),
    "KnowledgeDocument": ("知识文档", "知识文档"),
    "KnowledgeChunk": ("知识片段", "知识片段"),
    "StudyReport": ("研究报告", "研究报告"),
    "AggregateSynthesis": ("综合分析", "综合分析"),
    "CustomReportQuery": ("自定义报告查询", "自定义报告查询"),
    "StudyInsights": ("研究洞察", "研究洞察"),
    "InsightHighlight": ("洞察亮点", "洞察亮点"),
    "InsightFinding": ("洞察发现", "洞察发现"),
    "CustomReport": ("自定义报告", "自定义报告"),
    "ReportQuestion": ("报告问题", "报告问题"),
    "ReportSegment": ("报告段落", "报告段落"),
    "LinkClick": ("链接点击", "链接点击"),
    "LinkShareEvent": ("链接分享", "链接分享"),
    "StudyGoal": ("研究目标", "研究目标"),
    "Theme": ("主题", "主题"),
    "CoverageSnapshot": ("覆盖快照", "覆盖快照"),
    "CohortSegment": ("群组分段", "群组分段"),
    "Glossary": ("术语表", "术语表"),
    "ServiceSettings": ("服务配置", "服务配置"),
}


def apply_verbose_names() -> None:
    """Patch verbose_name on all registered models."""
    from django.apps import apps

    for model in apps.get_app_config("merism").get_models():
        name = model.__name__
        if name in MODEL_VERBOSE_NAMES:
            vn, vnp = MODEL_VERBOSE_NAMES[name]
            model._meta.verbose_name = vn
            model._meta.verbose_name_plural = vnp
