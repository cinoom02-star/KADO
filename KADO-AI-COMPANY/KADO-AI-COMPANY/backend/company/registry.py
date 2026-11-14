"""Role definitions, not 35 permanently loaded models or fabricated conversations."""
from __future__ import annotations

_DEPARTMENTS = {
    "engineering": ("cto", "CTO Agent", [
        ("senior_fullstack", "Senior Full-Stack Developer"),
        ("backend_architect", "Backend Architect"),
        ("frontend_engineer", "Frontend/UI Engineer"),
        ("mobile_developer", "Mobile Developer"),
        ("database_engineer", "Database Engineer"),
        ("devops_engineer", "DevOps Engineer"),
        ("security_engineer", "Cybersecurity Engineer"),
        ("qa_engineer", "QA Automation Engineer"),
    ]),
    "media": ("cmo", "CMO Agent", [
        ("instagram_specialist", "Instagram Specialist"),
        ("tiktok_specialist", "TikTok Specialist"),
        ("youtube_specialist", "YouTube Specialist"),
        ("facebook_specialist", "Facebook Specialist"),
        ("social_strategist", "Social Media Strategist"),
        ("video_producer", "Video Production Specialist"),
        ("graphic_designer", "Graphic Design Specialist"),
        ("community_manager", "Community Management Specialist"),
    ]),
    "research": ("crco", "Chief Research & Creative Officer", [
        ("deep_researcher", "Deep Research Agent"),
        ("market_intelligence", "Market Intelligence Agent"),
        ("business_ideator", "Business Idea Generator"),
        ("screenwriter", "Screenwriter & Storytelling Agent"),
        ("production_planner", "Film & Series Production Planner"),
        ("product_innovator", "Product Innovation Agent"),
        ("trend_analyst", "Marketing Psychology & Trend Analyst"),
    ]),
    "operations": ("coo", "COO Agent", [
        ("quality_auditor", "Quality Auditor"),
        ("financial_analyst", "Financial Analysis Agent"),
        ("project_manager", "Project Management Agent"),
        ("ecommerce_operator", "E-Commerce Operations Agent"),
        ("customer_support", "Customer Support Agent"),
        ("compliance_agent", "Compliance & Risk Agent"),
        ("workflow_automator", "Workflow Automation Agent"),
    ]),
}

AGENTS: list[dict] = [{
    "id": "kado", "name": "KADO", "role": "CEO — mevcut KADO", "department": "executive",
    "manager_id": None, "tools": ["task_dispatch", "task_status"],
    "model_provider": "external_kado", "integration_required": True,
    "capability_status": "adapter_ready_local_connection_unverified",
}]
for department, (manager_id, manager_name, specialists) in _DEPARTMENTS.items():
    AGENTS.append({"id": manager_id, "name": manager_name, "role": "manager",
                   "department": department, "manager_id": "kado",
                   "tools": ["task_dispatch", "task_status"], "model_provider": "unconfigured",
                   "capability_status": "role_defined"})
    for agent_id, name in specialists:
        permitted = ["llm_generate"]
        if agent_id == "senior_fullstack":
            permitted += ["workspace_inventory", "write_report"]
        if agent_id == "qa_engineer":
            permitted += ["verify_report"]
        if agent_id == "quality_auditor":
            permitted += ["audit_report"]
        AGENTS.append({"id": agent_id, "name": name, "role": "specialist", "department": department,
                       "manager_id": manager_id, "tools": permitted,
                       "model_provider": "unconfigured", "capability_status": "role_defined"})

AGENT_BY_ID = {agent["id"]: agent for agent in AGENTS}

TOOL_CATALOG = [
    {"name": "workspace_inventory", "description": "İzinli klasörde gerçek dosya envanteri ve SHA-256", "status": "available"},
    {"name": "write_report", "description": "Göreve ait JSON kanıt dosyası oluşturma", "status": "available"},
    {"name": "verify_report", "description": "Raporu dosyalardan tekrar hesaplayarak test etme", "status": "available"},
    {"name": "audit_report", "description": "Bağımsız dosya, özet ve kapsam doğrulaması", "status": "available"},
    {"name": "llm_generate", "description": "Yapılandırılmış Ollama/Gemini üzerinden gerçek üretim", "status": "requires_provider"},
    {"name": "shell_execute", "description": "İzolasyonlu komut işçisi henüz uygulanmadı", "status": "unsupported"},
    {"name": "social_publish", "description": "Resmî OAuth ve platform connector'ı gerekir", "status": "unsupported"},
]


def require_permission(agent_id: str, tool: str) -> None:
    if agent_id not in AGENT_BY_ID or tool not in AGENT_BY_ID[agent_id]["tools"]:
        raise PermissionError(f"{agent_id!r} ajanının {tool!r} aracı için yetkisi yok")
