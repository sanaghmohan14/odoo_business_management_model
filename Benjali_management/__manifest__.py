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
        "security/user_groups.xml",
        "security/ir.model.access.csv",
        # "data/project_task_type_data.xml",
        "data/approval_sequence.xml",
        "data/sequence_data.xml",
        "data/stage_data.xml",
        "views/reporting.xml",
        "views/dashboard_views.xml",
        "views/hr_department_views.xml",
        "views/crm_lead_views.xml",
        "views/business_project_approval_views.xml",
        "views/business_project_views.xml",
        "views/project_stage_views.xml",
        "views/menu.xml"
    ],
    'assets': {
        'web.assets_backend': [
            'Benjali_management/static/src/js/dashboard.js',
            'Benjali_management/static/src/xml/dashboard.xml',
            'Benjali_management/static/src/scss/dashboard.scss',
        ]},
    "installable": True,
    "application": True,
}