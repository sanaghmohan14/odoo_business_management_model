import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

HR_USER = 'hr.group_hr_user'
HR_MANAGER = 'hr.group_hr_manager'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ---------------- Pre-joining ----------------
    hrx_offer_accepted_date = fields.Date('Offer Accepted On', groups=HR_USER)
    hrx_joining_date = fields.Date('Date of Joining', groups=HR_USER)
    hrx_joining_confirmed = fields.Boolean('Joining Confirmed', groups=HR_USER)

    # ---------------- Salary (HR Manager only) ----------------
    hrx_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', string='Currency')
    hrx_salary = fields.Monetary(
        'Salary (Monthly)', currency_field='hrx_currency_id', groups=HR_MANAGER)

    # ---------------- Identity ----------------
    hrx_aadhaar_no = fields.Char('Aadhaar Number', groups=HR_USER, copy=False)
    hrx_pan_no = fields.Char('PAN Number', groups=HR_USER, copy=False)

    # ---------------- Documents ----------------
    hrx_document_ids = fields.One2many(
        'hrx.emp.doc', 'employee_id', string='Joining Documents',
        domain=[('category', '=', 'joining')], groups=HR_USER)
    hrx_exit_document_ids = fields.One2many(
        'hrx.emp.doc', 'employee_id', string='Exit Documents',
        domain=[('category', '=', 'exit')], groups=HR_USER)
    hrx_docs_summary = fields.Char(compute='_compute_hrx_docs_summary', groups=HR_USER)
    hrx_exit_docs_summary = fields.Char(compute='_compute_hrx_docs_summary', groups=HR_USER)
    hrx_notes = fields.Text('Other HR Notes', groups=HR_USER)

    # ---------------- Lifecycle ----------------
    hrx_event_ids = fields.One2many(
        'hrx.employee.event', 'employee_id', string='Lifecycle Events', groups=HR_USER)
    hrx_event_count = fields.Integer(compute='_compute_hrx_event_count', groups=HR_USER)
    hrx_probation_start = fields.Date('Probation Start', groups=HR_USER, copy=False)
    hrx_probation_end = fields.Date('Probation End', groups=HR_USER, copy=False)
    hrx_confirmation_date = fields.Date('Confirmation Date', groups=HR_USER, copy=False)
    hrx_probation_state = fields.Selection([
        ('not_set', 'Not Set'),
        ('on_probation', 'On Probation'),
        ('confirmed', 'Confirmed'),
    ], compute='_compute_hrx_probation_state', string='Probation Status', groups=HR_USER)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('hrx_document_ids.state', 'hrx_document_ids.is_required',
                 'hrx_exit_document_ids.state', 'hrx_exit_document_ids.is_required')
    def _compute_hrx_docs_summary(self):
        for emp in self:
            for docs, fname in ((emp.hrx_document_ids, 'hrx_docs_summary'),
                                (emp.hrx_exit_document_ids, 'hrx_exit_docs_summary')):
                required = docs.filtered('is_required')
                verified = required.filtered(lambda d: d.state == 'verified')
                emp[fname] = _("%(v)s of %(t)s required documents verified",
                               v=len(verified), t=len(required))

    @api.depends('hrx_event_ids')
    def _compute_hrx_event_count(self):
        for emp in self:
            emp.hrx_event_count = len(emp.hrx_event_ids)

    @api.depends('hrx_probation_start', 'hrx_confirmation_date')
    def _compute_hrx_probation_state(self):
        for emp in self:
            if emp.hrx_confirmation_date:
                emp.hrx_probation_state = 'confirmed'
            elif emp.hrx_probation_start:
                emp.hrx_probation_state = 'on_probation'
            else:
                emp.hrx_probation_state = 'not_set'

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.constrains('hrx_aadhaar_no')
    def _check_hrx_aadhaar(self):
        for emp in self:
            if emp.hrx_aadhaar_no:
                digits = emp.hrx_aadhaar_no.replace(' ', '')
                if not re.fullmatch(r'\d{12}', digits):
                    raise ValidationError(_("Aadhaar number must be 12 digits."))

    @api.constrains('hrx_pan_no')
    def _check_hrx_pan(self):
        for emp in self:
            if emp.hrx_pan_no and not re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]', emp.hrx_pan_no):
                raise ValidationError(
                    _("PAN must be in the format ABCDE1234F (capital letters)."))

    @api.onchange('hrx_pan_no')
    def _onchange_hrx_pan(self):
        if self.hrx_pan_no:
            self.hrx_pan_no = self.hrx_pan_no.strip().upper()

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------
    def _hrx_add_documents(self, category, only_auto=False):
        domain = [('category', '=', category)]
        if only_auto:
            domain.append(('auto_add', '=', True))
        types = self.env['hrx.emp.doc.type'].sudo().search(domain)
        for emp in self.sudo():
            have = emp.hrx_document_ids.mapped('type_id') | emp.hrx_exit_document_ids.mapped('type_id')
            lines = [(0, 0, {'type_id': t.id}) for t in types - have]
            if lines:
                emp.write({'hrx_document_ids' if category == 'joining'
                           else 'hrx_exit_document_ids': lines})

    def action_hrx_add_documents(self):
        """Joining documents, for employees created before this module existed."""
        self._hrx_add_documents('joining', only_auto=True)

    def action_hrx_add_exit_documents(self):
        """Add the exit document checklist when an employee resigns or leaves."""
        self._hrx_add_documents('exit')

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def action_hrx_view_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Lifecycle Events"),
            'res_model': 'hrx.employee.event',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_hrx_create_joining_events(self):
        """Create a Joining event for employees that don't have one yet."""
        Event = self.env['hrx.employee.event'].sudo().with_context(hrx_wf=True)
        for emp in self.sudo():
            if emp.hrx_event_ids.filtered(lambda e: e.event_type == 'joining'):
                continue
            Event.create({
                'employee_id': emp.id,
                'event_type': 'joining',
                'date': emp.hrx_joining_date or fields.Date.context_today(emp),
                'state': 'approved',
                'approved_by': self.env.uid,
                'approval_date': fields.Datetime.now(),
                'reason': _("Employee record created."),
            })

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._hrx_add_documents('joining', only_auto=True)
        records.action_hrx_create_joining_events()
        return records

    # ------------------------------------------------------------------
    # Scheduled action
    # ------------------------------------------------------------------
    @api.model
    def _hrx_cron_probation_alert(self, days=15):
        today = fields.Date.context_today(self)
        emps = self.search([
            ('hrx_probation_end', '>=', today),
            ('hrx_probation_end', '<=', today + timedelta(days=days)),
            ('hrx_confirmation_date', '=', False),
        ])
        group = self.env.ref('hr.group_hr_manager').sudo()
        users = self.env['res.users']
        for fname in ('all_user_ids', 'user_ids', 'users'):
            if fname in group._fields:
                users = group[fname]
                break
        users = users.filtered(lambda u: u.active and not u.share)
        summary = _("Probation ending soon")
        for emp in emps:
            for user in users:
                if emp.activity_ids.filtered(
                        lambda a: a.summary == summary and a.user_id == user):
                    continue
                emp.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    date_deadline=emp.hrx_probation_end, summary=summary,
                    note=_("Probation of %(name)s ends on %(date)s. Decide on confirmation.",
                           name=emp.name, date=emp.hrx_probation_end))