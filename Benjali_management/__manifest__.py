{
    "name": "Business Project Management",
    "version": "1.0",
    "category": "Project",
    "summary": "Business project workflow management",
    "depends": [
        "base",
        "mail",
        "hr",
        "crm",
        "sale_management",
        "account",
        "project",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/approval_sequence.xml",
        "data/sequence_data.xml",
        "data/stage_data.xml",
        "views/crm_lead_views.xml",
        "views/business_project_approval_views.xml",
        "views/business_project_views.xml",
        "views/project_stage_views.xml",
        "views/menu.xml"
    ],
    "installable": True,
    "application": True,
}