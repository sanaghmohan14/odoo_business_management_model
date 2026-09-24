from odoo import models, fields


class BusinessProjectTeam(models.Model):
    _name = 'business.project.team'
    _description = 'Business Project Team'
    _order = 'id'

    project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        required=True,
        ondelete='cascade'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Team Member',
        required=True
    )

    role = fields.Selection([
        ('project_manager', 'Project Manager'),
        ('lead_consultant', 'Lead Consultant'),
        ('consultant', 'Consultant'),
        ('business_analyst', 'Business Analyst'),
        ('technical_consultant', 'Technical Consultant'),
        ('other', 'Other'),
    ], string='Role', required=True)

    notes = fields.Text(
        string='Notes'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )