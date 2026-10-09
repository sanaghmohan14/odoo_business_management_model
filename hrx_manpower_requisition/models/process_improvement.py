from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MOD = 'hrx_manpower_requisition'
G_HR = f'{MOD}.group_hrx_hr'
G_CEO = f'{MOD}.group_hrx_ceo'


class HrxProcessImprovement(models.Model):
    _name = 'hrx.process.improvement'
    _description = 'Operational Efficiency & Process Improvement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Initiative Title', required=True, tracking=True)
    existing_process = fields.Text('Existing Process', required=True)
    problem_identified = fields.Text('Problem / Inefficiency Identified', required=True)
    proposed_improvement = fields.Text('Proposed Improvement Solution', required=True)

    responsible_id = fields.Many2one('res.users', string='Responsible Person',
                                     default=lambda s: s.env.user, required=True, tracking=True)
    target_date = fields.Date('Target Implementation Date', tracking=True)
    expected_result = fields.Text('Expected Result / Benefit')
    actual_result = fields.Text('Actual Result / Outcome Achieved', tracking=True)

    state = fields.Selection([
        ('identified', 'Process / Issue Identified'),
        ('proposed', 'Improvement Proposed'),
        ('approved', 'Approved by CEO'),
        ('implementation', 'In Implementation'),
        ('monitoring', 'Monitoring'),
        ('result', 'Result Achieved'),
        ('cancelled', 'Cancelled'),
    ], default='identified', required=True, tracking=True, copy=False)

    approved_by = fields.Many2one('res.users', string='Approved By (CEO)', readonly=True, copy=False)
    approval_date = fields.Datetime('Approval Date', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)

    def action_propose(self):
        for rec in self:
            rec.state = 'proposed'

    def action_approve(self):
        if not (self.env.su or self.env.user.has_group(G_CEO)):
            raise AccessError(_("Only the CEO can approve process improvement initiatives."))
        for rec in self:
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })

    def action_implement(self):
        for rec in self:
            rec.state = 'implementation'

    def action_monitor(self):
        for rec in self:
            rec.state = 'monitoring'

    def action_record_result(self):
        for rec in self:
            if not rec.actual_result:
                raise UserError(_("Please describe the actual result before marking completed."))
            rec.state = 'result'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'
