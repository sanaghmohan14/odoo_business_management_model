from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    kra_id = fields.Many2one(
        'business.project.kra', string='KRA', ondelete='set null', index=True)
    assigned_employee_id = fields.Many2one(
        'res.users', string='KRA Employee', index=True,
        help='Employee whose task performance is measured in KRA entries.')
    performance_status = fields.Selection([
        ('pending', 'Pending'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'), ('on_hold', 'On Hold'),
        ('blocked', 'Blocked'), ('cancelled', 'Cancelled'),
    ], string='KRA Task Status', default='pending', index=True)
    kra_entry_ids = fields.One2many(
        'business.project.kra.entry', 'task_id', string='Performance Entries')

    business_project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        ondelete='set null',
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            business_project_id = vals.get('business_project_id')
            if business_project_id and not vals.get('project_id'):
                business_project = self.env['business.project'].browse(
                    business_project_id
                )
                if business_project.project_id:
                    vals['project_id'] = business_project.project_id.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('business_project_id') and not vals.get('project_id'):
            business_project = self.env['business.project'].browse(
                vals['business_project_id']
            )
            if business_project.project_id:
                vals['project_id'] = business_project.project_id.id
        return super().write(vals)
