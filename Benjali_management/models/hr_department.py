from odoo import api, fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    business_project_ids = fields.One2many(
        'business.project',
        'department_id',
        string='Business Projects'
    )
    kra_ids = fields.One2many(
        'business.project.kra',
        'department_id',
        string='Department KRAs'
    )
    kpi_ids = fields.One2many(
        'business.project.kpi',
        'department_id',
        string='Department KPIs'
    )

    project_count = fields.Integer(
        string='Projects',
        compute='_compute_department_performance'
    )
    kra_count = fields.Integer(
        string='KRAs',
        compute='_compute_department_performance'
    )
    kpi_count = fields.Integer(
        string='KPIs',
        compute='_compute_department_performance'
    )
    avg_kra_progress = fields.Float(
        string='Avg KRA Progress (%)',
        compute='_compute_department_performance'
    )

    @api.depends('business_project_ids', 'kra_ids', 'kpi_ids', 'kra_ids.progress_percentage', 'kra_ids.active')
    def _compute_department_performance(self):
        for dep in self:
            dep.project_count = len(dep.business_project_ids)
            dep.kra_count = len(dep.kra_ids)
            dep.kpi_count = len(dep.kpi_ids)
            active_kras = dep.kra_ids.filtered(lambda k: k.active)
            dep.avg_kra_progress = (
                sum(active_kras.mapped('progress_percentage')) / len(active_kras)
                if active_kras else 0.0
            )

    def action_open_business_projects(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Business Projects',
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

    def action_open_department_kras(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - KRAs',
            'res_model': 'business.project.kra',
            'view_mode': 'list,kanban,form',
            'domain': [
                ('department_id', '=', self.id)
            ],
            'context': {
                'default_department_id': self.id,
            },
            'target': 'current',
        }

    def action_open_department_kpis(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - KPIs',
            'res_model': 'business.project.kpi',
            'view_mode': 'list,form',
            'domain': [
                ('department_id', '=', self.id)
            ],
            'context': {
                'default_department_id': self.id,
            },
            'target': 'current',
        }