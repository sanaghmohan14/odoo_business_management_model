from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # Allow stages with no project_ids to be used by every project task.



    title = fields.Char(string='Title')

    assignee_id = fields.Many2one('res.users', string='Assignee')

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        ondelete='set null',
        index=True,
    )

    business_project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        ondelete='set null',
        index=True,
    )

    task_id = fields.Many2one(
        'business.project',
        string='Business Project',
        ondelete='cascade',
    )


    @api.model_create_multi
    def create(self, vals_list):
        """Use the task title as the standard Project name.

        Records created from the Business Project Tasks notebook are
        project.project records. The Project app identifies them by ``name``,
        while the notebook previously only filled the custom ``title`` field.
        """
        for vals in vals_list:
            if vals.get('title') and not vals.get('name'):
                vals['name'] = vals['title']
        projects = super().create(vals_list)

        for project in projects:
            if (
                    project.department_id
                    and project.partner_id
                    and not project.business_project_id
            ):
                business_project = self.env['business.project'].create({
                    'name': project.name,
                    'partner_id': project.partner_id.id,
                    'department_id': project.department_id.id,
                    'sales_person_id': project.user_id.id,
                    'project_id': project.id,
                })
                project.business_project_id = business_project.id

        return projects

    def write(self, vals):
        if vals.get('title') and 'name' not in vals:
            vals['name'] = vals['title']
        return super().write(vals)

