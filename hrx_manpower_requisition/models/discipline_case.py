from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MOD = 'hrx_manpower_requisition'
G_HR = f'{MOD}.group_hrx_hr'
G_CEO = f'{MOD}.group_hrx_ceo'
PRIVATE = f'{G_HR},{G_CEO}'

CASE_TYPES = [
    ('attendance', 'Attendance Violation'),
    ('policy', 'Policy Violation'),
    ('dress_code', 'Dress-code Violation'),
    ('work_discipline', 'Work Discipline Issue'),
    ('kra_kpi', 'KRA/KPI Non-compliance'),
    ('recognition', 'Appreciation / Recognition'),
]

DECISIONS = [
    ('no_action', 'No Action'),
    ('verbal_warning', 'Verbal Warning'),
    ('written_warning', 'Written Warning Letter'),
    ('show_cause', 'Show-cause Notice'),
    ('final_warning', 'Final Warning'),
    ('appreciation', 'Appreciation / Recognition'),
    ('other', 'Other Action'),
]

WARNING_DECISIONS = ('verbal_warning', 'written_warning', 'show_cause', 'final_warning')


class HrxDisciplineCase(models.Model):
    _name = 'hrx.discipline.case'
    _description = 'Discipline / HR Action Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'incident_date desc, id desc'

    name = fields.Char('Reference', default='New', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Reported'),
        ('review', 'HR Review'),
        ('explanation', 'Employee Explanation'),
        ('decision', 'Management Decision'),
        ('action', 'HR Action'),
        ('followup', 'Follow-up'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, copy=False, tracking=True, index=True)
    case_type = fields.Selection(CASE_TYPES, required=True, default='policy', tracking=True)
    severity = fields.Selection([
        ('minor', 'Minor'), ('major', 'Major'), ('critical', 'Critical'),
    ], default='minor', tracking=True)

    employee_id = fields.Many2one('hr.employee', required=True, index=True, tracking=True)
    employee_user_id = fields.Many2one(
        'res.users', related='employee_id.user_id', store=True, string='Employee User')
    department_id = fields.Many2one(
        'hr.department', related='employee_id.department_id', store=True)
    head_user_id = fields.Many2one(
        'res.users', related='employee_id.department_id.manager_id.user_id',
        store=True, string='Department Head User')
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True)
    reported_by = fields.Many2one(
        'res.users', default=lambda s: s.env.user, readonly=True, copy=False)
    incident_date = fields.Date(
        'Incident / Observation Date', required=True,
        default=fields.Date.context_today, tracking=True)
    description = fields.Text('Details')

    hr_review_note = fields.Text('HR Review Notes', groups=PRIVATE)

    explanation_deadline = fields.Date('Explanation Due By')
    explanation = fields.Text('Employee Explanation')
    explanation_date = fields.Datetime('Explanation Submitted On', readonly=True, copy=False)

    decision = fields.Selection(DECISIONS, string='Management Decision', tracking=True)
    decision_note = fields.Text('Decision Notes', groups=PRIVATE)
    decided_by = fields.Many2one('res.users', readonly=True, copy=False)
    decision_date = fields.Datetime(readonly=True, copy=False)

    action_taken = fields.Text('Action Taken')
    action_date = fields.Date('Action Date')
    action_by = fields.Many2one('res.users', readonly=True, copy=False)
    followup_date = fields.Date('Follow-up Date', tracking=True)
    followup_note = fields.Text('Follow-up Notes')

    closure_note = fields.Text('Closure Notes')
    closed_by = fields.Many2one('res.users', readonly=True, copy=False)
    closed_date = fields.Datetime(readonly=True, copy=False)

    is_hr = fields.Boolean(compute='_compute_flags')
    is_subject = fields.Boolean(compute='_compute_flags')
    can_edit_explanation = fields.Boolean(compute='_compute_flags')
    can_decide = fields.Boolean(compute='_compute_flags')

    # ------------------------------------------------------------------
    @api.depends('state', 'employee_user_id')
    def _compute_flags(self):
        user = self.env.user
        is_hr = user.has_group(G_HR)
        is_mgmt = user.has_group(G_CEO)
        for rec in self:
            rec.is_hr = is_hr
            rec.is_subject = rec.employee_user_id == user
            rec.can_edit_explanation = rec.state == 'explanation' and (rec.is_subject or is_hr)
            rec.can_decide = rec.state == 'decision' and is_mgmt

    @api.depends('name', 'employee_id', 'case_type')
    def _compute_display_name(self):
        labels = dict(CASE_TYPES)
        for rec in self:
            rec.display_name = "%s - %s - %s" % (
                rec.name, rec.employee_id.name or '', labels.get(rec.case_type, ''))

    # ------------------------------------------------------------------
    # Security helpers
    # ------------------------------------------------------------------
    def _is_employee_only(self):
        user = self.env.user
        return (not self.env.su and not user.has_group(G_HR) and not user.has_group(G_CEO)
                and not user.has_group('base.group_system'))

    def _require(self, *xmlids):
        user = self.env.user
        if self.env.su or user.has_group('base.group_system'):
            return
        if not any(user.has_group(x) for x in xmlids):
            raise AccessError(_("You are not allowed to perform this action."))

    @api.constrains('employee_id')
    def _check_head_employee(self):
        for rec in self:
            if rec.employee_user_id.id == self.env.user.id and not self.env.su and not self.env.user.has_group(G_HR):
                raise ValidationError(_("You cannot raise a discipline case about yourself."))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hrx.discipline.case') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if not (self.env.su or self.env.context.get('hrx_wf')
                or self.env.user.has_group(G_HR)):
            user = self.env.user
            keys = set(vals)
            for rec in self:
                if rec.state == 'explanation' and rec.employee_user_id == user \
                        and keys <= {'explanation'}:
                    continue
                if rec.state == 'decision' and user.has_group(G_MGMT) \
                        and keys <= {'decision', 'decision_note'}:
                    continue
                if rec.state == 'draft' and rec.employee_user_id != user \
                        and user in (rec.reported_by | rec.head_user_id):
                    continue
                raise UserError(_("You cannot edit this case in its current state."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state not in ('draft', 'cancelled') for rec in self):
            raise UserError(_("Only reported or cancelled cases can be deleted."))
        return super().unlink()

    def _wf_write(self, vals):
        return self.with_context(hrx_wf=True).write(vals)

    # ------------------------------------------------------------------
    # Notification helpers
    # ------------------------------------------------------------------
    def _users_of(self, xmlid):
        group = self.env.ref(xmlid).sudo()
        users = self.env['res.users']
        for fname in ('all_user_ids', 'user_ids', 'users'):
            if fname in group._fields:
                users = group[fname]
                break
        return users.filtered(lambda u: u.active and not u.share)

    def _todo(self, users, summary, deadline=None):
        for rec in self:
            for user in users:
                rec.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=summary, date_deadline=deadline)

    def _close_activities(self):
        self.sudo().activity_feedback(['mail.mail_activity_data_todo'])

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        self._require('base.group_user', G_HR)
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only reported cases can be submitted."))
            if not rec.description:
                raise UserError(_("Please describe the issue before submitting."))
        self._wf_write({'state': 'review'})
        self._todo(self._users_of(G_HR), _("Review discipline case"))

    def action_request_explanation(self):
        self._require(G_HR)
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != 'review':
                raise UserError(_("Only cases in HR Review can request an explanation."))
            if rec.case_type == 'recognition':
                raise UserError(_("Recognition cases do not need an explanation. "
                                  "Use Send for Decision."))
            if not rec.employee_user_id:
                raise UserError(_("%s has no user account to receive the request.",
                                  rec.employee_id.name))
            if not rec.explanation_deadline:
                rec._wf_write({'explanation_deadline': today + timedelta(days=3)})
        self._close_activities()
        self._wf_write({'state': 'explanation'})
        for rec in self:
            rec._todo(rec.employee_user_id, _("Submit your explanation"),
                      rec.explanation_deadline)
            rec.message_post(body=_("Explanation requested from %(emp)s, due by %(d)s.",
                                    emp=rec.employee_id.name, d=rec.explanation_deadline))

    def action_submit_explanation(self):
        user = self.env.user
        for rec in self:
            if rec.state != 'explanation':
                raise UserError(_("No explanation is being requested for this case."))
            if not (rec.employee_user_id == user or user.has_group(G_HR) or self.env.su):
                raise AccessError(_("Only the employee concerned can submit the explanation."))
            if not rec.explanation:
                raise UserError(_("Please write your explanation first."))
        self._close_activities()
        self._wf_write({'explanation_date': fields.Datetime.now()})
        self._todo(self._users_of(G_HR), _("Explanation received, review the case"))
        for rec in self:
            rec.message_post(body=_("Explanation submitted."))

    def action_send_decision(self):
        self._require(G_HR)
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state not in ('review', 'explanation'):
                raise UserError(_("Only cases in review or explanation can be sent for a decision."))
            if rec.state == 'explanation' and not rec.explanation_date and not (
                    rec.explanation_deadline and rec.explanation_deadline < today):
                raise UserError(_("Wait for the explanation, or until the due date has passed."))
        self._close_activities()
        self._wf_write({'state': 'decision'})
        for rec in self:
            rec._todo(self._users_of(G_CEO) - rec.employee_user_id,
                      _("Decide on discipline case"))

    def action_decide(self):
        self._require(G_CEO)
        for rec in self:
            if rec.state != 'decision':
                raise UserError(_("Only cases awaiting a decision can be decided."))
            if not rec.decision:
                raise UserError(_("Select a decision first."))
            if rec.employee_user_id == self.env.user and not self.env.su:
                raise UserError(_("You cannot decide a case about yourself."))
        self._close_activities()
        self._wf_write({
            'state': 'action',
            'decided_by': self.env.user.id,
            'decision_date': fields.Datetime.now(),
        })
        self._todo(self._users_of(G_HR), _("Record the action for this case"))

    def _check_action_ready(self):
        for rec in self:
            if rec.state != 'action':
                raise UserError(_("Only cases in HR Action can record an action."))
            if not rec.action_taken:
                raise UserError(_("Describe the action taken."))

    def action_record_followup(self):
        self._require(G_HR)
        self._check_action_ready()
        for rec in self:
            if not rec.followup_date:
                raise UserError(_("Set a follow-up date."))
        self._close_activities()
        for rec in self:
            rec._wf_write({'state': 'followup', 'action_by': self.env.user.id,
                           'action_date': rec.action_date or fields.Date.context_today(rec)})
            rec._log_lifecycle_event()

    def action_record_close(self):
        self._require(G_HR)
        self._check_action_ready()
        self._close_activities()
        for rec in self:
            rec._wf_write({
                'state': 'closed', 'action_by': self.env.user.id,
                'action_date': rec.action_date or fields.Date.context_today(rec),
                'closed_by': self.env.user.id, 'closed_date': fields.Datetime.now()})
            rec._log_lifecycle_event()

    def action_close(self):
        self._require(G_HR)
        for rec in self:
            if rec.state != 'followup':
                raise UserError(_("Only cases in follow-up can be closed."))
            if not rec.closure_note:
                raise UserError(_("Enter the closure notes."))
        self._close_activities()
        self._wf_write({'state': 'closed', 'closed_by': self.env.user.id,
                        'closed_date': fields.Datetime.now()})

    def action_cancel(self):
        user = self.env.user
        for rec in self:
            if rec.state in ('closed', 'cancelled'):
                raise UserError(_("This case is already closed or cancelled."))
            if not (self.env.su or user.has_group(G_HR) or (
                    rec.state == 'draft' and user in (rec.reported_by | rec.head_user_id))):
                raise AccessError(_("You cannot cancel this case."))
        self._close_activities()
        self._wf_write({'state': 'cancelled'})

    def action_reset_draft(self):
        self._require(G_HR)
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_("Only cancelled cases can be reset."))
        self._wf_write({'state': 'draft'})

    # ------------------------------------------------------------------
    # Lifecycle history
    # ------------------------------------------------------------------
    def _log_lifecycle_event(self):
        self.ensure_one()
        if self.decision in WARNING_DECISIONS:
            event_type = 'warning'
        elif self.decision == 'appreciation':
            event_type = 'recognition'
        else:
            return
        label = dict(DECISIONS).get(self.decision)
        self.env['hrx.employee.event'].sudo().with_context(hrx_wf=True).create({
            'employee_id': self.employee_id.id,
            'event_type': event_type,
            'date': self.action_date or fields.Date.context_today(self),
            'reason': "%s (%s): %s" % (label, self.name, self.action_taken or ''),
            'state': 'approved',
            'approved_by': self.env.uid,
            'approval_date': fields.Datetime.now(),
        })

    # ------------------------------------------------------------------
    # Scheduled action
    # ------------------------------------------------------------------
    @api.model
    def _cron_followup_reminder(self):
        today = fields.Date.context_today(self)
        cases = self.search([('state', '=', 'followup'), ('followup_date', '<=', today)])
        hr_users = self._users_of(G_HR)
        summary = _("Discipline case follow-up due")
        for case in cases:
            for user in hr_users:
                if case.activity_ids.filtered(
                        lambda a: a.user_id == user and a.summary == summary):
                    continue
                case.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=summary, date_deadline=case.followup_date)