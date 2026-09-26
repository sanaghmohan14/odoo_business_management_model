from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Allow stages with no project_ids to be used by every project task.

    stage_id = fields.Many2one(
        domain="['|', ('project_ids', '=', project_id), ('project_ids', '=', False)]",
    )

    @api.model
    def stage_find(self, section_id, domain=None, order='sequence, id'):
        domain = list(domain or [])
        stage_domain = [('project_ids', '=', False)]
        if section_id:
            stage_domain = ['|', ('project_ids', '=', section_id)] + stage_domain
        return self.env['project.task.type'].search(
            stage_domain + domain,
            order=order,
            limit=1,
        ).id

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        project_id = self.env.context.get('default_project_id')
        if project_id and 'project_kanban' in self.env.context:
            stages = self.env['project.task.type'].search([
                '|',
                ('project_ids', '=', project_id),
                ('project_ids', '=', False),
            ], order='sequence, id')
        return stages
