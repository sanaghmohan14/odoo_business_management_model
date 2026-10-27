from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class BusinessConsultingDeliverable(models.Model):
    _name = 'business.consulting.deliverable'
    _description = 'Consulting Deliverable'
    _order = 'department_id, sequence, name'

    name = fields.Char(string='Deliverable', required=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True,
                                    ondelete='restrict', index=True)
    deliverable_type = fields.Selection([
        ('assessment', 'Assessment'),
        ('design', 'Design'),
        ('implementation', 'Implementation'),
        ('training', 'Training'),
        ('report', 'Report'),
        ('other', 'Other'),
    ], string='Type', default='other', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class BusinessConsultingDeliverableProject(models.Model):
    _name = 'business.consulting.deliverable.project'
    _description = 'Project Consulting Deliverable'
    _order = 'department_id, sequence, name'

    name = fields.Char(string='Deliverable', required=True)
    project_id = fields.Many2one('business.project', string='Business Project', required=True,
                                 ondelete='cascade', index=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True,
                                    ondelete='restrict', index=True)
    deliverable_type = fields.Selection([
        ('assessment', 'Assessment'), ('design', 'Design'),
        ('implementation', 'Implementation'), ('training', 'Training'),
        ('report', 'Report'), ('other', 'Other'),
    ], string='Type', default='other', required=True)
    description = fields.Text(string='Description')
    responsible_user_id = fields.Many2one('res.users', string='Responsible Employee')
    due_date = fields.Date(string='Due Date')
    state = fields.Selection([
        ('planned', 'Planned'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'), ('cancelled', 'Cancelled'),
    ], default='planned', required=True, index=True)
    sequence = fields.Integer(default=10)


class BusinessProjectSOP(models.Model):
    _name = 'business.project.sop'
    _description = 'Project Standard Operating Procedure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'department_id, name'

    name = fields.Char(string='SOP Title', required=True, tracking=True)
    project_id = fields.Many2one('business.project', string='Business Project',
                                 required=True, ondelete='cascade', index=True, tracking=True,
                                 domain="[('is_sop_required', '=', True)]")
    stage_id = fields.Many2one('business.project.stage', string='Associated Stage',
                               ondelete='set null', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True,
                                    ondelete='restrict', index=True, tracking=True)
    sop_type = fields.Selection([
        ('procedure', 'Standard Operating Procedure (SOP)'),
        ('policy', 'Company Policy'),
        ('workflow', 'Process Workflow'),
        ('jd', 'Job Description / Role Profile'),
        ('kpi_standard', 'KRA / KPI Benchmark'),
    ], string='SOP Type', required=True, default='procedure', tracking=True)
    objective = fields.Text(string='Objective / Purpose')
    scope = fields.Text(string='Applicable Scope')
    owner_id = fields.Many2one('res.users', string='Lead Consultant / Author', required=True,
                               default=lambda self: self.env.user, tracking=True)
    version = fields.Char(string='Version', default='1.0')

    # Status tracking (Steps 27 - 32)
    state = fields.Selection([
        ('draft', 'Draft / Discussion'),
        ('checklist_prep', 'Checklist Development'),
        ('rollout', 'Rollout to Client'),
        ('verification', 'Consultant Verification'),
        ('active', 'Compliant & Active'),
        ('audit', 'Under Monthly Audit'),
        ('obsolete', 'Obsolete'),
    ], default='draft', required=True, index=True, tracking=True)

    # SOP Discussion Details (Step 28)
    discussion_date = fields.Date(string='Discussion Date', default=fields.Date.context_today)
    discussion_attendees = fields.Char(string='Discussion Attendees')
    discussion_notes = fields.Text(string='Discussion Minutes & Agreed Scope')

    # Client Implementation Coordinator (Step 29)
    coordinator_id = fields.Many2one('res.partner', string='Client Implementation Coordinator',
                                     tracking=True)
    coordinator_designation_date = fields.Date(string='Coordinator Designated Date')
    rollout_date = fields.Date(string='Client Rollout Date')
    rollout_notes = fields.Text(string='Rollout & Implementation Instructions')

    # Checklists
    checklist_ids = fields.One2many('business.project.sop.checklist', 'sop_id',
                                    string='All Checklists', copy=True)
    daily_checklist_ids = fields.One2many('business.project.sop.checklist', 'sop_id',
                                         string='Daily Checklists',
                                         domain=[('frequency', '=', 'daily')])
    weekly_checklist_ids = fields.One2many('business.project.sop.checklist', 'sop_id',
                                          string='Weekly Checklists',
                                          domain=[('frequency', '=', 'weekly')])
    monthly_checklist_ids = fields.One2many('business.project.sop.checklist', 'sop_id',
                                           string='Monthly Checklists',
                                           domain=[('frequency', '=', 'monthly')])

    # Compliance & Gaps
    compliance_ids = fields.One2many('business.project.sop.compliance', 'sop_id',
                                     string='Compliance Checks', copy=False)
    document_ids = fields.One2many('business.project.sop.document', 'sop_id',
                                   string='Formats and Templates', copy=True)
    gap_ids = fields.One2many('business.project.gap', 'sop_id',
                              string='Identified Gaps & Corrective Actions')

    # Computed Counts and Rates
    daily_count = fields.Integer(compute='_compute_counts', string='Daily Items')
    weekly_count = fields.Integer(compute='_compute_counts', string='Weekly Items')
    monthly_count = fields.Integer(compute='_compute_counts', string='Monthly Items')
    checklist_count = fields.Integer(compute='_compute_counts', string='Total Items')
    compliant_count = fields.Integer(compute='_compute_counts', string='Compliant Items')
    non_compliant_count = fields.Integer(compute='_compute_counts', string='Non-Compliant Items')
    gap_count = fields.Integer(compute='_compute_counts', string='Open Gaps')
    compliance_rate = fields.Float(compute='_compute_compliance_rate', string='Compliance Score (%)', store=True)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            if not self.department_id and self.project_id.department_id:
                self.department_id = self.project_id.department_id
            if not self.stage_id:
                self.stage_id = self.project_id.stage_id
            if not self.coordinator_id and self.project_id.client_implementation_coordinator_id:
                self.coordinator_id = self.project_id.client_implementation_coordinator_id

    @api.constrains('project_id')
    def _check_project_sop_requirement(self):
        for sop in self:
            if sop.project_id and not sop.project_id.is_sop_required:
                dept_name = sop.project_id.department_id.name or 'Unknown'
                raise ValidationError(
                    f'SOP is only applicable for BenAc projects. '
                    f'Project "{sop.project_id.name}" belongs to department "{dept_name}".'
                )

    @api.depends('checklist_ids', 'checklist_ids.frequency', 'checklist_ids.status', 'gap_ids', 'gap_ids.state')
    def _compute_counts(self):
        for sop in self:
            items = sop.checklist_ids
            sop.daily_count = len(items.filtered(lambda c: c.frequency == 'daily'))
            sop.weekly_count = len(items.filtered(lambda c: c.frequency == 'weekly'))
            sop.monthly_count = len(items.filtered(lambda c: c.frequency == 'monthly'))
            sop.checklist_count = len(items)
            sop.compliant_count = len(items.filtered(lambda c: c.status == 'compliant'))
            sop.non_compliant_count = len(items.filtered(lambda c: c.status == 'non_compliant'))
            sop.gap_count = len(sop.gap_ids.filtered(lambda g: g.state in ('open', 'in_progress')))

    @api.depends('checklist_ids.status')
    def _compute_compliance_rate(self):
        for sop in self:
            evaluable = sop.checklist_ids.filtered(lambda c: c.status in ('compliant', 'partially_compliant', 'non_compliant'))
            if evaluable:
                score = sum(
                    100.0 if c.status == 'compliant' else 50.0 if c.status == 'partially_compliant' else 0.0
                    for c in evaluable
                )
                sop.compliance_rate = round(score / len(evaluable), 1)
            else:
                sop.compliance_rate = 0.0

    def action_set_checklist_prep(self):
        self.write({'state': 'checklist_prep'})

    def action_set_rollout(self):
        for rec in self:
            if not rec.checklist_ids:
                raise UserError('Please create at least one checklist item before rolling out the SOP to client.')
            rec.write({
                'state': 'rollout',
                'rollout_date': rec.rollout_date or fields.Date.today(),
            })

    def action_set_verification(self):
        self.write({'state': 'verification'})

    def action_set_active(self):
        self.write({'state': 'active'})

    def action_set_audit(self):
        self.write({'state': 'audit'})

    def action_quick_verify_all(self):
        """1-click verification of all pending checklist items as compliant."""
        for sop in self:
            pending_items = sop.checklist_ids.filtered(lambda c: c.status == 'pending')
            pending_items.write({
                'status': 'compliant',
                'last_verified_date': fields.Date.today(),
                'verified_by_id': self.env.user.id,
                'verification_notes': 'Verified compliant during consultant review.',
            })
            if sop.state in ('rollout', 'verification'):
                sop.state = 'active'
        return True

    def action_generate_standard_checklists(self):
        """Automatically populates standard Daily, Weekly, and Monthly checklists for this SOP."""
        self.ensure_one()
        dept_name = self.department_id.name or 'Department'
        sop_title = self.name or 'Process'

        templates = [
            # DAILY CHECKLISTS
            {
                'name': f'Daily Attendance & Operational Readiness ({dept_name})',
                'frequency': 'daily',
                'sequence': 10,
                'is_required': True,
                'verification_method': 'document',
                'instructions': 'Ensure all team members log in on time, confirm daily workstation readiness and initial task allocation.',
            },
            {
                'name': f'Execution of {sop_title} Daily Tasks',
                'frequency': 'daily',
                'sequence': 20,
                'is_required': True,
                'verification_method': 'system',
                'instructions': 'Execute operational duties in compliance with the defined steps and log activity in the prescribed format.',
            },
            {
                'name': 'Daily Log / Register Maintenance & Handover',
                'frequency': 'daily',
                'sequence': 30,
                'is_required': True,
                'verification_method': 'document',
                'instructions': 'Fill out the daily operational sheet and report any variances to the Client Implementation Coordinator.',
            },
            # WEEKLY CHECKLISTS
            {
                'name': f'Weekly Pending Task & Variance Review ({dept_name})',
                'frequency': 'weekly',
                'sequence': 10,
                'is_required': True,
                'verification_method': 'document',
                'instructions': 'Review all unresolved items, bottlenecks, and incomplete tasks from the current week.',
            },
            {
                'name': 'Weekly Compliance & Format Utilization Check',
                'frequency': 'weekly',
                'sequence': 20,
                'is_required': True,
                'verification_method': 'system',
                'instructions': 'Client Implementation Coordinator verifies that employees used the standard formats throughout the week.',
            },
            {
                'name': 'Weekly Reporting to Assigned Consultant',
                'frequency': 'weekly',
                'sequence': 30,
                'is_required': True,
                'verification_method': 'interview',
                'instructions': 'Submit weekly summary report and coordinate review meeting with BenAc consulting team.',
            },
            # MONTHLY CHECKLISTS
            {
                'name': f'Monthly SOP Compliance & Standards Audit ({dept_name})',
                'frequency': 'monthly',
                'sequence': 10,
                'is_required': True,
                'verification_method': 'document',
                'instructions': 'Perform comprehensive audit against Standards, Sub-standards, and Reference Documents.',
            },
            {
                'name': 'Monthly KRA Achievement & KPI Reconciliation',
                'frequency': 'monthly',
                'sequence': 20,
                'is_required': True,
                'verification_method': 'system',
                'instructions': 'Verify monthly targets against actual results achieved by department employees.',
            },
            {
                'name': 'Monthly Corrective Actions & Gap Resolution Review',
                'frequency': 'monthly',
                'sequence': 30,
                'is_required': True,
                'verification_method': 'interview',
                'instructions': 'Inspect all open gaps, ensure corrective actions are completed, and update management review log.',
            },
        ]

        # Avoid duplicates
        existing_names = set(self.checklist_ids.mapped('name'))
        created_count = 0
        for tpl in templates:
            if tpl['name'] not in existing_names:
                self.env['business.project.sop.checklist'].create({
                    'sop_id': self.id,
                    'name': tpl['name'],
                    'frequency': tpl['frequency'],
                    'sequence': tpl['sequence'],
                    'is_required': tpl['is_required'],
                    'verification_method': tpl['verification_method'],
                    'instructions': tpl['instructions'],
                    'responsible_user_id': self.owner_id.id,
                })
                created_count += 1

        if self.state == 'draft':
            self.state = 'checklist_prep'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Checklists Generated',
                'message': f'Generated {created_count} standard checklists (Daily, Weekly, Monthly) for {sop_title}.',
                'type': 'success',
                'sticky': False,
            }
        }


