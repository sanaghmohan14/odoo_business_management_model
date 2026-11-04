# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
import logging

_logger = logging.getLogger(__name__)


class BusinessProjectTracker(models.Model):
    _name = 'business.project.tracker'
    _description = 'Business Project Scope Tracker'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scope_no, category desc, item_no, sequence, id'

    project_id = fields.Many2one(
        'business.project',
        string='Project',
        required=False,
        default=lambda self: self.env.context.get('default_project_id') or self.env['business.project'].search([], limit=1).id,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    template_line_id = fields.Many2one(
        'business.project.tracker.template.line',
        string='Template Deliverable',
        ondelete='set null'
    )
    item_id = fields.Char(
        string='Item ID',
        index=True,
        copy=False
    )
    scope_no = fields.Integer(
        string='Scope No',
        required=True,
        default=0,
        index=True
    )
    scope_name = fields.Char(
        string='Scope',
        required=True,
        index=True
    )
    scope = fields.Char(
        string='Scope',
        compute='_compute_scope',
        inverse='_inverse_scope',
        search='_search_scope',
        store=True,
        index=True
    )
    scope_pillar = fields.Char(
        string='Pillar',
        index=True
    )
    category = fields.Selection([
        ('documentation', 'Documentation'),
        ('implementation', 'Implementation'),
    ], string='Category', required=True, default='documentation', index=True, tracking=True)

    item_no = fields.Integer(
        string='Item No',
        default=1
    )
    name = fields.Char(
        string='Item Name',
        required=True,
        tracking=True
    )
    item_name = fields.Char(
        string='Item Name',
        compute='_compute_item_name',
        inverse='_inverse_item_name',
        search='_search_item_name',
        store=True,
        tracking=True
    )
    item_type = fields.Char(
        string='Item Type'
    )
    evidence_required = fields.Text(
        string='Evidence / Proof Required'
    )
    evidence_proof = fields.Text(
        string='Evidence / Proof',
        compute='_compute_evidence_proof',
        inverse='_inverse_evidence_proof',
        store=True
    )
    final_approval_authority = fields.Selection([
        ('TL', 'Team Lead (TL)'),
        ('PM', 'Project Manager (PM)'),
        ('VP', 'Vice President (VP)'),
        ('CEO', 'Chief Executive Officer (CEO)'),
    ], string='Final Approval Authority', required=True, default='TL', tracking=True, index=True)
    approval_authority = fields.Selection([
        ('TL', 'Team Lead (TL)'),
        ('PM', 'Project Manager (PM)'),
        ('VP', 'Vice President (VP)'),
        ('CEO', 'Chief Executive Officer (CEO)'),
    ], string='Approval Authority', compute='_compute_approval_authority', inverse='_inverse_approval_authority', store=True)

    can_current_user_approve = fields.Boolean(
        string='Can Approve',
        compute='_compute_can_approve'
    )

    accountable_id = fields.Many2one(
        'res.users',
        string='Accountable (TL / PM)',
        tracking=True,
        index=True
    )
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsible',
        tracking=True,
        index=True
    )

    start_date = fields.Date(
        string='Start Date',
        tracking=True
    )
    end_date = fields.Date(
        string='End Date',
        tracking=True
    )

    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='not_started', index=True, tracking=True)

    progress = fields.Float(
        string='Progress (%)',
        default=0.0,
        tracking=True
    )

    evidence_file = fields.Binary(
        string='Evidence Attachment',
        attachment=True
    )
    evidence_filename = fields.Char(
        string='Evidence File Name'
    )
    evidence_notes = fields.Text(
        string='Evidence Details & Remarks',
        tracking=True
    )

    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True
    )
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )
    review_comments = fields.Text(
        string='Approval / Review Comments'
    )

    is_overdue = fields.Boolean(
        string='Is Overdue',
        compute='_compute_is_overdue',
        search='_search_is_overdue'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    company_id = fields.Many2one(
        'res.company',
        related='project_id.company_id',
        string='Company',
        store=True,
        readonly=True
    )

    @api.depends('final_approval_authority')
    def _compute_can_approve(self):
        user = self.env.user
        is_admin = user.has_group('base.group_system')
        has_tl = user.has_group('Benjali_management.group_Team_lead') or is_admin
        has_pm = user.has_group('Benjali_management.group_project_manager') or is_admin
        has_vp = user.has_group('Benjali_management.group_gvp') or is_admin
        has_ceo = user.has_group('Benjali_management.group_ceo') or is_admin

        for rec in self:
            auth = rec.final_approval_authority
            if auth == 'TL':
                rec.can_current_user_approve = has_tl
            elif auth == 'PM':
                rec.can_current_user_approve = has_pm
            elif auth == 'VP':
                rec.can_current_user_approve = has_vp
            elif auth == 'CEO':
                rec.can_current_user_approve = has_ceo
            else:
                rec.can_current_user_approve = is_admin

    @api.depends('end_date', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = bool(
                rec.end_date and rec.end_date < today and rec.state not in ('approved', 'completed', 'cancelled')
            )

    def _search_is_overdue(self, operator, value):
        today = fields.Date.today()
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [
                ('end_date', '<', today),
                ('state', 'not in', ('approved', 'completed', 'cancelled'))
            ]
        else:
            return ['|', '|',
                ('end_date', '>=', today),
                ('end_date', '=', False),
                ('state', 'in', ('approved', 'completed', 'cancelled'))
            ]

    # -------------------------------------------------------------------------
    # SYNCHRONIZATION HELPERS & ALIASES
    # -------------------------------------------------------------------------

    @api.depends('scope_name')
    def _compute_scope(self):
        for rec in self:
            rec.scope = rec.scope_name

    def _inverse_scope(self):
        for rec in self:
            if rec.scope and not rec.scope_name:
                rec.scope_name = rec.scope

    def _search_scope(self, operator, value):
        return [('scope_name', operator, value)]

    @api.depends('name')
    def _compute_item_name(self):
        for rec in self:
            rec.item_name = rec.name

    def _inverse_item_name(self):
        for rec in self:
            if rec.item_name and not rec.name:
                rec.name = rec.item_name

    def _search_item_name(self, operator, value):
        return [('name', operator, value)]

    @api.depends('evidence_required')
    def _compute_evidence_proof(self):
        for rec in self:
            rec.evidence_proof = rec.evidence_required

    def _inverse_evidence_proof(self):
        for rec in self:
            if rec.evidence_proof and not rec.evidence_required:
                rec.evidence_required = rec.evidence_proof

    @api.depends('final_approval_authority')
    def _compute_approval_authority(self):
        for rec in self:
            rec.approval_authority = rec.final_approval_authority

    def _inverse_approval_authority(self):
        for rec in self:
            if rec.approval_authority and not rec.final_approval_authority:
                rec.final_approval_authority = rec.approval_authority

    @api.model_create_multi
    def create(self, vals_list):
        default_proj = self.env.context.get('default_project_id') or self.env['business.project'].search([], limit=1).id
        for vals in vals_list:
            if not vals.get('project_id') and default_proj:
                vals['project_id'] = default_proj
            if 'item_name' in vals and not vals.get('name'):
                vals['name'] = vals['item_name']
            elif 'name' in vals and not vals.get('item_name'):
                vals['item_name'] = vals['name']
            if 'scope' in vals and not vals.get('scope_name'):
                vals['scope_name'] = vals['scope']
            elif 'scope_name' in vals and not vals.get('scope'):
                vals['scope'] = vals['scope_name']
            if 'evidence_proof' in vals and not vals.get('evidence_required'):
                vals['evidence_required'] = vals['evidence_proof']
            elif 'evidence_required' in vals and not vals.get('evidence_proof'):
                vals['evidence_proof'] = vals['evidence_required']
            if 'approval_authority' in vals and not vals.get('final_approval_authority'):
                vals['final_approval_authority'] = vals['approval_authority']
            elif 'final_approval_authority' in vals and not vals.get('approval_authority'):
                vals['approval_authority'] = vals['final_approval_authority']
        return super().create(vals_list)

    def write(self, vals):
        if 'item_name' in vals and 'name' not in vals:
            vals['name'] = vals['item_name']
        elif 'name' in vals and 'item_name' not in vals:
            vals['item_name'] = vals['name']
        if 'scope' in vals and 'scope_name' not in vals:
            vals['scope_name'] = vals['scope']
        elif 'scope_name' in vals and 'scope' not in vals:
            vals['scope'] = vals['scope_name']
        if 'evidence_proof' in vals and 'evidence_required' not in vals:
            vals['evidence_required'] = vals['evidence_proof']
        elif 'evidence_required' in vals and 'evidence_proof' not in vals:
            vals['evidence_proof'] = vals['evidence_required']
        if 'approval_authority' in vals and 'final_approval_authority' not in vals:
            vals['final_approval_authority'] = vals['approval_authority']
        elif 'final_approval_authority' in vals and 'approval_authority' not in vals:
            vals['approval_authority'] = vals['final_approval_authority']
        return super().write(vals)

    # -------------------------------------------------------------------------
    # WORKFLOW ACTIONS
    # -------------------------------------------------------------------------

    def action_start(self):
        for rec in self:
            vals = {'state': 'in_progress'}
            if rec.progress == 0.0:
                vals['progress'] = 10.0
            rec.write(vals)

    def action_submit(self):
        for rec in self:
            if not rec.evidence_file and not (rec.evidence_notes and rec.evidence_notes.strip()):
                raise UserError(_(
                    "Please attach an Evidence File or enter Evidence Details/Remarks before submitting deliverable '%s' for approval."
                ) % rec.name)
            vals = {'state': 'submitted'}
            if rec.progress < 90.0:
                vals['progress'] = 90.0
            rec.write(vals)
            rec.message_post(
                body=_("Deliverable submitted for approval (%s authority required).") % dict(
                    self._fields['final_approval_authority'].selection
                ).get(rec.final_approval_authority, rec.final_approval_authority),
                subject=_("Submitted for Approval")
            )

    def action_approve(self):
        for rec in self:
            rec._check_approval_permission()
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
                'progress': 100.0,
            })
            rec.message_post(
                body=_("Deliverable approved by %s (%s).") % (
                    self.env.user.name,
                    dict(self._fields['final_approval_authority'].selection).get(rec.final_approval_authority)
                ),
                subject=_("Deliverable Approved")
            )

    def _check_approval_permission(self):
        self.ensure_one()
        user = self.env.user
        if user.has_group('base.group_system'):
            return True

        auth = self.final_approval_authority
        authority_name = dict(self._fields['final_approval_authority'].selection).get(auth, auth)

        if auth == 'TL' and not user.has_group('Benjali_management.group_Team_lead'):
            raise AccessError(_("Approval authority '%s' is required. You do not have Team Lead rights.") % authority_name)
        elif auth == 'PM' and not user.has_group('Benjali_management.group_project_manager'):
            raise AccessError(_("Approval authority '%s' is required. You do not have Project Manager rights.") % authority_name)
        elif auth == 'VP' and not user.has_group('Benjali_management.group_gvp'):
            raise AccessError(_("Approval authority '%s' is required. You do not have VP rights.") % authority_name)
        elif auth == 'CEO' and not user.has_group('Benjali_management.group_ceo'):
            raise AccessError(_("Approval authority '%s' is required. You do not have CEO rights.") % authority_name)

        return True

    def action_complete(self):
        for rec in self:
            rec.write({
                'state': 'completed',
                'progress': 100.0,
            })

    def action_reject(self):
        for rec in self:
            rec._check_approval_permission()
            rec.write({
                'state': 'in_progress',
                'approved_by_id': False,
                'approval_date': False,
            })
            rec.message_post(
                body=_("Deliverable returned to In Progress by %s. Review Comments: %s") % (
                    self.env.user.name, rec.review_comments or 'None'
                ),
                subject=_("Deliverable Returned / Needs Revision")
            )

    def action_reset(self):
        for rec in self:
            rec.write({
                'state': 'not_started',
                'progress': 0.0,
                'approved_by_id': False,
                'approval_date': False,
            })

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})
