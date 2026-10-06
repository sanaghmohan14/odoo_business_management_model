from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
    _order = 'department_id, name'

    name = fields.Char(string='SOP Title', required=True)
    project_id = fields.Many2one('business.project', string='Business Project',
                                 required=True, ondelete='cascade', index=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True,
                                    ondelete='restrict', index=True)
    sop_type = fields.Selection([
        ('policy', 'Policy'),
        ('procedure', 'Procedure'),
        ('workflow', 'Workflow'),
    ], string='SOP Type', required=True, default='procedure')
    objective = fields.Text(string='Objective')
    scope = fields.Text(string='Scope')
    owner_id = fields.Many2one('res.users', string='SOP Owner', required=True,
                               default=lambda self: self.env.user)
    version = fields.Char(default='1.0')
    state = fields.Selection([
        ('draft', 'Draft'), ('active', 'Active'), ('review', 'Under Review'),
        ('approved', 'Approved'), ('obsolete', 'Obsolete'),
    ], default='draft', required=True, index=True)
    checklist_ids = fields.One2many('business.project.sop.checklist', 'sop_id',
                                    string='Checklists', copy=True)
    compliance_ids = fields.One2many('business.project.sop.compliance', 'sop_id',
                                     string='Compliance Checks', copy=False)
    document_ids = fields.One2many('business.project.sop.document', 'sop_id',
                                   string='Formats and Documents', copy=True)
    checklist_count = fields.Integer(compute='_compute_counts')
    compliance_count = fields.Integer(compute='_compute_counts')

    @api.depends('checklist_ids', 'compliance_ids')
    def _compute_counts(self):
        for sop in self:
            sop.checklist_count = len(sop.checklist_ids)
            sop.compliance_count = len(sop.compliance_ids)

    def action_activate(self):
        self.write({'state': 'active'})

    def action_submit_review(self):
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({'state': 'approved'})


class BusinessProjectSOPChecklist(models.Model):
    _name = 'business.project.sop.checklist'
    _description = 'SOP Checklist Item'
    _order = 'frequency, sequence, name'

    name = fields.Char(string='Checklist Item', required=True)
    sop_id = fields.Many2one('business.project.sop', string='SOP', required=True,
                             ondelete='cascade', index=True)
    frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], required=True, default='daily', index=True)
    sequence = fields.Integer(default=10)
    responsible_user_id = fields.Many2one('res.users', string='Responsible Employee')
    is_required = fields.Boolean(string='Required', default=True)
    instructions = fields.Text(string='Instructions')
    active = fields.Boolean(default=True)


class BusinessProjectSOPDocument(models.Model):
    _name = 'business.project.sop.document'
    _description = 'SOP Format or Required Document'
    _order = 'sop_id, name'

    name = fields.Char(string='Document / Format', required=True)
    sop_id = fields.Many2one('business.project.sop', string='SOP', required=True,
                             ondelete='cascade', index=True)
    document_type = fields.Selection([
        ('format', 'Required Format'),
        ('document', 'Required Document'),
        ('evidence', 'Evidence'),
        ('reference', 'Reference'),
    ], string='Type', required=True, default='format')
    description = fields.Text(string='Description')
    attachment = fields.Binary(string='File', attachment=True)
    attachment_filename = fields.Char(string='Filename')
    required = fields.Boolean(default=True)


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
    employee_id = fields.Many2one('res.users', string='Checked Employee', required=True)
    status = fields.Selection([
        ('compliant', 'Compliant'), ('non_compliant', 'Non-compliant'),
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
    _order = 'due_date, id'

    name = fields.Char(string='Gap', required=True)
    project_id = fields.Many2one('business.project', string='Business Project', required=True,
                                 ondelete='cascade', index=True)
    monitoring_id = fields.Many2one('business.project.monitoring', string='Monitoring')
    compliance_id = fields.Many2one('business.project.sop.compliance', string='Compliance Check')
    department_id = fields.Many2one('hr.department', string='Department')
    employee_id = fields.Many2one('res.users', string='Responsible Employee')
    severity = fields.Selection([
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical'),
    ], default='medium', required=True)
    description = fields.Text(string='Gap Details')
    corrective_action = fields.Text(string='Corrective Action')
    due_date = fields.Date(string='Due Date')
    state = fields.Selection([
        ('open', 'Open'), ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'), ('closed', 'Closed'),
    ], default='open', required=True, index=True)

    @api.constrains('monitoring_id', 'compliance_id')
    def _check_source(self):
        for gap in self:
            if not gap.monitoring_id and not gap.compliance_id:
                raise ValidationError('A gap must come from monitoring or an SOP compliance check.')
