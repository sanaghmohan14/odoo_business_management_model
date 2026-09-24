from odoo import models, fields


class BusinessProjectKRA(models.Model):
    _name = 'business.project.kra'
    _description = 'Business Project KRA'
    _order = 'sequence, id'

    project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        string='KRA',
        required=True
    )

    description = fields.Text(
        string='Description'
    )

    objective = fields.Text(
        string='Objective'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsible Person'
    )

    target = fields.Char(
        string='Target'
    )

    measurement = fields.Char(
        string='Measurement'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )