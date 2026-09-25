from odoo import models, fields


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    business_project_ids = fields.One2many(
        'business.project',
        'department_id',
        string='Business Projects'
    )

    def action_open_business_projects(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': self.name + ' - Business Projects',
            'res_model': 'business.project',
            'view_mode': 'kanban,list,form',
            'domain': [
                ('department_id', '=', self.id)
            ],
            'context': {
                'default_department_id': self.id,
            },
            'target': 'current',
        }