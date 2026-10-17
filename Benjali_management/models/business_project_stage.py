from odoo import models, fields, api


class BusinessProjectStage(models.Model):
    _name = 'business.project.stage'
    _description = 'Business Project Stage'
    _order = 'sequence, id'

    name = fields.Char(
        string='Stage Name',
        required=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    phase = fields.Selection(
        [
            ('sales', 'Sales & Business Development'),
            ('onboarding', 'Onboarding & Project Initiation'),
            ('planning', 'Planning & Analysis'),
        ],
        string='Phase',
        required=True,
        default='sales'
    )

    description = fields.Text(
        string='Description'
    )

    responsible_role = fields.Char(
        string='Responsible Role'
    )

    approver_role = fields.Char(
        string='Approver Role'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    folded = fields.Boolean(
        string='Folded in Kanban',
        default=False
    )

    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=False
    )

    approval_type = fields.Selection([
        ('management_review', 'Management Review'),
        ('kra', 'KRA Approval'),
        ('activity_plan', 'Activity Plan Approval'),
        ('other', 'Other'),
    ], string='Approval Type')

    @api.onchange('requires_approval', 'name')
    def _onchange_requires_approval(self):
        if self.requires_approval and not self.approval_type:
            name_lower = (self.name or '').lower()
            if 'management' in name_lower or 'review' in name_lower:
                self.approval_type = 'management_review'
            elif 'kra' in name_lower:
                self.approval_type = 'kra'
            elif 'activity' in name_lower:
                self.approval_type = 'activity_plan'
            else:
                self.approval_type = 'other'

    approver_id = fields.Many2one(
        'res.users',
        string='Default Approver'
    )

    responsible_user_id = fields.Many2one(
        'res.users',
        string='Default Responsible User'
    )