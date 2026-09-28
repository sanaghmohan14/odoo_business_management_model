from odoo import fields, models


class BusinessProjectSubtask(models.Model):
    _name = 'business.project.subtask'
    _description = 'Business Project Sub-task'
    _order = 'id'

    project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        required=True,
        ondelete='cascade',
    )

    task = fields.Char(
        string='Task',
        required=True,
    )

    assignee_id = fields.Many2one(
        'res.users',
        string='Assignee',
        required=True,
    )

    completed= fields.Boolean(
        string='Completed',
    )
