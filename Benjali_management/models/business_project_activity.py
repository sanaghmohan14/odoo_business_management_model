from odoo import api, fields, models


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

    todo_activity_id = fields.Many2one(
        'mail.activity',
        string='To-do Activity',
        readonly=True,
        copy=False,
        ondelete='set null'
    )

    @api.model_create_multi
    def create(self, vals_list):
        activities = super().create(vals_list)
        activities._sync_todo_activities()
        return activities

    def write(self, vals):
        result = super().write(vals)
        if set(vals) & {
            'name', 'description', 'responsible_user_id',
            'planned_start', 'planned_end', 'state'
        }:
            self._sync_todo_activities()
        return result

    def unlink(self):
        self.mapped('todo_activity_id').unlink()
        return super().unlink()

    def _sync_todo_activities(self):
        todo_type = self.env.ref(
            'mail.mail_activity_data_todo',
            raise_if_not_found=False
        )
        project_model = self.env['ir.model']._get('business.project')
        today = fields.Date.context_today(self)

        for activity in self:
            if not todo_type or not activity.project_id or not activity.responsible_user_id:
                continue

            deadline = activity.planned_end or activity.planned_start or today
            values = {
                'activity_type_id': todo_type.id,
                'res_model_id': project_model.id,
                'res_id': activity.project_id.id,
                'summary': activity.name,
                'note': activity.description or activity.notes or False,
                'date_deadline': deadline,
                'user_id': activity.responsible_user_id.id,
                'active': activity.state not in ('completed', 'cancelled'),
            }

            if activity.todo_activity_id:
                activity.todo_activity_id.write(values)
            else:
                todo = self.env['mail.activity'].create(values)
                activity.todo_activity_id = todo.id
