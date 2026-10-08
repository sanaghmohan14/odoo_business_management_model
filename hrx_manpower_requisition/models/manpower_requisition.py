from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError




MOD = 'hrx_manpower_requisition'
G_HEAD = f'{MOD}.group_mpr_dept_head'
G_HR = f'{MOD}.group_mpr_hr_exec'
G_MGMT = f'{MOD}.group_mpr_management'


class ManpowerRequisition(models.Model):
    _name = 'manpower.requisition'
    _description = 'Manpower Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    def _default_department(self):
        dept = self.env['hr.department'].sudo().search(
            [('manager_id.user_id', '=', self.env.uid)], limit=1)
        return dept.id

    # ------------------------------------------------------------------
    # Fields: raised by Department Head
    # ------------------------------------------------------------------
    name = fields.Char('Reference', default='New', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted to HR'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('done', 'Job Opened'),
    ], default='draft', required=True, copy=False, tracking=True, index=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)
    department_id = fields.Many2one(
        'hr.department', string='Department', required=True,
        default=_default_department, tracking=True)
    head_user_id = fields.Many2one(
        'res.users', string='Department Head (User)',
        related='department_id.manager_id.user_id', store=True)
    requested_by = fields.Many2one(
        'res.users', string='Requested By', default=lambda s: s.env.user,
        readonly=True, copy=False)
    request_date = fields.Date(default=fields.Date.context_today, readonly=True, copy=False)

    position_name = fields.Char('Position', required=True, tracking=True)
    job_id = fields.Many2one(
        'hr.job', string='Existing Job Position',
        help="Leave empty to create a new Job Position when the requisition is opened.")
    vacancies = fields.Integer('Number of Vacancies', default=1, required=True, tracking=True)
    reason = fields.Selection([
        ('new', 'New Position'),
        ('replacement', 'Replacement'),
        ('expansion', 'Expansion'),
        ('project', 'Project Based'),
    ], string='Reason for Requirement', required=True, tracking=True)
    replaced_employee_id = fields.Many2one('hr.employee', string='Employee Being Replaced')
    reason_note = fields.Text('Reason Details')
    joining_requirement = fields.Selection([
        ('immediate', 'Immediate'),
        ('15', 'Within 15 days'),
        ('30', 'Within 30 days'),
        ('60', 'Within 60 days'),
        ('90', 'Within 90 days'),
    ], string='Joining Requirement')

    # ------------------------------------------------------------------
    # Fields: completed by HR
    # ------------------------------------------------------------------
    experience_min = fields.Float('Min Experience (years)')
    experience_max = fields.Float('Max Experience (years)')
    qualification = fields.Text('Required Qualification')
    skills = fields.Text('Skills')
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)
    salary_min = fields.Monetary('Salary Range (From)', currency_field='currency_id')
    salary_max = fields.Monetary('Salary Range (To)', currency_field='currency_id')
    location = fields.Char('Work Location')

    # ------------------------------------------------------------------
    # Fields: decision
    # ------------------------------------------------------------------
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approval_date = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('vacancies')
    def _check_vacancies(self):
        for rec in self:
            if rec.vacancies < 1:
                raise ValidationError(_("Number of vacancies must be at least 1."))

    @api.constrains('salary_min', 'salary_max', 'experience_min', 'experience_max')
    def _check_ranges(self):
        for rec in self:
            if rec.salary_max and rec.salary_max < rec.salary_min:
                raise ValidationError(_("Maximum salary cannot be lower than minimum salary."))
            if rec.experience_max and rec.experience_max < rec.experience_min:
                raise ValidationError(_("Maximum experience cannot be lower than minimum experience."))

    @api.constrains('department_id')
    def _check_head_department(self):
        """A department head may only raise requests for the department they manage."""
        if self._is_head_only():
            for rec in self:
                if rec.department_id.sudo().manager_id.user_id.id != self.env.user.id:
                    raise ValidationError(
                        _("You can only raise requisitions for the department you head."))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_head_only(self):
        user = self.env.user
        return (
            not self.env.su
            and user.has_group(G_HEAD)
            and not user.has_group(G_HR)
            and not user.has_group(G_MGMT)
            and not user.has_group('base.group_system')
        )

    def _require(self, *xmlids):
        user = self.env.user
        if self.env.su or user.has_group('base.group_system'):
            return
        if not any(user.has_group(x) for x in xmlids):
            raise AccessError(_("You are not allowed to perform this action."))

    def _wf_write(self, vals):
        return self.with_context(wf_write=True).write(vals)

    def _notify_group(self, xmlid, summary):
        group = self.env.ref(xmlid).sudo()
        users = self.env['res.users']
        for fname in ('all_user_ids', 'user_ids', 'users'):
            if fname in group._fields:
                users = group[fname]
                break
        users = users.filtered(lambda u: u.active and not u.share)
        for rec in self:
            for user in users:
                rec.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id, summary=summary)

    def _notify_requester(self, body):
        for rec in self:
            partner = rec.requested_by.partner_id
            if partner:
                rec.message_subscribe(partner_ids=partner.ids)
            rec.message_post(body=body, partner_ids=partner.ids if partner else [])

    def _close_activities(self):
        self.sudo().activity_feedback(['mail.mail_activity_data_todo'])

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('manpower.requisition') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if self._is_head_only() and not self.env.context.get('wf_write'):
            if any(rec.state != 'draft' for rec in self):
                raise UserError(_("Only draft requisitions can be edited."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_("Only draft requisitions can be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        self._require(G_HEAD, G_HR)
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft requisitions can be submitted."))
            if rec.reason == 'replacement' and not rec.replaced_employee_id:
                raise UserError(_("Please name the employee being replaced."))
        self._wf_write({'state': 'submitted'})
        self._notify_group(G_HR, _("Review manpower requisition"))
        return True

    def action_send_for_approval(self):
        self._require(G_HR)
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_("Only submitted requisitions can be sent for approval."))
            missing = []
            if not rec.qualification:
                missing.append(_("Required Qualification"))
            if not rec.salary_max:
                missing.append(_("Salary Range"))
            if not rec.location:
                missing.append(_("Work Location"))
            if not rec.experience_max:
                missing.append(_("Experience"))
            if missing:
                raise UserError(_("Please complete before sending for approval: %s",
                                  ", ".join(missing)))
        self._close_activities()
        self._wf_write({'state': 'pending_approval'})
        self._notify_group(G_MGMT, _("Approve manpower requisition"))
        return True

    def action_approve(self):
        self._require(G_MGMT)
        for rec in self:
            if rec.state != 'pending_approval':
                raise UserError(_("Only requisitions pending approval can be approved."))
        self._close_activities()
        self._wf_write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        self._notify_requester(_("Your manpower requisition has been approved."))
        self._notify_group(G_HR, _("Open job for approved requisition"))
        return True

    def action_reject(self):
        """Open the reject wizard to collect a reason."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Reject Requisition"),
            'res_model': 'manpower.requisition.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_requisition_id': self.id},
        }

    def _do_reject(self, reason):
        for rec in self:
            if rec.state == 'submitted':
                rec._require(G_HR)
            elif rec.state == 'pending_approval':
                rec._require(G_MGMT)
            else:
                raise UserError(_("This requisition cannot be rejected in its current state."))
        self._close_activities()
        self._wf_write({
            'state': 'rejected',
            'rejection_reason': reason,
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        self._notify_requester(_("Your manpower requisition was rejected. Reason: %s", reason))

    def action_reset_draft(self):
        self._require(G_HEAD, G_HR)
        for rec in self:
            if rec.state != 'rejected':
                raise UserError(_("Only rejected requisitions can be reset to draft."))
        self._wf_write({'state': 'draft', 'rejection_reason': False})
        return True

    def action_open_job(self):
        """Hand off to Recruitment: update or create the Job Position."""
        self._require(G_HR)
        Job = self.env['hr.job'].sudo()
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_("Only approved requisitions can be opened for recruitment."))
            job = rec.job_id.sudo()
            if not job:
                job = Job.create({
                    'name': rec.position_name,
                    'department_id': rec.department_id.id,
                    'company_id': rec.company_id.id,
                    'no_of_recruitment': rec.vacancies,
                })
                rec._wf_write({'job_id': job.id})
            # Target = vacancies of all requisitions already opened for this job + this one
            opened = self.sudo().search([('job_id', '=', job.id), ('state', '=', 'done')])
            job.no_of_recruitment = sum(opened.mapped('vacancies')) + rec.vacancies
            if 'description' in job._fields and not job.description:
                job.description = rec._job_description()
            rec._wf_write({'state': 'done'})
            rec.message_post(body=_(
                "Job position <b>%(job)s</b> opened for %(n)s vacancy(ies).",
                job=job.name, n=rec.vacancies))
        self._close_activities()
        return True

    def _job_description(self):
        self.ensure_one()
        parts = []
        if self.qualification:
            parts.append(_("Qualification: %s", self.qualification))
        if self.experience_max:
            parts.append(_("Experience: %(a)s - %(b)s years",
                           a=self.experience_min, b=self.experience_max))
        if self.location:
            parts.append(_("Location: %s", self.location))
        return "\n".join(parts)
