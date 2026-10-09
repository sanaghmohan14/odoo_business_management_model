from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MOD = 'hrx_manpower_requisition'
G_HR = f'{MOD}.group_hrx_hr'
G_CEO = f'{MOD}.group_hrx_ceo'


class HrxEmployeeRequest(models.Model):
    _name = 'hrx.employee.request'
    _description = 'Interdepartmental & Employee HR Support Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    def _default_employee(self):
        return self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)], limit=1).id

    name = fields.Char('Reference', default='New', readonly=True, copy=False)
    employee_id = fields.Many2one('hr.employee', string='Requested By', required=True,
                                  default=_default_employee, tracking=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True)

    request_type = fields.Selection([
        ('hr_document', 'HR Document Request (Letters, Certificates)'),
        ('recruitment', 'Recruitment / Replacement Request'),
        ('training', 'Training Request'),
        ('employee_issue', 'Employee Grievance / Workplace Issue'),
        ('asset_coordination', 'Asset Coordination'),
        ('dept_transfer', 'Department Transfer Request'),
        ('performance', 'Performance-related Request'),
        ('other', 'General HR Support'),
    ], string='Request Type', required=True, default='hr_document', tracking=True)

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='1', tracking=True)

    subject = fields.Char('Subject / Summary', required=True, tracking=True)
    description = fields.Text('Request Details', required=True)

    state = fields.Selection([
        ('raised', 'Request Raised'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('action_taken', 'Action Taken'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='raised', required=True, tracking=True, copy=False)

    assigned_to = fields.Many2one('res.users', string='Assigned HR Person', tracking=True)
    action_taken = fields.Text('Action Taken / Response', tracking=True)
    resolution_date = fields.Datetime('Resolution Date', readonly=True)
    closure_notes = fields.Text('Closure Remarks')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hrx.employee.request') or 'New'
        return super().create(vals_list)

    def action_assign(self):
        for rec in self:
            rec.write({
                'state': 'assigned',
                'assigned_to': rec.assigned_to.id or self.env.user.id,
            })

    def action_start(self):
        for rec in self:
            rec.state = 'in_progress'

    def action_take_action(self):
        for rec in self:
            if not rec.action_taken:
                raise UserError(_("Please describe the action taken before moving forward."))
            rec.write({
                'state': 'action_taken',
                'resolution_date': fields.Datetime.now(),
            })

    def action_complete(self):
        for rec in self:
            rec.state = 'completed'

    def action_close(self):
        for rec in self:
            rec.state = 'closed'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'
