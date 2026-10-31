from odoo import models, fields, api
from odoo.exceptions import UserError


class BusinessProjectApproval(models.Model):
    _name = 'business.project.approval'
    _description = 'Business Project Approval'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', readonly=True, default='New')

    project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        required=False,
        ondelete='cascade',
        index=True
    )

    kra_id = fields.Many2one(
        'business.project.kra',
        string='KRA',
        ondelete='cascade',
        index=True,
    )

    kpi_id = fields.Many2one(
        'business.project.kpi',
        string='KPI',
        ondelete='cascade',
        index=True,
    )

    subtask_id = fields.Many2one(
        'business.project.kpi.subtask',
        string='Subtask',
        ondelete='cascade',
        index=True,
    )

    approval_type = fields.Selection([
        ('management_review', 'Management Review'),
        ('kra', 'KRA Approval'),
        ('activity_plan', 'Activity Plan Approval'),
        ('system_study', 'System Study Report Approval'),
        ('strategic_foundation', 'Strategic Foundation Approval'),
        ('deliverables', 'Consulting Deliverables Approval'),
        ('project_closure', 'Project Closure Approval'),
        ('kra_completion', 'KRA Completion Approval'),
        ('kpi_completion', 'KPI Completion Approval'),
        ('subtask_completion', 'Subtask Completion Approval'),
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

    company_id = fields.Many2one('res.company',
                                 string="Company",
                                 default=lambda self: self.env.company,
                                 readonly=True)

    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('approval_type'):
                project = self.env['business.project'].browse(vals.get('project_id')) if vals.get('project_id') else None
                if project and project.stage_id and project.stage_id.approval_type:
                    vals['approval_type'] = project.stage_id.approval_type
                else:
                    vals['approval_type'] = 'management_review'

            if not vals.get('approver_id'):
                if vals.get('kra_id'):
                    kra = self.env['business.project.kra'].browse(vals['kra_id'])
                    approver = kra.project_id.project_manager_id if kra.project_id else False
                    if not approver:
                        pm_users = self.env['res.users'].search([('share', '=', False)]).filtered(
                            lambda u: u.has_group('Benjali_management.group_project_manager')
                        )
                        if pm_users:
                            approver = pm_users[0]
                    if approver:
                        vals['approver_id'] = approver.id
                elif vals.get('kpi_id'):
                    kpi = self.env['business.project.kpi'].browse(vals['kpi_id'])
                    approver = (
                        kpi.responsible_user_id or
                        (kpi.kra_id and kpi.kra_id.responsible_user_id) or
                        (kpi.project_id and kpi.project_id.responsible_user_id) or
                        kpi.project_manager_id
                    )
                    if not approver:
                        tl_users = self.env['res.users'].search([('share', '=', False)]).filtered(
                            lambda u: u.has_group('Benjali_management.group_Team_lead')
                        )
                        if tl_users:
                            approver = tl_users[0]
                    if approver:
                        vals['approver_id'] = approver.id
                elif vals.get('subtask_id'):
                    sub = self.env['business.project.kpi.subtask'].browse(vals['subtask_id'])
                    approver = (
                        sub.responsible_user_id or
                        (sub.kpi_id and sub.kpi_id.responsible_user_id) or
                        (sub.kra_id and sub.kra_id.responsible_user_id) or
                        (sub.project_id and sub.project_id.responsible_user_id) or
                        (sub.kpi_id and sub.kpi_id.project_manager_id)
                    )
                    if not approver:
                        tl_users = self.env['res.users'].search([('share', '=', False)]).filtered(
                            lambda u: u.has_group('Benjali_management.group_Team_lead')
                        )
                        if tl_users:
                            approver = tl_users[0]
                    if approver:
                        vals['approver_id'] = approver.id

            if not vals.get('approver_id'):
                pm_users = self.env['res.users'].search([('share', '=', False)]).filtered(
                    lambda u: u.has_group('Benjali_management.group_project_manager')
                )
                if pm_users:
                    vals['approver_id'] = pm_users[0].id
                else:
                    ceo_users = self.env['res.users'].search([('share', '=', False)]).filtered(
                        lambda u: u.has_group('Benjali_management.group_ceo')
                    )
                    if ceo_users:
                        vals['approver_id'] = ceo_users[0].id
                    else:
                        vals['approver_id'] = self.env.user.id

            sequence = self.env['ir.sequence'].next_by_code(
                'business.project.approval'
            )

            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = sequence or 'New'

        return super().create(vals_list)

    def _check_approver_permission(self):
        self.ensure_one()
        is_ceo = self.env.user.has_group('Benjali_management.group_ceo')
        is_vp = self.env.user.has_group('Benjali_management.group_gvp')
        is_pm = self.env.user.has_group('Benjali_management.group_project_manager')
        is_admin = self.env.is_admin()
        is_assigned_approver = (self.approver_id == self.env.user)
        is_project_responsible = bool(self.project_id and self.project_id.responsible_user_id == self.env.user)
        is_project_manager = bool(self.project_id and self.project_id.project_manager_id == self.env.user)

        if not (is_assigned_approver or is_project_responsible or is_project_manager or is_ceo or is_vp or is_pm or is_admin):
            raise UserError(
                'Only the assigned approver, Project Manager, or Executive can approve/reject this request.'
            )

    def action_approve(self):
        for approval in self:
            if approval.state != 'pending':
                raise UserError(
                    'Only pending approval requests can be approved.'
                )

            approval._check_approver_permission()

            approval.write({
                'state': 'approved',
                'approval_date': fields.Datetime.now(),
            })

            if approval.approval_type == 'kra_completion' and approval.kra_id:
                approval.kra_id.sudo()._do_mark_completed()
                approval.kra_id.message_post(
                    body=(
                        f'Approval <b>{approval.name}</b> for KRA completion '
                        f'has been <b>approved</b> by {self.env.user.name}.'
                    )
                )
            elif approval.approval_type == 'kpi_completion' and approval.kpi_id:
                approval.kpi_id.sudo()._do_mark_completed()
                approval.kpi_id.message_post(
                    body=(
                        f'Approval <b>{approval.name}</b> for KPI completion '
                        f'has been <b>approved</b> by {self.env.user.name}.'
                    )
                )
            elif approval.approval_type == 'subtask_completion' and approval.subtask_id:
                approval.subtask_id.sudo()._do_mark_completed()
                approval.subtask_id.message_post(
                    body=(
                        f'Approval <b>{approval.name}</b> for Subtask completion '
                        f'has been <b>approved</b> by {self.env.user.name}.'
                    )
                )
            elif approval.project_id:
                # Move project automatically
                approval.project_id.action_move_after_approval()
                approval.project_id.message_post(
                    body=(
                        f'Approval <b>{approval.name}</b> '
                        f'has been <b>approved</b> by '
                        f'{self.env.user.name}.'
                    )
                )

    def action_reject(self):
        for approval in self:
            if approval.state != 'pending':
                raise UserError(
                    'Only pending approval requests can be rejected.'
                )

            approval._check_approver_permission()

            approval.write({
                'state': 'rejected',
                'approval_date': fields.Datetime.now(),
            })

            comments_str = f" Reason: {approval.comments}" if approval.comments else ""

            if approval.approval_type == 'kra_completion' and approval.kra_id:
                approval.kra_id.write({'approval_pending': False})
                approval.kra_id.message_post(
                    body=(
                        f'Approval <b>{approval.name}</b> for KRA completion '
                        f'has been <b>rejected</b> by {self.env.user.name}.{comments_str}'
                    )
                )
            elif approval.approval_type == 'kpi_completion' and approval.kpi_id:
                approval.kpi_id.write({'approval_pending': False})
                approval.kpi_id.message_post(
                    body=(
                        f'Approval <b>{approval.name}</b> for KPI completion '
                        f'has been <b>rejected</b> by {self.env.user.name}.{comments_str}'
                    )
                )
            elif approval.approval_type == 'subtask_completion' and approval.subtask_id:
                approval.subtask_id.write({'approval_pending': False})
                approval.subtask_id.message_post(
                    body=(
                        f'Approval <b>{approval.name}</b> for Subtask completion '
                        f'has been <b>rejected</b> by {self.env.user.name}.{comments_str}'
                    )
                )
            elif approval.project_id:
                approval.project_id.message_post(
                    body=(
                        f'Approval <b>{approval.name}</b> '
                        f'has been <b>rejected</b> by '
                        f'{self.env.user.name}.{comments_str}'
                    )
                )
