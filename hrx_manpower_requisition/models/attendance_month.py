from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

HR_MANAGER = 'hr.group_hr_manager'
HOLIDAY_DOMAIN = [('time_type', '=', 'leave'), ('resource_id', '=', False)]

EXCEPTION_TYPES = [
    ('late', 'Late Arrival'),
    ('early', 'Early Leaving'),
    ('absent', 'Absent (No Approval)'),
    ('no_checkout', 'Missing Check-out'),
    ('extra', 'Worked on Week-off / Holiday'),
]


def _subtract(segments, cuts):
    """Remove the cut intervals from the (start, end) segments."""
    cuts = sorted((c[0], c[1]) for c in cuts)
    for cut_start, cut_end in cuts:
        remaining = []
        for a, b in segments:
            if cut_end <= a or cut_start >= b:
                remaining.append((a, b))
                continue
            if cut_start > a:
                remaining.append((a, cut_start))
            if cut_end < b:
                remaining.append((cut_end, b))
        segments = remaining
    return segments


def _intersect(segments, windows):
    """Parts of the segments that fall inside the windows."""
    out = []
    for a, b in segments:
        for w_start, w_end in windows:
            start, end = max(a, w_start), min(b, w_end)
            if start < end:
                out.append((start, end))
    return out


def _hours_per_day(segments, tz):
    """Total hours of the segments per local calendar day."""
    hours = defaultdict(float)
    for a, b in segments:
        hours[a.astimezone(tz).date()] += (b - a).total_seconds() / 3600.0
    return hours


