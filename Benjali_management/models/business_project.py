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
        string='Responsible User',
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

    approval_ids = fields.One2many(
        'business.project.approval',
        'project_id',
        string='Approvals'
    )

    qualification_status = fields.Selection([
        ('not_checked', 'Not Checked'),
        ('qualified', 'Qualified'),
        ('not_qualified', 'Not Qualified'),
    ], string='Qualification Status', default='not_checked', tracking=True)

    qualification_notes = fields.Text(
        string='Qualification Notes'
    )



    @api.model
    def _default_stage(self):
        stage = self.env.ref(
            'Benjali_management.stage_new',
            raise_if_not_found=False
        )
        return stage.id if stage else False


    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return self.env['business.project.stage'].search(
            [('active', '=', True)],
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
                vals['stage_id'] = self.env.ref(
                    'Benjali_management.stage_new'
                ).id

        projects = super().create(vals_list)

        for project in projects:
            project._assign_stage_responsible_user()
            project.message_post(
                body=f'Business Project {project.name} created.'
            )

        return projects



    # ---------------------------------------------------------
    # WORKFLOW STATUS
    # ---------------------------------------------------------

    @api.depends('stage_id')
    def _compute_workflow_status(self):

        for record in self:

            stage_name = (record.stage_id.name or '').strip().lower()

            record.is_on_hold = stage_name == 'on hold'
            record.is_cancelled = stage_name == 'cancelled'
            record.is_completed = stage_name == 'completed'

    def _check_stage_requirements(self):
        """Validate requirements before leaving the current stage."""
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
            if record.stage_id.name == 'Team Allocation' and not record.team_member_ids:
                raise UserError(
                    'Please allocate at least one team member before '
                    'moving to the next stage.'
                )
            if record.stage_id.name == 'Initial Client Contact & Kick-off' \
                    and not record.kickoff_completed:
                raise UserError(
                    'Please complete the client kick-off before moving '
                    'to the next stage.'
                )
            if record.stage_id.name == 'System Study & Data Collection':
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
            if record.stage_id.name == 'Project Communication Setup' \
                    and not record.communication_created:
                raise UserError(
                    'Please complete the project communication setup '
                    'before moving to the next stage.'
                )
            if record.stage_id.name == 'Lead Screening & Qualification':
                if record.qualification_status == 'not_checked':
                    raise UserError(
                        'Please complete the lead qualification before '
                        'moving to the next stage.'
                    )
                if record.qualification_status == 'not_qualified':
                    raise UserError(
                        'This lead is not qualified and cannot proceed.'
                    )

    def write(self, vals):
        if 'stage_id' in vals and not self.env.context.get(
                'skip_stage_requirements'):
            for record in self:
                if vals['stage_id'] != record.stage_id.id:
                    record._check_stage_requirements()
                    if record.stage_id.requires_approval:
                        pending_approval = self.env[
                            'business.project.approval'
                        ].search([
                            ('project_id', '=', record.id),
                            ('approval_type', '=', record.stage_id.approval_type),
                            ('state', '=', 'pending'),
                        ], limit=1)
                        if pending_approval:
                            raise UserError(
                                'This stage is waiting for approval.'
                            )
                        raise UserError(
                            'Approval is required before moving to the next '
                            'stage. Use the Next Stage button to request it.'
                        )
        return super().write(vals)

    # ---------------------------------------------------------
    # NEXT STAGE
    # ---------------------------------------------------------

    def action_next_stage(self):
        for record in self:
            record._check_stage_requirements()
            # Check whether current stage needs approval
            if record.stage_id.requires_approval:

                pending_approval = self.env[
                    'business.project.approval'
                ].search([
                    ('project_id', '=', record.id),
                    ('approval_type', '=', record.stage_id.approval_type),
                    ('state', '=', 'pending'),
                ], limit=1)

                if pending_approval:
                    raise UserError(
                        'This stage is waiting for approval.'
                    )

                # Create approval request
                if not record.stage_id.approver_id:
                    raise UserError(
                        'Please configure an approver for this stage.'
                    )

                self.env['business.project.approval'].create({
                    'project_id': record.id,
                    'approval_type': record.stage_id.approval_type,
                    'approver_id': record.stage_id.approver_id.id,
                })

                record.message_post(
                    body=(
                        f'Approval request created for '
                        f'<b>{record.stage_id.name}</b>.'
                    )
                )

                return True

            # Normal stage movement

            next_stage = self.env['business.project.stage'].search([
                ('sequence', '>', record.stage_id.sequence),
                ('active', '=', True),
                ('name', 'not in', ['On Hold', 'Cancelled']),
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


    # ---------------------------------------------------------
    # PREVIOUS STAGE
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # HOLD
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # RESUME
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # CANCEL
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # COMPLETE
    # ---------------------------------------------------------

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



