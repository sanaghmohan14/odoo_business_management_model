from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

HR_USER = 'hr.group_hr_user'
HR_MANAGER = 'hr.group_hr_manager'


class HrxAttendanceRequest(models.Model):
    _name = 'hrx.attendance.request'
    _description = 'Attendance Request (Correction / WFH / Permission)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    def _default_employee(self):
        return self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1).id

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    request_type = fields.Selection([
        ('correction', 'Attendance Correction'),
        ('wfh', 'Work From Home'),
        ('permission', 'Permission (Short Leave)'),
    ], required=True, default='correction', tracking=True, index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, copy=False, tracking=True, index=True)

    employee_id = fields.Many2one(
        'hr.employee', required=True, default=_default_employee, index=True, tracking=True)
    employee_user_id = fields.Many2one(
        'res.users', related='employee_id.user_id', store=True, string='Employee User')
    manager_user_id = fields.Many2one(
        'res.users', related='employee_id.parent_id.user_id', store=True,
        string='Manager User')
    head_user_id = fields.Many2one(
        'res.users', related='employee_id.department_id.manager_id.user_id', store=True,
        string='Department Head User')
    department_id = fields.Many2one(
        'hr.department', related='employee_id.department_id', store=True)
    company_id = fields.Many2one(
        'res.company', related='employee_id.company_id', store=True)

    # Correction
    check_in = fields.Datetime('Correct Check-in')
    check_out = fields.Datetime('Correct Check-out')
    attendance_id = fields.Many2one(
        'hr.attendance', string='Attendance to Correct', groups=HR_USER,
        help="Only needed if the employee has several attendance records on that day.")

    # Dates / time
    date_from = fields.Date(
        'Date', compute='_compute_date_from', store=True, readonly=False,
        required=True, tracking=True, default=fields.Date.context_today)
    date_to = fields.Date(
        'To Date', compute='_compute_date_to', store=True, readonly=False)
    hour_from = fields.Float('From Time')
    hour_to = fields.Float('To Time')
    days = fields.Float(compute='_compute_amounts', store=True, string='Days')
    hours = fields.Float(compute='_compute_amounts', store=True, string='Hours')

    reason = fields.Text(required=True)
    decision_note = fields.Text('Decision Note')
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approval_date = fields.Datetime(readonly=True, copy=False)

    can_approve = fields.Boolean(compute='_compute_permissions')
    is_mine = fields.Boolean(compute='_compute_permissions')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('check_in', 'request_type')
    def _compute_date_from(self):
        for rec in self:
            if rec.request_type == 'correction' and rec.check_in:
                rec.date_from = fields.Datetime.context_timestamp(rec, rec.check_in).date()
            elif not rec.date_from:
                rec.date_from = fields.Date.context_today(rec)

    @api.depends('date_from', 'request_type')
    def _compute_date_to(self):
        for rec in self:
            if rec.request_type == 'wfh':
                if not rec.date_to or (rec.date_from and rec.date_to < rec.date_from):
                    rec.date_to = rec.date_from
            else:
                rec.date_to = rec.date_from

    @api.depends('request_type', 'date_from', 'date_to', 'hour_from', 'hour_to')
    def _compute_amounts(self):
        for rec in self:
            rec.days = 0.0
            rec.hours = 0.0
            if rec.request_type == 'wfh' and rec.date_from and rec.date_to:
                rec.days = (rec.date_to - rec.date_from).days + 1
            elif rec.request_type == 'permission':
                rec.hours = max(rec.hour_to - rec.hour_from, 0.0)

    @api.depends('state', 'employee_user_id', 'manager_user_id', 'head_user_id')
    def _compute_permissions(self):
        user = self.env.user
        is_hr = user.has_group(HR_USER)
        is_hr_manager = user.has_group(HR_MANAGER)
        for rec in self:
            own = rec.employee_user_id == user
            rec.is_mine = own or is_hr
            rec.can_approve = rec.state == 'submitted' and (
                (is_hr and (not own or is_hr_manager))
                or (not own and user in (rec.manager_user_id | rec.head_user_id)))

    @api.depends('request_type', 'employee_id', 'date_from')
    def _compute_display_name(self):
        labels = dict(self._fields['request_type'].selection)
        for rec in self:
            rec.display_name = "%s - %s - %s" % (
                labels.get(rec.request_type, ''), rec.employee_id.name or '',
                rec.date_from or '')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('request_type', 'check_in', 'check_out', 'date_from', 'date_to',
                    'hour_from', 'hour_to')
    def _check_values(self):
        for rec in self:
            t = rec.request_type
            if t == 'correction' and rec.check_in and rec.check_out \
                    and rec.check_out <= rec.check_in:
                raise ValidationError(_("Check-out must be after check-in."))
            if t == 'wfh' and rec.date_to < rec.date_from:
                raise ValidationError(_("The end date cannot be before the start date."))
            if t == 'permission':
                if not (0.0 <= rec.hour_from < rec.hour_to <= 24.0):
                    raise ValidationError(_("Enter a valid permission time range."))

    @api.constrains('employee_id', 'request_type', 'date_from', 'date_to',
                    'hour_from', 'hour_to', 'state')
    def _check_overlap(self):
        for rec in self.filtered(lambda r: r.state in ('submitted', 'approved')):
            others = self.sudo().search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('request_type', '=', rec.request_type),
                ('state', 'in', ('submitted', 'approved')),
                ('date_from', '<=', rec.date_to),
                ('date_to', '>=', rec.date_from),
            ])
            for other in others:
                if rec.request_type != 'permission' or (
                        rec.hour_from < other.hour_to and other.hour_from < rec.hour_to):
                    raise ValidationError(_(
                        "This overlaps an existing request (%s).", other.display_name))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su or self.env.user.has_group(HR_USER)):
            mine = self.env['hr.employee'].sudo().search(
                [('user_id', '=', self.env.uid)]).ids
            for vals in vals_list:
                if vals.get('employee_id') and vals['employee_id'] not in mine:
                    raise AccessError(_("You can only raise requests for yourself."))
        for vals in vals_list:
            if not vals.get('date_from'):
                if vals.get('check_in'):
                    check_in = fields.Datetime.to_datetime(vals['check_in'])
                    vals['date_from'] = fields.Datetime.context_timestamp(self, check_in).date()
                else:
                    vals['date_from'] = fields.Date.context_today(self)
            if not vals.get('date_to'):
                vals['date_to'] = vals['date_from']
        return super().create(vals_list)



    def write(self, vals):
        if not (self.env.su or self.env.context.get('hrx_wf')
                or self.env.user.has_group(HR_USER)):
            user = self.env.user
            for rec in self:
                is_approver = (user in (rec.manager_user_id | rec.head_user_id)
                               and rec.employee_user_id != user)
                if set(vals) <= {'decision_note'} and is_approver:
                    continue
                if rec.state != 'draft' or rec.employee_user_id != user:
                    raise UserError(_("Only your own draft requests can be edited."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state not in ('draft', 'cancelled') for rec in self):
            raise UserError(_("Only draft or cancelled requests can be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _hr_users(self):
        group = self.env.ref(HR_USER).sudo()
        users = self.env['res.users']
        for fname in ('all_user_ids', 'user_ids', 'users'):
            if fname in group._fields:
                users = group[fname]
                break
        return users.filtered(lambda u: u.active and not u.share)

    def _notify_approvers(self):
        labels = dict(self._fields['request_type'].selection)
        for rec in self:
            users = (rec.manager_user_id | rec.head_user_id) - rec.employee_user_id
            if not users:
                users = rec._hr_users() - rec.employee_user_id
            for user in users:
                rec.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_("Approve %s", labels[rec.request_type]))

    def _notify_employee(self, body):
        for rec in self:
            partner = rec.employee_user_id.partner_id
            rec.message_post(body=body, partner_ids=partner.ids if partner else [])

    def _close_activities(self):
        self.sudo().activity_feedback(['mail.mail_activity_data_todo'])

    def _check_can_act(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_("Only submitted requests can be approved or rejected."))
            if not (self.env.su or rec.can_approve):
                raise AccessError(_("You are not allowed to approve or reject this request."))

    # ------------------------------------------------------------------
    # Correction: write to the real attendance record
    # ------------------------------------------------------------------
    def _apply_correction(self):
        self.ensure_one()
        emp = self.employee_id.sudo()
        Attendance = self.env['hr.attendance'].sudo()
        vals = {'check_in': self.check_in, 'check_out': self.check_out}
        att = self.attendance_id.sudo()
        if not att:
            tz = pytz.timezone(emp.tz or self.env.user.tz or 'UTC')
            local_day = fields.Datetime.context_timestamp(
                self.with_context(tz=tz.zone), self.check_in).date()
            start = tz.localize(datetime.combine(local_day, time.min)) \
                .astimezone(pytz.utc).replace(tzinfo=None)
            att = Attendance.search([
                ('employee_id', '=', emp.id),
                ('check_in', '>=', start),
                ('check_in', '<', start + timedelta(days=1)),
            ])
            if len(att) > 1:
                raise UserError(_(
                    "%(emp)s has several attendance records on %(day)s. "
                    "Ask HR to select the one to correct.", emp=emp.name, day=local_day))
        if att:
            att.write(vals)
            self.message_post(body=_("Existing attendance record updated."))
        else:
            Attendance.create(dict(vals, employee_id=emp.id))
            self.message_post(body=_("New attendance record created."))

    # ------------------------------------------------------------------
    # Workflow
    # -----------------------------------------------------------------


    def _check_month_open(self):
        Month = self.env['hrx.attendance.month'].sudo()
        for rec in self:
            if Month.search_count([
                    ('state', '=', 'finalized'), ('company_id', '=', rec.company_id.id),
                    ('date_from', '<=', rec.date_to), ('date_to', '>=', rec.date_from)]):
                raise UserError(_(
                    "The attendance month containing %s is already finalized. "
                    "Ask an HR Manager to reopen it.", rec.date_from))


    def action_submit(self):
        self._check_month_open()
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            if not rec.is_mine:
                raise AccessError(_("You can only submit your own requests."))
            if rec.request_type == 'correction':
                if not (rec.check_in and rec.check_out):
                    raise UserError(_("Enter both the correct check-in and check-out."))
                if rec.check_in > now:
                    raise UserError(_("A correction cannot be for a future time."))
            if rec.request_type == 'permission' and not rec.hour_to:
                raise UserError(_("Enter the permission time range."))
        self.with_context(hrx_wf=True).write({'state': 'submitted'})
        self._notify_approvers()

    def action_approve(self):
        self._check_can_act()
        self._check_month_open()
        for rec in self:
            if rec.request_type == 'correction':
                rec._apply_correction()
        self._close_activities()
        self.with_context(hrx_wf=True).write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        self._notify_employee(_("Your request has been approved."))

    def action_reject(self):
        self._check_can_act()
        for rec in self:
            if not rec.decision_note:
                raise UserError(_("Enter the reason in Decision Note before rejecting."))
        self._close_activities()
        self.with_context(hrx_wf=True).write({
            'state': 'rejected',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        for rec in self:
            rec._notify_employee(_("Your request was rejected. Reason: %s", rec.decision_note))

    def action_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'submitted'):
                raise UserError(_("Only draft or submitted requests can be cancelled."))
            if not rec.is_mine:
                raise AccessError(_("You can only cancel your own requests."))
        self._close_activities()
        self.with_context(hrx_wf=True).write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('rejected', 'cancelled'):
                raise UserError(_("Only rejected or cancelled requests can be reset."))
            if not rec.is_mine:
                raise AccessError(_("You can only reset your own requests."))
        self.with_context(hrx_wf=True).write({'state': 'draft'})