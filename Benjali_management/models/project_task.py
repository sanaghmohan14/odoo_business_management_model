from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

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
