from odoo import models, fields, api
from odoo.exceptions import UserError


class BusinessProject(models.Model):
    _name = 'business.project'
    _description = 'Business Consulting Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # BASIC INFORMATION

    name = fields.Char(
        string='Project Name',
        required=True,
        tracking=True
    )

    reference = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'business.project'
        ) or 'New'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    company_id = fields.Many2one('res.company',
                                 string="Company",
                                 default=lambda self: self.env.company,
                                 readonly=True)


    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Very High'),
    ], string='Priority', default='0', index=True, tracking=True)

    # WORKFLOW

    stage_id = fields.Many2one(
        'business.project.stage',
        string='Stage',
        required=True,
        default=lambda self: self._default_stage(),
        tracking=True,
        ondelete='restrict',
        group_expand='_read_group_stage_ids'
    )

    phase = fields.Selection(
        related='stage_id.phase',
        string='Phase',
        store=True,
        readonly=True
    )

    previous_stage_id = fields.Many2one(
        'business.project.stage',
        string='Previous Stage',
        readonly=True
    )



    hold_return_stage_id = fields.Many2one(
        'business.project.stage',
        string='Resume Stage',
        readonly=True
    )
    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=False
    )
    stage_requires_approval = fields.Boolean(
        related='stage_id.requires_approval',
        string='Stage Requires Approval',
        readonly=True
    )
    has_pending_approval = fields.Boolean(
        string='Has Pending Approval',
        compute='_compute_approval_state'
    )
    is_stage_approved = fields.Boolean(
        string='Is Stage Approved',
        compute='_compute_approval_state'
    )
    is_current_user_ceo = fields.Boolean(
        string='Is Current User CEO',
        compute='_compute_is_current_user_ceo'
    )

    # CUSTOMER

    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
        ondelete='restrict'
    )

    responsible_user_id = fields.Many2one(
        'res.users',
        string='Project Responsible',
        tracking=True
    )

    team_member_ids = fields.One2many(
        'business.project.team',
        'project_id',
        string='Team Members'
    )
    #time sheets
    timesheet_ids = fields.One2many(
        'account.analytic.line',
        'business_project_id',
        string='Timesheets'
    )

    # CRM / SALES


    opportunity_id = fields.Many2one(
        'crm.lead',
        string='Opportunity',
        tracking=True,
        ondelete='set null',
        index=True
    )



    lead_id = fields.Many2one(
        'crm.lead',
        string='CRM Lead',
        ondelete='set null'
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        tracking=True,
        ondelete='set null'
    )

    sales_person_id = fields.Many2one(
        'res.users',
        string='Sales Person',
        # tracking=True,
        # ondelete='set null'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        ondelete='set null',
        index=True
    )
    #communication steps
    communication_channel = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('teams', 'Microsoft Teams'),
        ('other', 'Other'),
    ], string='Communication Channel')

    communication_group_name = fields.Char(
        string='Group / Channel Name'
    )

    communication_created = fields.Boolean(
        string='Communication Setup Completed',
        default=False
    )

    communication_notes = fields.Text(
        string='Communication Notes'
    )


    # PROJECT


    project_id = fields.Many2one(
        'project.project',
        string='Project Allocate',
        tracking=True,
        ondelete='set null'
    )

    project_manager_id = fields.Many2one(
        'res.users',
        string='Project Manager',
        tracking=True,
        ondelete='set null'
    )

    # DATES


    start_date = fields.Date(
        string='Start Date',
        tracking=True
    )

    expected_end_date = fields.Date(
        string='Expected End Date',
        tracking=True
    )

    actual_end_date = fields.Date(
        string='Actual End Date',
        tracking=True
    )

    #client kickoff

    kickoff_contact_date = fields.Datetime(
        string='Initial Client Contact'
    )

    kickoff_date = fields.Datetime(
        string='Kick-off Date'
    )

    kickoff_completed = fields.Boolean(
        string='Kick-off Completed',
        default=False
    )

    kickoff_notes = fields.Text(
        string='Kick-off Notes'
    )



    # DESCRIPTION


    description = fields.Text(
        string='Description'
    )

    notes = fields.Html(
        string='Internal Notes'
    )

    #kra connection
    kra_ids = fields.One2many(
        'business.project.kra',
        'project_id',
        string='KRAs'
    )

    #activity

    activity_plan_ids = fields.One2many(
        'business.project.activity',
        'project_id',
        string='Activity Plan'
    )

    #data collection

    data_collection_ids = fields.One2many(
        'business.project.data.collection',
        'project_id',
        string='Data Collection'
    )

    consulting_deliverable_ids = fields.One2many(
        'business.consulting.deliverable.project', 'project_id',
        string='Consulting Deliverables'
    )

    sop_ids = fields.One2many(
        'business.project.sop', 'project_id', string='SOPs'
    )

    sop_checklist_ids = fields.One2many(
        'business.project.sop.checklist', 'project_id', string='All Checklists'
    )

    sop_daily_checklist_ids = fields.One2many(
        'business.project.sop.checklist', 'project_id', string='Daily Checklists',
        domain=[('frequency', '=', 'daily')]
    )

    sop_weekly_checklist_ids = fields.One2many(
        'business.project.sop.checklist', 'project_id', string='Weekly Checklists',
        domain=[('frequency', '=', 'weekly')]
    )

    sop_monthly_checklist_ids = fields.One2many(
        'business.project.sop.checklist', 'project_id', string='Monthly Checklists',
        domain=[('frequency', '=', 'monthly')]
    )

    sop_count = fields.Integer(string='Total SOPs', compute='_compute_sop_metrics')
    sop_daily_count = fields.Integer(string='Daily Checklist Count', compute='_compute_sop_metrics')
    sop_weekly_count = fields.Integer(string='Weekly Checklist Count', compute='_compute_sop_metrics')
    sop_monthly_count = fields.Integer(string='Monthly Checklist Count', compute='_compute_sop_metrics')
    sop_total_checklists = fields.Integer(string='Total Checklists', compute='_compute_sop_metrics')
    sop_compliant_count = fields.Integer(string='Compliant Checklists', compute='_compute_sop_metrics')
    sop_compliance_rate = fields.Float(string='SOP Compliance Rate (%)', compute='_compute_sop_metrics')
    sop_open_gaps_count = fields.Integer(string='Open SOP Gaps', compute='_compute_sop_metrics')

    monitoring_ids = fields.One2many(
        'business.project.monitoring', 'project_id', string='Implementation Monitoring'
    )

    gap_ids = fields.One2many(
        'business.project.gap', 'project_id', string='Gaps and Corrective Actions'
    )

    client_implementation_coordinator_id = fields.Many2one(
        'res.partner', string='Client Implementation Coordinator',
        tracking=True, ondelete='set null'
    )



    task_ids = fields.One2many(
        'project.task',
        'business_project_id',
        string='Sub Tasks'
    )




    # COMPUTED INFORMATION


    stage_sequence = fields.Integer(
        related='stage_id.sequence',
        string='Stage Sequence',
        store=True
    )

    is_on_hold = fields.Boolean(
        string='On Hold',
        compute='_compute_workflow_status'
    )

    is_cancelled = fields.Boolean(
        string='Cancelled',
        compute='_compute_workflow_status'
    )

    is_completed = fields.Boolean(
        string='Completed',
        compute='_compute_workflow_status'
    )

    is_team_allocation_stage = fields.Boolean(
        string='Team Allocation Stage',
        compute='_compute_workflow_status'
    )

    is_kickoff_stage = fields.Boolean(
        string='Kick-off Stage',
        compute='_compute_workflow_status'
    )

    is_communication_stage = fields.Boolean(
        string='Communication Stage',
        compute='_compute_workflow_status'
    )

    is_client_onboarding_stage = fields.Boolean(
        string='Client Onboarding Stage',
        compute='_compute_workflow_status'
    )

    is_sop_development_stage = fields.Boolean(
        string='SOP Development Stage',
        compute='_compute_workflow_status'
    )

    is_sop_discussion_stage = fields.Boolean(
        string='SOP Discussion Stage',
        compute='_compute_workflow_status'
    )

    is_sop_rollout_stage = fields.Boolean(
        string='SOP Rollout Stage',
        compute='_compute_workflow_status'
    )

    is_consultant_verification_stage = fields.Boolean(
        string='Consultant Verification Stage',
        compute='_compute_workflow_status'
    )

    is_monthly_audit_stage = fields.Boolean(
        string='Monthly Audit Stage',
        compute='_compute_workflow_status'
    )

    is_sop_active_stage = fields.Boolean(
        string='SOP Active Stage',
        compute='_compute_workflow_status'
    )

    approval_ids = fields.One2many(
        'business.project.approval',
        'project_id',
        string='Approvals'
    )

    # qualification_status = fields.Selection([
    #     ('not_checked', 'Not Checked'),
    #     ('qualified', 'Qualified'),
    #     ('not_qualified', 'Not Qualified'),
    # ], string='Qualification Status', default='not_checked', tracking=True)
    #
    # qualification_notes = fields.Text(
    #     string='Qualification Notes'
    # )

    meeting_count = fields.Integer(
        string='Meetings',
        compute='_compute_meeting_count'
    )

    @api.depends()
    def _compute_meeting_count(self):
        Meeting = self.env['calendar.event']
        for record in self:
            record.meeting_count = Meeting.search_count([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id),
            ])


    def action_view_meetings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Meetings',
            'res_model': 'calendar.event',
            'view_mode': 'calendar,list,form',
            'domain': [
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
            ],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_name': self.name,
            },
        }

    def action_view_activity_calendar(self):
        self.ensure_one()
        calendar_view = self.env.ref(
            'Benjali_management.business_project_activity_calendar'
        )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Project Activities',
            'res_model': 'business.project.activity',
            'view_mode': 'calendar,list,form',
            'views': [
                (calendar_view.id, 'calendar'),
                (False, 'list'),
                (False, 'form'),
            ],
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
            },
        }



    @api.model
    def _default_stage(self):
        stage = self.env.ref(
            'Benjali_management.stage_client_onboarding',
            raise_if_not_found=False
        )
        if not stage:
            stage = self.env['business.project.stage'].search([
                ('phase', '=', 'onboarding')
            ], order='sequence asc', limit=1)
        return stage.id if stage else False


    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return self.env['business.project.stage'].search(
            [('active', '=', True), ('name', 'not ilike', 'proposal')],
            order='sequence, id'
        )

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------


    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('reference', 'New') == 'New':
    #             vals['reference'] = (
    #                     self.env['ir.sequence'].next_by_code(
    #                         'business.project'
    #                     ) or 'New'
    #             )
    #
    #     return super().create(vals_list)

    def _assign_stage_responsible_user(self):
        for record in self:
            responsible_user = record.stage_id.responsible_user_id

            if not responsible_user and record.stage_id.name == 'Team Allocation':
                responsible_user = record.sales_person_id

            if responsible_user:
                record.responsible_user_id = responsible_user.id


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference'):
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'business.project'
                ) or 'New'

            if not vals.get('stage_id'):
                vals['stage_id'] = self._default_stage()

        projects = super().create(vals_list)

        for project in projects:
            project._assign_stage_responsible_user()
            project.message_post(
                body=f'Business Project {project.name} created.'
            )

        return projects




    # WORKFLOW STATUS


    @api.depends('stage_id')
    def _compute_workflow_status(self):

        for record in self:

            stage_name = (record.stage_id.name or '').strip().lower()

            record.is_on_hold = stage_name == 'on hold'
            record.is_cancelled = stage_name == 'cancelled'
            record.is_completed = stage_name == 'completed'
            record.is_client_onboarding_stage = 'client onboarding' in stage_name
            record.is_team_allocation_stage = 'team allocation' in stage_name or 'team designation' in stage_name
            record.is_kickoff_stage = (
                'kick-off' in stage_name or 'kickoff' in stage_name
            )
            record.is_communication_stage = (
                'communication' in stage_name
            )
            record.is_sop_development_stage = 'deliverables & sop' in stage_name or 'sop development' in stage_name
            record.is_sop_discussion_stage = 'sop discussion' in stage_name
            record.is_sop_rollout_stage = 'rollout' in stage_name
            record.is_consultant_verification_stage = 'consultant verification' in stage_name
            record.is_monthly_audit_stage = 'monthly audit' in stage_name or 'audit' in stage_name
            record.is_sop_active_stage = any([
                record.is_sop_development_stage,
                record.is_sop_discussion_stage,
                record.is_sop_rollout_stage,
                record.is_consultant_verification_stage,
                record.is_monthly_audit_stage,
                record.stage_id.phase in ('execution', 'governance')
            ])

    @api.depends('sop_ids', 'sop_ids.checklist_ids', 'sop_ids.checklist_ids.status', 'gap_ids', 'gap_ids.state')
    def _compute_sop_metrics(self):
        for project in self:
            sops = project.sop_ids
            checklists = project.sop_checklist_ids
            daily = checklists.filtered(lambda c: c.frequency == 'daily')
            weekly = checklists.filtered(lambda c: c.frequency == 'weekly')
            monthly = checklists.filtered(lambda c: c.frequency == 'monthly')
            compliant = checklists.filtered(lambda c: c.status == 'compliant')
            open_gaps = project.gap_ids.filtered(lambda g: g.state in ('open', 'in_progress'))

            project.sop_count = len(sops)
            project.sop_daily_count = len(daily)
            project.sop_weekly_count = len(weekly)
            project.sop_monthly_count = len(monthly)
            project.sop_total_checklists = len(checklists)
            project.sop_compliant_count = len(compliant)
            project.sop_open_gaps_count = len(open_gaps)

            evaluable = checklists.filtered(lambda c: c.status in ('compliant', 'partially_compliant', 'non_compliant'))
            if evaluable:
                score = sum(
                    100.0 if c.status == 'compliant' else 50.0 if c.status == 'partially_compliant' else 0.0
                    for c in evaluable
                )
                project.sop_compliance_rate = round(score / len(evaluable), 1)
            else:
                project.sop_compliance_rate = 0.0

    def action_generate_project_sop_checklists(self):
        for project in self:
            if not project.sop_ids:
                dept = project.department_id or self.env['hr.department'].search([], limit=1)
                sop = self.env['business.project.sop'].create({
                    'name': f'{dept.name or "Operations"} Standard Operating Procedure',
                    'project_id': project.id,
                    'department_id': dept.id,
                    'stage_id': project.stage_id.id,
                    'owner_id': project.responsible_user_id.id or self.env.user.id,
                    'coordinator_id': project.client_implementation_coordinator_id.id if project.client_implementation_coordinator_id else False,
                })
                sop.action_generate_standard_checklists()
            else:
                for sop in project.sop_ids:
                    sop.action_generate_standard_checklists()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'SOP Checklists Generated',
                'message': 'Standard Daily, Weekly, and Monthly checklists generated for project SOPs.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_mark_all_sop_compliant(self):
        for project in self:
            pending = project.sop_checklist_ids.filtered(lambda c: c.status == 'pending')
            pending.write({
                'status': 'compliant',
                'last_verified_date': fields.Date.today(),
                'verified_by_id': self.env.user.id,
                'verification_notes': 'Verified compliant during project review.',
            })
            for sop in project.sop_ids:
                if sop.state in ('rollout', 'verification'):
                    sop.state = 'active'
        return True

    def _compute_is_current_user_ceo(self):
        is_ceo = self.env.user.has_group('Benjali_management.group_ceo') or self.env.is_admin()
        for record in self:
            record.is_current_user_ceo = is_ceo

    @api.depends('stage_id', 'approval_ids.state', 'approval_ids.approval_type')
    def _compute_approval_state(self):
        for record in self:
            stage = record.stage_id
            requires = stage.requires_approval or (
                stage.name and 'management review' in stage.name.lower()
            )
            if not requires:
                record.has_pending_approval = False
                record.is_stage_approved = False
                continue

            approval_type = stage.approval_type or 'management_review'
            pending = record.approval_ids.filtered(
                lambda a: a.approval_type == approval_type and a.state == 'pending'
            )
            approved = record.approval_ids.filtered(
                lambda a: a.approval_type == approval_type and a.state == 'approved'
            )
            record.has_pending_approval = bool(pending)
            record.is_stage_approved = bool(approved)

    def action_request_approval(self):
        for record in self:
            record._check_basic_stage_requirements()

            approval_type = record.stage_id.approval_type
            if not approval_type:
                name_lower = (record.stage_id.name or '').lower()
                if 'management' in name_lower or 'review' in name_lower:
                    approval_type = 'management_review'
                elif 'kra' in name_lower:
                    approval_type = 'kra'
                elif 'activity' in name_lower:
                    approval_type = 'activity_plan'
                elif 'study' in name_lower or 'finding' in name_lower:
                    approval_type = 'system_study'
                elif 'strategic' in name_lower or 'foundation' in name_lower:
                    approval_type = 'strategic_foundation'
                elif 'deliverable' in name_lower or 'sop' in name_lower:
                    approval_type = 'deliverables'
                elif 'closure' in name_lower:
                    approval_type = 'project_closure'
                else:
                    approval_type = 'other'
                record.stage_id.sudo().write({
                    'approval_type': approval_type,
                    'requires_approval': True,
                })

            pending = self.env['business.project.approval'].search([
                ('project_id', '=', record.id),
                ('approval_type', '=', approval_type),
                ('state', '=', 'pending'),
            ], limit=1)
            if pending:
                raise UserError(
                    f'An approval request ({pending.name}) is already pending for stage "{record.stage_id.name}".'
                )

            approver = record.stage_id.approver_id
            if not approver:
                ceo_users = self.env['res.users'].search([]).filtered(
                    lambda u: u.has_group('Benjali_management.group_ceo')
                )
                if ceo_users:
                    approver = ceo_users[0]
                else:
                    approver = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user

            approval = self.env['business.project.approval'].create({
                'project_id': record.id,
                'approval_type': approval_type,
                'approver_id': approver.id,
                'requires_approval': True,
                'company_id': record.company_id.id or self.env.company.id,
            })

            record.message_post(
                body=(
                    f'Approval request <b>{approval.name}</b> submitted to '
                    f'<b>{approver.name}</b> (CEO) for stage <b>{record.stage_id.name}</b>.'
                )
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Approval Requested',
                'message': 'Approval request submitted to CEO.',
                'sticky': False,
                'type': 'success',
            }
        }

    def action_approve_pending(self):
        self.ensure_one()
        approval_type = self.stage_id.approval_type or 'management_review'
        pending = self.approval_ids.filtered(
            lambda a: a.approval_type == approval_type and a.state == 'pending'
        )
        if not pending:
            pending = self.approval_ids.filtered(lambda a: a.state == 'pending')
        if not pending:
            raise UserError('No pending approval request found for this project.')
        pending[:1].action_approve()

    def action_reject_pending(self):
        self.ensure_one()
        approval_type = self.stage_id.approval_type or 'management_review'
        pending = self.approval_ids.filtered(
            lambda a: a.approval_type == approval_type and a.state == 'pending'
        )
        if not pending:
            pending = self.approval_ids.filtered(lambda a: a.state == 'pending')
        if not pending:
            raise UserError('No pending approval request found for this project.')
        pending[:1].action_reject()

    def _check_basic_stage_requirements(self):
        """Validate non-approval stage requirements."""
        for record in self:
            if record.is_cancelled:
                raise UserError(
                    'Cancelled projects cannot move to another stage.'
                )
            if record.is_completed:
                raise UserError(
                    'Completed projects cannot move to another stage.'
                )
            if record.is_on_hold:
                raise UserError(
                    'Resume the project before moving to another stage.'
                )

    def _check_stage_requirements(self):
        """Validate requirements before leaving the current stage."""
        for record in self:
            record._check_basic_stage_requirements()

            # Check approval requirements
            stage_needs_approval = record.stage_id.requires_approval or (
                record.stage_id.name and 'management review' in record.stage_id.name.lower()
            )
            if stage_needs_approval:
                approval_type = record.stage_id.approval_type or 'management_review'
                if not record.stage_id.approval_type:
                    record.stage_id.sudo().write({
                        'approval_type': approval_type,
                        'requires_approval': True,
                    })

                approved_approval = self.env['business.project.approval'].search([
                    ('project_id', '=', record.id),
                    ('approval_type', '=', approval_type),
                    ('state', '=', 'approved'),
                ], limit=1)

                if not approved_approval:
                    pending_approval = self.env['business.project.approval'].search([
                        ('project_id', '=', record.id),
                        ('approval_type', '=', approval_type),
                        ('state', '=', 'pending'),
                    ], limit=1)

                    if pending_approval:
                        raise UserError(
                            f'Stage "{record.stage_id.name}" is waiting for CEO approval ({pending_approval.name}). '
                            'The project can move to the next stage only after approval.'
                        )

                    # Auto-create approval request if none exists
                    record.action_request_approval()
                    raise UserError(
                        f'CEO Approval is required for stage "{record.stage_id.name}". '
                        'An approval request has now been submitted to the CEO. '
                        'The stage will advance once approved.'
                    )

            stage_lower = (record.stage_id.name or '').lower()
            if ('team allocation' in stage_lower or 'team designation' in stage_lower) and not record.team_member_ids:
                raise UserError(
                    'Please allocate at least one team member before '
                    'moving to the next stage.'
                )
            if ('kick-off' in stage_lower or 'kickoff' in stage_lower) and not record.kickoff_completed:
                raise UserError(
                    'Please complete the client kick-off before moving '
                    'to the next stage.'
                )
            if 'data collection' in stage_lower:
                if not record.data_collection_ids:
                    raise UserError(
                        'Please add at least one data collection item '
                        'before moving to the next stage.'
                    )
                if any(
                        item.state not in ('collected', 'verified')
                        for item in record.data_collection_ids
                ):
                    raise UserError(
                        'All data collection items must be Collected or '
                        'Verified before moving to Analysis & Findings.'
                    )
            if 'communication' in stage_lower and not record.communication_created:
                raise UserError(
                    'Please complete the project communication setup '
                    'before moving to the next stage.'
                )
            if 'rollout' in stage_lower and not record.client_implementation_coordinator_id:
                raise UserError(
                    'Step 29: Client must designate an Implementation Coordinator before moving to Consultant Verification.'
                )

    def write(self, vals):
        if 'stage_id' in vals and not self.env.context.get(
                'skip_stage_requirements'):
            for record in self:
                if vals['stage_id'] != record.stage_id.id:
                    record._check_stage_requirements()
        return super().write(vals)

    # NEXT STAGE

    def action_next_stage(self):
        for record in self:
            record._check_stage_requirements()

            # Normal stage movement
            next_stage = self.env['business.project.stage'].search([
                ('sequence', '>', record.stage_id.sequence),
                ('active', '=', True),
                ('name', 'not in', ['On Hold', 'Cancelled']),
                ('name', 'not ilike', 'proposal'),
            ], order='sequence asc', limit=1)

            if not next_stage:
                raise UserError(
                    'There is no next stage.'
                )

            old_stage = record.stage_id

            record.with_context(skip_stage_requirements=True).write({
                'previous_stage_id': old_stage.id,
                'stage_id': next_stage.id,
            })

            record._assign_stage_responsible_user()
            record._create_stage_activity()

            record.message_post(
                body=(
                    f'Project moved from '
                    f'<b>{old_stage.name}</b> to '
                    f'<b>{next_stage.name}</b>.'
                )
            )

    def action_move_after_approval(self):
        for record in self:

            current_stage = record.stage_id

            next_stage = self.env[
                'business.project.stage'
            ].search([
                ('sequence', '>', current_stage.sequence),
                ('active', '=', True),
                ('name', 'not in', ['On Hold', 'Cancelled']),
                ('name', 'not ilike', 'proposal'),
            ], order='sequence asc', limit=1)

            if not next_stage:
                raise UserError(
                    'There is no next stage.'
                )

            record.with_context(skip_stage_requirements=True).write({
                'previous_stage_id': current_stage.id,
                'stage_id': next_stage.id,
            })
            record._assign_stage_responsible_user()
            record._create_stage_activity()

            record.message_post(
                body=(
                    f'Approval completed for '
                    f'<b>{current_stage.name}</b>. '
                    f'Project moved to '
                    f'<b>{next_stage.name}</b>.'
                )
            )

    # PREVIOUS STAGE


    def action_previous_stage(self):

        for record in self:

            if record.is_completed:
                raise UserError(
                    'A completed project cannot move backwards directly.'
                )

            if record.is_on_hold:
                raise UserError(
                    'Resume the project before moving backwards.'
                )

            previous_stage = self.env['business.project.stage'].search(
                [
                    ('active', '=', True),
                    ('sequence', '<', record.stage_id.sequence),
                    ('name', 'not in', ['On Hold', 'Cancelled']),
                    ('name', 'not ilike', 'proposal'),
                ],
                order='sequence desc',
                limit=1
            )

            if not previous_stage:
                raise UserError(
                    'There is no previous stage.'
                )

            record.with_context(skip_stage_requirements=True).write({
                'previous_stage_id': record.stage_id.id,
                'stage_id': previous_stage.id,
            })

            record.message_post(
                body=(
                    'Stage changed from <b>%s</b> to <b>%s</b>.'
                    % (
                        record.previous_stage_id.name,
                        previous_stage.name
                    )
                )
            )

        return True


    # HOLD


    def action_hold(self):

        hold_stage = self.env.ref(
            'Benjali_management.stage_on_hold',
            raise_if_not_found=False
        )

        if not hold_stage:
            raise UserError(
                'On Hold stage was not found.'
            )

        for record in self:

            if record.is_cancelled:
                raise UserError(
                    'A cancelled project cannot be put on hold.'
                )

            if record.is_completed:
                raise UserError(
                    'A completed project cannot be put on hold.'
                )

            record.with_context(skip_stage_requirements=True).write({
                'hold_return_stage_id': record.stage_id.id,
                'stage_id': hold_stage.id,
            })

            record.message_post(
                body='Project has been placed <b>On Hold</b>.'
            )

        return True

    # RESUME


    def action_resume(self):

        for record in self:

            if not record.is_on_hold:
                raise UserError(
                    'This project is not on hold.'
                )

            if not record.hold_return_stage_id:
                raise UserError(
                    'No previous stage is available for resuming.'
                )

            resume_stage = record.hold_return_stage_id

            record.with_context(skip_stage_requirements=True).write({
                'stage_id': resume_stage.id,
                'hold_return_stage_id': False,
            })

            record.message_post(
                body=(
                    'Project resumed at stage '
                    '<b>%s</b>.'
                    % resume_stage.name
                )
            )

        return True


    # CANCEL


    def action_cancel(self):

        cancel_stage = self.env.ref(
            'Benjali_management.stage_cancelled',
            raise_if_not_found=False
        )

        if not cancel_stage:
            raise UserError(
                'Cancelled stage was not found.'
            )

        for record in self:

            if record.is_completed:
                raise UserError(
                    'A completed project cannot be cancelled.'
                )

            record.with_context(skip_stage_requirements=True).write({
                'previous_stage_id': record.stage_id.id,
                'stage_id': cancel_stage.id,
                'active': False,
            })

            record.message_post(
                body='Project has been <b>Cancelled</b>.'
            )

        return True

    # COMPLETE


    def action_complete(self):

        completed_stage = self.env.ref(
            'Benjali_management.stage_completed',
            raise_if_not_found=False
        )

        if not completed_stage:
            raise UserError(
                'Completed stage was not found.'
            )

        for record in self:

            if record.is_cancelled:
                raise UserError(
                    'A cancelled project cannot be completed.'
                )

            record.with_context(skip_stage_requirements=True).write({
                'previous_stage_id': record.stage_id.id,
                'stage_id': completed_stage.id,
                'actual_end_date': fields.Date.today(),
            })

            record.message_post(
                body='Project marked as <b>Completed</b>.'
            )

        return True




    #add activity

    def _create_stage_activity(self):
        for record in self:
            if not record.responsible_user_id:
                continue

            record.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=record.responsible_user_id.id,
                summary=f'Work on {record.stage_id.name}',
                note=(
                    f'Please complete the activities related to '
                    f'the stage: {record.stage_id.name}.'
                ),
            )


    def action_send_email(self):
        self.ensure_one()

        if self.communication_channel != 'email':
            raise UserError(
                'Please select Email as the communication channel before '
                'sending the project details.'
            )

        if not self.partner_id.email:
            raise UserError(
                'The project customer does not have an email address. '
                'Please add one before sending the project details.'
            )

        template = self.env.ref(
            'Benjali_management.email_template_business_project_details',
            raise_if_not_found=False
        )
        if not template:
            raise UserError('The project details email template is not configured.')

        template.with_context(
            lang=self.partner_id.lang or self.env.user.lang
        ).send_mail(self.id, force_send=True)

        self.message_post(
            body=(
                'Project details email sent to '
                f'<b>{self.partner_id.email}</b>.'
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        return True



