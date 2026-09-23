from odoo import models, fields, api
from odoo.exceptions import UserError


class BusinessProject(models.Model):
    _name = 'business.project'
    _description = 'Business Consulting Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # ---------------------------------------------------------
    # BASIC INFORMATION
    # ---------------------------------------------------------

    name = fields.Char(
        string='Project Name',
        required=True,
        tracking=True
    )

    reference = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # ---------------------------------------------------------
    # WORKFLOW
    # ---------------------------------------------------------

    stage_id = fields.Many2one(
        'business.project.stage',
        string='Stage',
        required=True,
        tracking=True,
        ondelete='restrict'
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

    # ---------------------------------------------------------
    # CUSTOMER
    # ---------------------------------------------------------

    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
        ondelete='restrict'
    )

    # ---------------------------------------------------------
    # CRM / SALES
    # ---------------------------------------------------------

    opportunity_id = fields.Many2one(
        'crm.lead',
        string='Opportunity',
        tracking=True,
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
        tracking=True,
        ondelete='set null'
    )

    # ---------------------------------------------------------
    # PROJECT
    # ---------------------------------------------------------

    project_id = fields.Many2one(
        'project.project',
        string='Odoo Project',
        tracking=True,
        ondelete='set null'
    )

    project_manager_id = fields.Many2one(
        'res.users',
        string='Project Manager',
        tracking=True,
        ondelete='set null'
    )

    # ---------------------------------------------------------
    # DATES
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # DESCRIPTION
    # ---------------------------------------------------------

    description = fields.Text(
        string='Description'
    )

    notes = fields.Html(
        string='Internal Notes'
    )

    # ---------------------------------------------------------
    # COMPUTED INFORMATION
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # DEFAULT
    # ---------------------------------------------------------

    @api.model
    def _default_stage(self):
        stage = self.env.ref(
            'business_consulting_management.stage_new',
            raise_if_not_found=False
        )
        return stage.id if stage else False

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:

            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'business.project'
                ) or 'New'

            if not vals.get('stage_id'):
                stage = self.env.ref(
                    'business_consulting_management.stage_new',
                    raise_if_not_found=False
                )

                if stage:
                    vals['stage_id'] = stage.id

        records = super().create(vals_list)

        for record in records:
            record.message_post(
                body='Business project created.'
            )

        return records

    # ---------------------------------------------------------
    # WORKFLOW STATUS
    # ---------------------------------------------------------

    @api.depends('stage_id')
    def _compute_workflow_status(self):

        for record in self:

            stage_name = record.stage_id.name.lower()

            record.is_on_hold = stage_name == 'on hold'
            record.is_cancelled = stage_name == 'cancelled'
            record.is_completed = stage_name == 'completed'

    # ---------------------------------------------------------
    # NEXT STAGE
    # ---------------------------------------------------------

    def action_next_stage(self):

        for record in self:

            if record.is_cancelled:
                raise UserError(
                    'A cancelled project cannot move to the next stage.'
                )

            if record.is_completed:
                raise UserError(
                    'This project is already completed.'
                )

            if record.is_on_hold:
                raise UserError(
                    'Resume the project before moving to the next stage.'
                )

            next_stage = self.env['business.project.stage'].search(
                [
                    ('active', '=', True),
                    ('sequence', '>', record.stage_id.sequence),
                    ('name', 'not in', ['On Hold', 'Cancelled']),
                ],
                order='sequence asc',
                limit=1
            )

            if not next_stage:
                raise UserError(
                    'There is no next stage.'
                )

            record.write({
                'previous_stage_id': record.stage_id.id,
                'stage_id': next_stage.id,
            })

            record.message_post(
                body=(
                    'Stage changed from <b>%s</b> to <b>%s</b>.'
                    % (
                        record.previous_stage_id.name,
                        next_stage.name
                    )
                )
            )

        return True

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

            record.write({
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
            'business_consulting_management.stage_on_hold',
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

            record.write({
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

            record.write({
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
            'business_consulting_management.stage_cancelled',
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

            record.write({
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
            'business_consulting_management.stage_completed',
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

            record.write({
                'previous_stage_id': record.stage_id.id,
                'stage_id': completed_stage.id,
                'actual_end_date': fields.Date.today(),
            })

            record.message_post(
                body='Project marked as <b>Completed</b>.'
            )

        return True