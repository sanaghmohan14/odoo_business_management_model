from odoo import models, fields


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