class BusinessProjectSOPChecklist(models.Model):
    _name = 'business.project.sop.checklist'
    _description = 'SOP Checklist Item'
    _order = 'frequency, sequence, name'

    name = fields.Char(string='Checklist Item / Task', required=True)
    sop_id = fields.Many2one('business.project.sop', string='SOP', required=True,
                             ondelete='cascade', index=True)
    project_id = fields.Many2one('business.project', string='Business Project',
                                 related='sop_id.project_id', store=True, index=True)
    department_id = fields.Many2one('hr.department', string='Department',
                                    related='sop_id.department_id', store=True, index=True)
    stage_id = fields.Many2one('business.project.stage', string='Stage',
                               related='sop_id.stage_id', store=True)

    frequency = fields.Selection([
        ('daily', 'Daily Checklist'),
        ('weekly', 'Weekly Checklist'),
        ('monthly', 'Monthly Checklist'),
    ], required=True, default='daily', index=True)

    sequence = fields.Integer(default=10)
    responsible_user_id = fields.Many2one('res.users', string='Responsible Person')
    responsible_role = fields.Char(string='Responsible Role / Designation')
    is_required = fields.Boolean(string='Mandatory', default=True)
    instructions = fields.Text(string='Execution Instructions & Standards')

    verification_method = fields.Selection([
        ('document', 'Document / Format Review'),
        ('system', 'Odoo System Verification'),
        ('physical', 'Physical Process Observation'),
        ('interview', 'Employee / Coordinator Interview'),
    ], string='Verification Method', default='document', required=True)

    status = fields.Selection([
        ('pending', 'Pending Verification'),
        ('compliant', 'Compliant'),
        ('partially_compliant', 'Partially Compliant'),
        ('non_compliant', 'Non-Compliant'),
        ('not_applicable', 'Not Applicable'),
    ], string='Verification Status', default='pending', required=True, index=True)

    last_verified_date = fields.Date(string='Last Verified Date')
    verified_by_id = fields.Many2one('res.users', string='Verified by (Consultant)')
    verification_notes = fields.Text(string='Verification Findings')

    gap_ids = fields.One2many('business.project.gap', 'checklist_id',
                              string='Identified Gaps & Actions')
    gap_count = fields.Integer(string='Gaps', compute='_compute_gap_count')
    active = fields.Boolean(default=True)

    @api.depends('gap_ids')
    def _compute_gap_count(self):
        for rec in self:
            rec.gap_count = len(rec.gap_ids)

    def action_mark_compliant(self):
        for rec in self:
            rec.write({
                'status': 'compliant',
                'last_verified_date': fields.Date.today(),
                'verified_by_id': self.env.user.id,
                'verification_notes': (rec.verification_notes or '') + f'\nVerified compliant on {fields.Date.today()} by {self.env.user.name}.',
            })
        return True

    def action_mark_non_compliant(self):
        """Marks non-compliant and creates a Gap & Corrective Action item."""
        for rec in self:
            rec.write({
                'status': 'non_compliant',
                'last_verified_date': fields.Date.today(),
                'verified_by_id': self.env.user.id,
            })
            gap = self.env['business.project.gap'].create({
                'name': f'Non-Compliance: {rec.name}',
                'project_id': rec.project_id.id,
                'sop_id': rec.sop_id.id,
                'checklist_id': rec.id,
                'department_id': rec.department_id.id,
                'employee_id': rec.responsible_user_id.id if rec.responsible_user_id else self.env.user.id,
                'severity': 'medium',
                'description': f'Failed SOP checklist check for: {rec.name}.\nInstructions: {rec.instructions or ""}',
                'corrective_action': 'Implement required corrective action and enforce daily/weekly compliance.',
                'due_date': fields.Date.today(),
                'state': 'open',
            })
            return {
                'type': 'ir.actions.act_window',
                'name': 'Corrective Action Gap',
                'res_model': 'business.project.gap',
                'res_id': gap.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return True

    def action_reset_pending(self):
        self.write({
            'status': 'pending',
            'last_verified_date': False,
            'verified_by_id': False,
        })
        return True


class BusinessProjectSOPDocument(models.Model):
    _name = 'business.project.sop.document'
    _description = 'SOP Format or Required Document'
    _order = 'sop_id, name'

    name = fields.Char(string='Format / Document Name', required=True)
    sop_id = fields.Many2one('business.project.sop', string='SOP', required=True,
                             ondelete='cascade', index=True)
    project_id = fields.Many2one('business.project', string='Business Project',
                                 related='sop_id.project_id', store=True)
    document_type = fields.Selection([
        ('format', 'Prescribed Format / Template'),
        ('document', 'Reference Policy / Procedure'),
        ('evidence', 'Compliance Evidence'),
        ('agenda', 'Meeting Agenda / MOM Template'),
    ], string='Type', required=True, default='format')
    description = fields.Text(string='Usage Instructions')
    attachment = fields.Binary(string='File / Template Attachment', attachment=True)
    attachment_filename = fields.Char(string='Filename')
    required = fields.Boolean(string='Mandatory for Client', default=True)


class BusinessProjectSOPCompliance(models.Model):
    _name = 'business.project.sop.compliance'
    _description = 'SOP Compliance Check'
    _order = 'check_date desc, id desc'

    sop_id = fields.Many2one('business.project.sop', string='SOP', required=True,
                             ondelete='cascade', index=True)
    checklist_id = fields.Many2one('business.project.sop.checklist', string='Checklist Item',
                                   required=True, ondelete='restrict')
    project_id = fields.Many2one(related='sop_id.project_id', store=True,
                                 string='Business Project', readonly=True, index=True)
    check_date = fields.Date(string='Check Date', required=True,
                             default=fields.Date.context_today, index=True)
    frequency = fields.Selection(related='checklist_id.frequency', store=True,
                                 readonly=True)
    employee_id = fields.Many2one('res.users', string='Checked Employee / Assignee', required=True)
    status = fields.Selection([
        ('compliant', 'Compliant'),
        ('partially_compliant', 'Partially Compliant'),
        ('non_compliant', 'Non-compliant'),
        ('not_applicable', 'Not Applicable'),
    ], string='Compliance', required=True, default='compliant', index=True)
    evidence = fields.Text(string='Evidence / Notes')
    gap_ids = fields.One2many('business.project.gap', 'compliance_id', string='Gaps')


class BusinessProjectMonitoring(models.Model):
    _name = 'business.project.monitoring'
    _description = 'Implementation Coordinator Monitoring'
    _order = 'monitoring_date desc, id desc'

    name = fields.Char(string='Monitoring Note', required=True)
    project_id = fields.Many2one('business.project', string='Business Project', required=True,
                                 ondelete='cascade', index=True)
    coordinator_id = fields.Many2one('res.partner', string='Client Coordinator',
                                     related='project_id.client_implementation_coordinator_id',
                                     store=True, readonly=True)
    employee_id = fields.Many2one('res.users', string='Employee Monitored', required=True)
    monitoring_date = fields.Date(string='Date', required=True,
                                  default=fields.Date.context_today, index=True)
    frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], default='weekly', required=True)
    status = fields.Selection([
        ('planned', 'Planned'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], default='planned', required=True)
    findings = fields.Text(string='Findings')
    client_report = fields.Text(string='Report to Client')
    gap_ids = fields.One2many('business.project.gap', 'monitoring_id', string='Gaps')


class BusinessProjectGap(models.Model):
    _name = 'business.project.gap'
    _description = 'Project Gap and Corrective Action'
    _order = 'due_date, id desc'

    name = fields.Char(string='Gap Title / Defect', required=True)
    project_id = fields.Many2one('business.project', string='Business Project', required=True,
                                 ondelete='cascade', index=True)
    sop_id = fields.Many2one('business.project.sop', string='SOP', ondelete='cascade', index=True)
    checklist_id = fields.Many2one('business.project.sop.checklist', string='Checklist Item',
                                   ondelete='set null', index=True)
    monitoring_id = fields.Many2one('business.project.monitoring', string='Monitoring')
    compliance_id = fields.Many2one('business.project.sop.compliance', string='Compliance Check')
    department_id = fields.Many2one('hr.department', string='Department')
    employee_id = fields.Many2one('res.users', string='Accountable Person')
    severity = fields.Selection([
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical'),
    ], default='medium', required=True)
    description = fields.Text(string='Gap Details / Root Cause')
    corrective_action = fields.Text(string='Corrective Action Plan')
    due_date = fields.Date(string='Target Resolution Date')
    state = fields.Selection([
        ('open', 'Open'), ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'), ('closed', 'Closed'),
    ], default='open', required=True, index=True)

    @api.constrains('monitoring_id', 'compliance_id', 'checklist_id', 'sop_id', 'project_id')
    def _check_source(self):
        for gap in self:
            if not gap.monitoring_id and not gap.compliance_id and not gap.checklist_id and not gap.sop_id and not gap.project_id:
                raise ValidationError('A gap must be linked to a project, SOP, checklist, or monitoring event.')

    def action_resolve(self):
        self.write({'state': 'resolved'})

    def action_close(self):
        self.write({'state': 'closed'})