class HrxAttendanceMonth(models.Model):
    _name = 'hrx.attendance.month'
    _description = 'Monthly Attendance'
    _inherit = ['mail.thread']
    _order = 'date_from desc'

    name = fields.Char(compute='_compute_name', store=True)
    date_from = fields.Date(
        'Month', required=True, tracking=True,
        default=lambda s: fields.Date.context_today(s).replace(day=1))
    date_to = fields.Date(compute='_compute_date_to', store=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('finalized', 'Finalized'),
    ], default='draft', required=True, tracking=True, copy=False)

    grace_late = fields.Integer('Late Grace (minutes)', default=15)
    grace_early = fields.Integer('Early-leaving Grace (minutes)', default=15)
    late_limit = fields.Integer(
        'Frequent Late / Early Limit', default=3,
        help="Employees with this many late arrivals (or early leavings) are flagged.")
    absence_limit = fields.Integer(
        'Frequent Absence Limit (days)', default=2,
        help="Employees with this many unapproved absent days are flagged as frequent absence.")

    line_ids = fields.One2many('hrx.attendance.month.line', 'month_id', string='Employees')
    exception_ids = fields.One2many('hrx.attendance.exception', 'month_id', string='Irregularities')
    line_count = fields.Integer(compute='_compute_counts')
    irregular_count = fields.Integer(compute='_compute_counts')

    computed_date = fields.Datetime(readonly=True, copy=False)
    finalized_by = fields.Many2one('res.users', readonly=True, copy=False)
    finalized_date = fields.Datetime(readonly=True, copy=False)

    # ------------------------------------------------------------------
    @api.depends('date_from')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.date_from.strftime('%B %Y') if rec.date_from else _("New")

    @api.depends('date_from')
    def _compute_date_to(self):
        for rec in self:
            rec.date_to = rec.date_from + relativedelta(months=1, days=-1) if rec.date_from else False

    @api.depends('line_ids', 'line_ids.is_irregular')
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.irregular_count = len(rec.line_ids.filtered('is_irregular'))

    @api.constrains('date_from', 'company_id')
    def _check_unique_month(self):
        for rec in self:
            if self.search_count([('id', '!=', rec.id), ('date_from', '=', rec.date_from),
                                  ('company_id', '=', rec.company_id.id)]):
                raise ValidationError(_("This month already exists for the company."))

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('date_from'):
                vals['date_from'] = fields.Date.to_date(vals['date_from']).replace(day=1)
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('hrx_wf') and any(r.state == 'finalized' for r in self):
            raise UserError(_("A finalized month cannot be edited. Ask an HR Manager to reopen it."))
        if vals.get('date_from'):
            vals['date_from'] = fields.Date.to_date(vals['date_from']).replace(day=1)
        return super().write(vals)

    def unlink(self):
        if any(r.state != 'draft' for r in self):
            raise UserError(_("Only draft months can be deleted."))
        return super().unlink()

    def _require_manager(self):
        if not (self.env.su or self.env.user.has_group(HR_MANAGER)):
            raise AccessError(_("Only an HR Manager can do this."))

    # ------------------------------------------------------------------
    # Helpers for the computation
    # ------------------------------------------------------------------
    @staticmethod
    def _schedule_window(emp, day):
        """Start and end hour (float) the employee is expected to work on that day."""
        cal = emp.resource_calendar_id
        if not cal:
            return None, None
        lines = cal.attendance_ids.filtered(
            lambda a: not getattr(a, 'display_type', False)
            and getattr(a, 'day_period', None) != 'lunch'
            and int(a.dayofweek) == day.weekday())
        if getattr(cal, 'two_weeks_calendar', False):
            week = str(int((day.toordinal() - 1) // 7 % 2))
            lines = lines.filtered(lambda a: a.week_type == week)
        if not lines:
            return None, None
        return min(lines.mapped('hour_from')), max(lines.mapped('hour_to'))

    @staticmethod
    def _covered(permissions, start_h, end_h):
        """True if one approved permission covers [start_h, end_h]."""
        return any(pf <= start_h + 0.02 and pt >= end_h - 0.02 for pf, pt in permissions)

    @staticmethod
    def _hour(dt):
        return dt.hour + dt.minute / 60.0

    @staticmethod
    def _work_days(emp, date_from, date_to):
        try:
            data = emp._get_work_days_data_batch(
                date_from, date_to, compute_leaves=True, domain=HOLIDAY_DOMAIN)
        except TypeError:
            data = emp._get_work_days_data_batch(date_from, date_to, compute_leaves=False)
        return data[emp.id]['days']

    def _employees(self):
        self.ensure_one()
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        domain = [('company_id', '=', self.company_id.id)]
        if 'departure_date' in Emp._fields:
            domain += ['|', ('active', '=', True), ('departure_date', '>=', self.date_from)]
        else:
            domain += [('active', '=', True)]
        return Emp.search(domain)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    def action_compute(self):
        for rec in self:
            if rec.state == 'finalized':
                raise UserError(_("This month is finalized. Reopen it to compute again."))
            rec._compute_month()
        return True

    def _compute_month(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        cutoff = min(self.date_to, today - timedelta(days=1))
        if cutoff < self.date_from:
            raise UserError(_("This month has no completed days yet."))

        Line = self.env['hrx.attendance.month.line'].sudo()
        Exc = self.env['hrx.attendance.exception'].sudo()
        Att = self.env['hr.attendance'].sudo()
        Req = self.env['hrx.attendance.request'].sudo()
        Leave = self.env['hr.leave'].sudo()

        keep = {l.employee_id.id: (l.lop_adjustment, l.remarks) for l in self.line_ids}

        skipped = []
        self.line_ids.sudo().with_context(hrx_wf=True).unlink()

        for emp in self._employees():
            tz = pytz.timezone(emp.tz or self.env.user.tz or 'UTC')
            start, end = self.date_from, cutoff
            if emp.hrx_joining_date and emp.hrx_joining_date > start:
                start = emp.hrx_joining_date
            if 'departure_date' in emp._fields and emp.departure_date and emp.departure_date < end:
                end = emp.departure_date
            if start > end:
                continue

            utc_start = tz.localize(datetime.combine(start, time.min)).astimezone(pytz.utc)
            utc_end = tz.localize(datetime.combine(end + timedelta(days=1), time.min)).astimezone(pytz.utc)
            n_start, n_end = utc_start.replace(tzinfo=None), utc_end.replace(tzinfo=None)

            # Expected hours per local day: scheduled / after holidays / after holidays and leave
            # Expected hours per local day: scheduled / after holidays / after holidays and leave
            cal, res = emp.resource_calendar_id, emp.resource_id
            if not cal or not res:
                skipped.append(emp.name)
                continue
            work = [(i[0], i[1]) for i in cal._attendance_intervals_batch(
                utc_start, utc_end, resources=res, tz=tz).get(res.id, [])]
            glob_cuts = [(i[0], i[1]) for i in cal._leave_intervals_batch(
                utc_start, utc_end, resources=None, tz=tz).get(False, [])]
            emp_cuts = [(i[0], i[1]) for i in cal._leave_intervals_batch(
                utc_start, utc_end, resources=res, tz=tz).get(res.id, [])]
            work_glob = _subtract(work, glob_cuts)
            work_net = _subtract(work, emp_cuts)
            sched = _hours_per_day(work, tz)
            glob = _hours_per_day(work_glob, tz)
            net = _hours_per_day(work_net, tz)

            # Attendance by local day
            by_day = defaultdict(list)
            atts = Att.search([('employee_id', '=', emp.id), ('check_in', '>=', n_start),
                               ('check_in', '<', n_end)], order='check_in')
            for att in atts:
                loc = pytz.utc.localize(att.check_in).astimezone(tz)
                by_day[loc.date()].append((att, loc))

            # Approved WFH days and permissions
            wfh_days, perms, perm_hours = set(), defaultdict(list), 0.0
            for r in Req.search([('employee_id', '=', emp.id), ('state', '=', 'approved'),
                                 ('date_from', '<=', end), ('date_to', '>=', start)]):
                if r.request_type == 'wfh':
                    d = max(r.date_from, start)
                    while d <= min(r.date_to, end):
                        wfh_days.add(d)
                        d += timedelta(days=1)
                elif r.request_type == 'permission':
                    perms[r.date_from].append((r.hour_from, r.hour_to))
                    perm_hours += r.hours

            # Loss-of-pay leave days
            # Loss-of-pay leave days (fraction of each scheduled day covered by LOP leave)
            lop_windows = []
            for lv in Leave.search([('employee_id', '=', emp.id), ('state', '=', 'validate'),
                                    ('holiday_status_id.hrx_is_lop', '=', True),
                                    ('date_from', '<=', n_end), ('date_to', '>=', n_start)]):
                lop_windows.append((
                    pytz.utc.localize(max(lv.date_from, n_start)),
                    pytz.utc.localize(min(lv.date_to, n_end))))
            lop_hours = _hours_per_day(_intersect(work_glob, lop_windows), tz)
            lop_leave = sum(min(h / sched[day], 1.0)
                            for day, h in lop_hours.items() if sched.get(day))

            tot = defaultdict(float)
            exceptions = []
            d = start
            while d <= end:
                sched_h = sched.get(d, 0.0)
                day_atts = by_day.get(d, [])

                if sched_h <= 0.01:
                    if day_atts:
                        tot['extra'] += 1
                        exceptions.append((d, 'extra', 0, _("Worked on a week-off")))
                else:
                    f_glob = min(glob.get(d, 0.0) / sched_h, 1.0)
                    f_net = min(net.get(d, 0.0) / sched_h, 1.0)
                    tot['working'] += f_glob
                    tot['holiday'] += 1 - f_glob
                    tot['leave'] += max(f_glob - f_net, 0.0)

                    if f_glob <= 0.01 and day_atts:
                        tot['extra'] += 1
                        exceptions.append((d, 'extra', 0, _("Worked on a holiday")))

                    if f_net > 0.01:
                        if day_atts:
                            tot['present'] += f_net
                            if f_net >= 0.99:
                                s_h, e_h = self._schedule_window(emp, d)
                                dperm = perms.get(d, [])
                                if s_h is not None:
                                    ci = self._hour(day_atts[0][1])
                                    if ci > s_h + self.grace_late / 60.0 \
                                            and not self._covered(dperm, s_h, ci):
                                        mins = round((ci - s_h) * 60)
                                        tot['late'] += 1
                                        tot['late_min'] += mins
                                        exceptions.append((d, 'late', mins, _("%s minutes late", mins)))
                                outs = [pytz.utc.localize(a.check_out).astimezone(tz)
                                        for a, _loc in day_atts if a.check_out]
                                if outs and e_h is not None:
                                    co = self._hour(max(outs))
                                    if co < e_h - self.grace_early / 60.0 \
                                            and not self._covered(dperm, co, e_h):
                                        mins = round((e_h - co) * 60)
                                        tot['early'] += 1
                                        tot['early_min'] += mins
                                        exceptions.append((d, 'early', mins, _("Left %s minutes early", mins)))
                        elif d in wfh_days:
                            tot['wfh'] += f_net
                        else:
                            tot['absent'] += f_net
                            exceptions.append((d, 'absent', 0, _("No attendance, leave or WFH approval")))

                if any(not a.check_out for a, _loc in day_atts):
                    tot['no_checkout'] += 1
                    exceptions.append((d, 'no_checkout', 0, _("No check-out recorded")))
                d += timedelta(days=1)

            adj, remarks = keep.get(emp.id, (0.0, False))
            line = Line.create({
                'month_id': self.id,
                'employee_id': emp.id,
                'department_id': emp.department_id.id,
                'working_days': round(tot['working'], 2),
                'holiday_days': round(tot['holiday'], 2),
                'leave_days': round(tot['leave'], 2),
                'lop_leave_days': round(lop_leave, 2),
                'present_days': round(tot['present'], 2),
                'wfh_days': round(tot['wfh'], 2),
                'absent_days': round(tot['absent'], 2),
                'extra_days': int(tot['extra']),
                'late_count': int(tot['late']),
                'late_minutes': int(tot['late_min']),
                'early_count': int(tot['early']),
                'early_minutes': int(tot['early_min']),
                'no_checkout_count': int(tot['no_checkout']),
                'permission_hours': round(perm_hours, 2),
                'worked_hours': round(sum(atts.mapped('worked_hours')), 2),
                'lop_adjustment': adj,
                'remarks': remarks,
            })
            Exc.create([{
                'month_id': self.id, 'line_id': line.id, 'date': ex[0],
                'type': ex[1], 'minutes': ex[2], 'note': ex[3],
            } for ex in exceptions])

        self.with_context(hrx_wf=True).write({
            'state': 'computed', 'computed_date': fields.Datetime.now()})
        self.message_post(body=_("Computed by %s up to %s.", self.env.user.name, cutoff))
        if skipped:
            self.message_post(body=_(
                "Skipped (no working hours set on the employee): %s", ", ".join(skipped)))

    # ------------------------------------------------------------------
    # Finalize / reopen
    # ------------------------------------------------------------------
    def action_finalize(self):
        self._require_manager()
        Leave = self.env['hr.leave'].sudo()
        Req = self.env['hrx.attendance.request'].sudo()
        Att = self.env['hr.attendance'].sudo()
        for rec in self:
            if rec.state != 'computed':
                raise UserError(_("Compute the month first."))
            if rec.date_to >= fields.Date.context_today(rec):
                raise UserError(_("The month is not over yet."))
            lo = datetime.combine(rec.date_from, time.min) - timedelta(days=1)
            hi = datetime.combine(rec.date_to, time.max) + timedelta(days=1)

            pending_leave = Leave.search_count([
                ('state', 'in', ('confirm', 'validate1')),
                ('employee_id.company_id', '=', rec.company_id.id),
                ('date_from', '<=', hi), ('date_to', '>=', lo)])
            pending_req = Req.search_count([
                ('state', '=', 'submitted'), ('company_id', '=', rec.company_id.id),
                ('date_from', '<=', rec.date_to), ('date_to', '>=', rec.date_from)])
            if pending_leave or pending_req:
                raise UserError(_(
                    "Resolve pending items first: %(l)s leave request(s) and "
                    "%(r)s attendance request(s) are waiting for approval.",
                    l=pending_leave, r=pending_req))

            changed = (
                Att.search_count([('write_date', '>', rec.computed_date),
                                  ('check_in', '>=', lo), ('check_in', '<=', hi)])
                + Req.search_count([('write_date', '>', rec.computed_date),
                                    ('state', '=', 'approved'),
                                    ('company_id', '=', rec.company_id.id),
                                    ('date_from', '<=', rec.date_to), ('date_to', '>=', rec.date_from)])
                + Leave.search_count([('write_date', '>', rec.computed_date),
                                      ('state', '=', 'validate'),
                                      ('employee_id.company_id', '=', rec.company_id.id),
                                      ('date_from', '<=', hi), ('date_to', '>=', lo)]))
            if changed:
                raise UserError(_("Attendance, leave or request data changed after the last "
                                  "computation. Click Compute again before finalizing."))
        self.with_context(hrx_wf=True).write({
            'state': 'finalized',
            'finalized_by': self.env.user.id,
            'finalized_date': fields.Datetime.now(),
        })
        for rec in self:
            rec.message_post(body=_("Month finalized by %s.", self.env.user.name))

    def action_reopen(self):
        self._require_manager()
        for rec in self:
            if rec.state != 'finalized':
                raise UserError(_("Only finalized months can be reopened."))
        self.with_context(hrx_wf=True).write({
            'state': 'computed', 'finalized_by': False, 'finalized_date': False})
        for rec in self:
            rec.message_post(body=_("Month reopened by %s.", self.env.user.name))



class HrxAttendanceMonthLine(models.Model):
    _name = 'hrx.attendance.month.line'
    _description = 'Monthly Attendance Line'
    _order = 'department_id, employee_id'

    month_id = fields.Many2one('hrx.attendance.month', required=True, ondelete='cascade', index=True)
    month_state = fields.Selection(related='month_id.state')
    company_id = fields.Many2one(related='month_id.company_id', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, readonly=True, index=True)
    department_id = fields.Many2one('hr.department', readonly=True)

    working_days = fields.Float(readonly=True, help="Scheduled days after public holidays.")
    holiday_days = fields.Float(readonly=True)
    leave_days = fields.Float('Leave Days', readonly=True)
    lop_leave_days = fields.Float('LOP Leave Days', readonly=True)
    present_days = fields.Float(readonly=True)
    wfh_days = fields.Float('WFH Days', readonly=True)
    absent_days = fields.Float('Absent (No Approval)', readonly=True)
    extra_days = fields.Integer('Worked on Off Days', readonly=True)
    late_count = fields.Integer(readonly=True)
    late_minutes = fields.Integer(readonly=True)
    early_count = fields.Integer(readonly=True)
    early_minutes = fields.Integer(readonly=True)
    no_checkout_count = fields.Integer('Missing Check-outs', readonly=True)
    permission_hours = fields.Float(readonly=True)
    worked_hours = fields.Float(readonly=True)

    lop_adjustment = fields.Float(
        'LOP Adjustment', help="Days added to (or, if negative, removed from) Loss of Pay.")
    remarks = fields.Char()
    lop_total = fields.Float(
        'Total LOP Days', compute='_compute_lop_total', store=True,
        help="LOP leave + unapproved absence + adjustment.")
    is_irregular = fields.Boolean(compute='_compute_irregular', store=True)
    irregularity_summary = fields.Char(compute='_compute_irregular', store=True)

    @api.depends('lop_leave_days', 'absent_days', 'lop_adjustment')
    def _compute_lop_total(self):
        for rec in self:
            rec.lop_total = max(rec.lop_leave_days + rec.absent_days + rec.lop_adjustment, 0.0)

    @api.depends('late_count', 'early_count', 'absent_days', 'no_checkout_count',
                 'month_id.late_limit', 'month_id.absence_limit')
    def _compute_irregular(self):
        for rec in self:
            m, notes = rec.month_id, []
            if m.late_limit and rec.late_count >= m.late_limit:
                notes.append(_("Frequent late (%s)", rec.late_count))
            if m.late_limit and rec.early_count >= m.late_limit:
                notes.append(_("Frequent early leaving (%s)", rec.early_count))
            if rec.absent_days > 0:
                label = _("Frequent absence") if (
                    m.absence_limit and rec.absent_days >= m.absence_limit) else _("Absent")
                notes.append(_("%(l)s (%(d)s day)", l=label, d=rec.absent_days))
            if rec.no_checkout_count:
                notes.append(_("Missing check-out (%s)", rec.no_checkout_count))
            rec.is_irregular = bool(notes)
            rec.irregularity_summary = "; ".join(notes)

    def write(self, vals):
        if not self.env.context.get('hrx_wf') and any(
                l.month_id.state == 'finalized' for l in self):
            raise UserError(_("This month is finalized. Ask an HR Manager to reopen it."))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('hrx_wf') and any(
                l.month_id.state == 'finalized' for l in self):
            raise UserError(_("This month is finalized."))
        return super().unlink()

    def action_view_exceptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Irregularities - %s", self.employee_id.name),
            'res_model': 'hrx.attendance.exception',
            'view_mode': 'list',
            'domain': [('line_id', '=', self.id)],
        }


class HrxAttendanceException(models.Model):
    _name = 'hrx.attendance.exception'
    _description = 'Attendance Irregularity'
    _order = 'date desc, id'

    month_id = fields.Many2one('hrx.attendance.month', required=True, ondelete='cascade', index=True)
    line_id = fields.Many2one('hrx.attendance.month.line', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='month_id.company_id', store=True)
    employee_id = fields.Many2one(related='line_id.employee_id', store=True, index=True)
    department_id = fields.Many2one(related='line_id.department_id', store=True)
    date = fields.Date(required=True, index=True)
    type = fields.Selection(EXCEPTION_TYPES, required=True, index=True)
    minutes = fields.Integer()
    note = fields.Char()