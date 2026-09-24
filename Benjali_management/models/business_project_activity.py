from odoo import models, fields


class BusinessProjectActivity(models.Model):
    _name = 'business.project.activity'
    _description = 'Business Project Activity'
    _order = 'planned_start, id'

    project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        required=True,
        ondelete='cascade'
    )

    kra_id = fields.Many2one(
        'business.project.kra',
        string='KRA',
        ondelete='set null'
    )

    name = fields.Char(
        string='Activity',
        required=True
    )

    description = fields.Text(
        string='Description'
    )

    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsible Person',
        required=True
    )

    planned_start = fields.Date(
        string='Planned Start'
    )

    planned_end = fields.Date(
        string='Planned End'
    )

    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='medium')

    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='planned', required=True)

    notes = fields.Text(
        string='Notes'
    )