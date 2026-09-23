from odoo import models, fields, api
from odoo.exceptions import UserError


class BusinessProjectApproval(models.Model):
    _name = 'business.project.approval'
    _description = 'Business Project Approval'
    _order = 'id desc'

    name = fields.Char(
        string='Approval Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'business.project.approval'
        ) or 'New'
    )

    project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        required=True,
        ondelete='cascade',
        index=True
    )

    approval_type = fields.Selection([
        ('proposal', 'Proposal Approval'),
        ('management_review', 'Management Review'),
        ('kra', 'KRA Approval'),
        ('activity_plan', 'Activity Plan Approval'),
        ('other', 'Other'),
    ], string='Approval Type', required=True)

    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        required=True,
        default=lambda self: self.env.user,
        readonly=True
    )

    approver_id = fields.Many2one(
        'res.users',
        string='Approver',
        required=True
    )

    requested_date = fields.Datetime(
        string='Requested Date',
        default=fields.Datetime.now,
        readonly=True
    )

    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )

    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', required=True, tracking=True)

    comments = fields.Text(
        string='Comments'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=False
    )



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('business.project.approval') or 'New'
        return super().create(vals_list)



    def action_approve(self):
        for approval in self:

            if approval.state != 'pending':
                raise UserError(
                    'Only pending approval requests can be approved.'
                )

            if approval.approver_id != self.env.user:
                raise UserError(
                    'Only the assigned approver can approve this request.'
                )

            approval.write({
                'state': 'approved',
                'approval_date': fields.Datetime.now(),
            })

            # Move project automatically
            approval.project_id.action_move_after_approval()

            approval.project_id.message_post(
                body=(
                    f'Approval <b>{approval.name}</b> '
                    f'has been <b>approved</b> by '
                    f'{self.env.user.name}.'
                )
            )



    # def action_approve(self):
    #     for approval in self:
    #
    #         if approval.state != 'pending':
    #             raise UserError(
    #                 'Only pending approval requests can be approved.'
    #             )
    #
    #         if approval.approver_id != self.env.user:
    #             raise UserError(
    #                 'Only the assigned approver can approve this request.'
    #             )
    #
    #         approval.write({
    #             'state': 'approved',
    #             'approval_date': fields.Datetime.now(),
    #         })
    #
    #         approval.project_id.message_post(
    #             body=(
    #                 f'Approval <b>{approval.name}</b> '
    #                 f'has been <b>approved</b> by '
    #                 f'{self.env.user.name}.'
    #             )
    #         )

    def action_reject(self):
        for approval in self:

            if approval.state != 'pending':
                raise UserError(
                    'Only pending approval requests can be rejected.'
                )

            if approval.approver_id != self.env.user:
                raise UserError(
                    'Only the assigned approver can reject this request.'
                )

            approval.write({
                'state': 'rejected',
                'approval_date': fields.Datetime.now(),
            })

            approval.project_id.message_post(
                body=(
                    f'Approval <b>{approval.name}</b> '
                    f'has been <b>rejected</b> by '
                    f'{self.env.user.name}.'
                )
            )
