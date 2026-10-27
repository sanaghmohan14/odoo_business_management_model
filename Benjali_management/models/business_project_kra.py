from datetime import timedelta
import calendar

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BusinessProjectKRAStage(models.Model):
    _name = 'business.project.kra.stage'
    _description = 'KRA Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    code = fields.Selection([
        ('new', 'New'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ], string='Stage Code', required=True)
    folded = fields.Boolean(string='Folded in Kanban', default=False)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')


class BusinessProjectKPIStage(models.Model):
    _name = 'business.project.kpi.stage'
    _description = 'KPI Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    code = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ], string='Stage Code', required=True)
    folded = fields.Boolean(string='Folded in Kanban', default=False)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')


class BusinessProjectKRA(models.Model):
    _name = 'business.project.kra'
    _description = 'Business Project & Department KRA (Main Task)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id desc'

    name = fields.Char(string='KRA Name (Main Task)', required=True, tracking=True)
    reference = fields.Char(string='KRA Code', required=True, copy=False,
                            default='New', index=True)

    project_id = fields.Many2one(
        'business.project', string='Project', required=True,
        ondelete='cascade', index=True, tracking=True,
        help='Project this KRA belongs to.')
    department_id = fields.Many2one(
        'hr.department', string='Department', required=False, index=True,
        compute='_compute_department_id', store=True, readonly=False,
        help='Department responsible for this Key Result Area.')

    manager_id = fields.Many2one(
        'res.users', string='KRA Manager', index=True,
        default=lambda self: self.env.user, tracking=True)
    responsible_user_id = fields.Many2one(
        'res.users', string='Responsible Manager / Lead', index=True,
        related='manager_id', store=True, readonly=False, tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Assigned User',
        related='manager_id', store=True, readonly=False, index=True)

    # Stages: Many2one for kanban ordering & drag, synced with state
    stage_id = fields.Many2one(
        'business.project.kra.stage',
        string='Stage',
        default=lambda self: self._default_stage_id(),
        group_expand='_read_group_stage_ids',
        tracking=True,
        index=True,
        copy=False,
    )
    state = fields.Selection([
        ('new', 'New'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ], string='Status', default='new', required=True, index=True, tracking=True)

    def _default_stage_id(self):
        stage = self.env['business.project.kra.stage'].search([('code', '=', 'new')], order='sequence, id', limit=1)
        if not stage:
            stage = self.env['business.project.kra.stage'].search([], order='sequence, id', limit=1)
        return stage

    @api.model
    def _normalize_stages(self):
        """Ensures exactly the 4 canonical KRA stages exist with correct names, codes, and sequences."""
        canonical_specs = [
            ('new', ['new', 'draft'], 'New', 10, False, 'Newly created KRA'),
            ('ongoing', ['ongoing', 'in_progress', 'active'], 'Ongoing', 20, False, 'KRA is currently in progress'),
            ('completed', ['completed', 'done', 'closed'], 'Completed', 30, False, 'KRA has been completed'),
            ('on_hold', ['on_hold', 'hold', 'paused', 'cancelled', 'postponed'], 'On Hold', 40, False, 'KRA is temporarily paused'),
        ]
        Stage = self.env['business.project.kra.stage']
        kept_ids = []

        try:
            with self.env.cr.savepoint():
                for code, aliases, name, seq, folded, desc in canonical_specs:
                    domain = ['|', ('code', 'in', aliases), ('name', 'ilike', name)]
                    matching = Stage.search(domain, order='id asc')

                    if matching:
                        primary = matching[0]
                        for st in matching:
                            self.env.cr.execute("""
                                SELECT id FROM ir_model_data
                                WHERE model = 'business.project.kra.stage' AND res_id = %s
                                LIMIT 1;
                            """, (st.id,))
                            if self.env.cr.fetchone():
                                primary = st
                                break

                        primary.write({
                            'name': name,
                            'code': code,
                            'sequence': seq,
                            'folded': folded,
                            'description': desc,
                            'active': True,
                        })
                        kept_ids.append(primary.id)

                        duplicates = matching.filtered(lambda s: s.id != primary.id)
                        if duplicates:
                            dup_ids = tuple(duplicates.ids)
                            self.env.cr.execute("""
                                UPDATE business_project_kra
                                SET stage_id = %s
                                WHERE stage_id IN %s;
                            """, (primary.id, dup_ids))
                            self.env.cr.execute("""
                                DELETE FROM ir_model_data
                                WHERE model = 'business.project.kra.stage' AND res_id IN %s;
                            """, (dup_ids,))
                            self.env.cr.execute("""
                                DELETE FROM business_project_kra_stage
                                WHERE id IN %s;
                            """, (dup_ids,))
                    else:
                        st = Stage.create({
                            'name': name,
                            'code': code,
                            'sequence': seq,
                            'folded': folded,
                            'description': desc,
                            'active': True,
                        })
                        kept_ids.append(st.id)

                if kept_ids:
                    orphan_stages = Stage.search([('id', 'not in', kept_ids)])
                    if orphan_stages:
                        default_stage_id = kept_ids[0]
                        orphan_ids = tuple(orphan_stages.ids)
                        self.env.cr.execute("""
                            UPDATE business_project_kra
                            SET stage_id = %s
                            WHERE stage_id IN %s;
                        """, (default_stage_id, orphan_ids))
                        self.env.cr.execute("""
                            DELETE FROM ir_model_data
                            WHERE model = 'business.project.kra.stage' AND res_id IN %s;
                        """, (orphan_ids,))
                        self.env.cr.execute("""
                            DELETE FROM business_project_kra_stage
                            WHERE id IN %s;
                        """, (orphan_ids,))

                self.env.cr.execute("""
                    UPDATE business_project_kra kra
                    SET stage_id = st.id
                    FROM business_project_kra_stage st
                    WHERE kra.state = st.code AND (kra.stage_id IS NULL OR kra.stage_id != st.id);
                """)
                self.env.cr.execute("""
                    UPDATE business_project_kra kra
                    SET state = st.code
                    FROM business_project_kra_stage st
                    WHERE kra.stage_id = st.id AND kra.state != st.code;
                """)
        except Exception:
            pass

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        self._normalize_stages()
        return self.env['business.project.kra.stage'].search(
            [('active', '=', True), ('code', 'in', ['new', 'ongoing', 'completed', 'on_hold'])],
            order='sequence asc, id asc'
        )
    priority = fields.Selection([
        ('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Very High'),
    ], string='Priority', default='0', index=True)
    active = fields.Boolean(string='Active', default=True)

    start_date = fields.Date(string='Start Date', default=fields.Date.context_today)
    end_date = fields.Date(string='End Date')
    description = fields.Text(string='Description / Strategic Objective')
    objective = fields.Text(string='Objective Details')
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True)

    # Sub-tasks: KPIs
    kpi_ids = fields.One2many(
        'business.project.kpi', 'kra_id', string='KPIs (Sub-Tasks)', copy=True)
    entry_ids = fields.One2many(
        'business.project.kra.entry', 'kra_id', string='Performance Entries', copy=False)
    task_ids = fields.One2many('project.task', 'kra_id', string='Project Tasks')
    employee_ids = fields.Many2many(
        'res.users', 'business_project_kra_employee_rel', 'kra_id', 'user_id',
        string='Assigned Employees', compute='_compute_assigned_employees', store=True)

    # Metrics
    kpi_count = fields.Integer(compute='_compute_kpi_metrics', string='Total KPIs', store=True)
    completed_kpi_count = fields.Integer(compute='_compute_kpi_metrics', string='Completed KPIs', store=True)

    daily_kpi_total = fields.Integer(compute='_compute_daily_metrics', string="Today's Tasks")
    daily_kpi_completed = fields.Integer(compute='_compute_daily_metrics', string="Today's Completed")
    daily_completion_rate = fields.Float(compute='_compute_daily_metrics', string="Today's Completion Rate (%)")

    weekly_weightage_total = fields.Float(compute='_compute_weekly_metrics', string='Total Weekly Weight (%)', store=True)
    weekly_target_total = fields.Float(compute='_compute_weekly_metrics', string='Weekly Target Total', store=True)
    weekly_achievement = fields.Float(compute='_compute_weekly_metrics', string='Weekly Achievement', store=True)
    weekly_progress = fields.Float(compute='_compute_weekly_metrics', string='Weekly Progress (%)', store=True)

    monthly_target = fields.Float(string='Monthly Weightage Target', default=100.0, readonly=True)
    monthly_achievement = fields.Float(compute='_compute_monthly_metrics', string='Monthly Achievement (/100)', store=True)

    # Overall progress percentage (used by dashboard and progress bars)
    progress_percentage = fields.Float(compute='_compute_overall_progress', string='Overall Progress (%)', store=True)
    achievement = fields.Float(compute='_compute_overall_progress', string='Actual Achievement', store=True)

    # Legacy fields
    kpi = fields.Char(string='KPI Summary')
    measurement = fields.Char(string='Measurement Method')
    target = fields.Float(string='Target (Legacy)', default=0.0)
    unit = fields.Char(string='Unit', default='units')
    frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Frequency', default='weekly')
    entry_count = fields.Integer(compute='_compute_entry_count', string='Entries')
    task_count = fields.Integer(compute='_compute_task_metrics', string='Tasks')
    completed_task_count = fields.Integer(compute='_compute_task_metrics', string='Completed Tasks')
    pending_task_count = fields.Integer(compute='_compute_task_metrics', string='Pending Tasks')
    on_hold_task_count = fields.Integer(compute='_compute_task_metrics', string='On Hold Tasks')
    task_completion_percentage = fields.Float(compute='_compute_task_metrics', string='Task Completion (%)')
    kpi_weight_total = fields.Float(compute='_compute_weekly_metrics', string='Total KPI Weight (%)', store=True)
    weighted_kpi_score = fields.Float(compute='_compute_weekly_metrics', string='Weighted KPI Score (%)', store=True)

    @api.depends('project_id', 'project_id.department_id')
    def _compute_department_id(self):
        for kra in self:
            if kra.project_id and kra.project_id.department_id:
                kra.department_id = kra.project_id.department_id
            elif not kra.department_id:
                ctx_dept = self.env.context.get('default_department_id')
                user_dept = self.env.user.department_id.id if hasattr(self.env.user, 'department_id') and self.env.user.department_id else False
                kra.department_id = ctx_dept or user_dept or False

    @api.depends('kpi_ids.employee_id')
    def _compute_assigned_employees(self):
        for kra in self:
            employees = kra.kpi_ids.mapped('employee_id')
            if kra.responsible_user_id and kra.responsible_user_id not in employees:
                employees |= kra.responsible_user_id
            kra.employee_ids = [(6, 0, employees.ids)]

    @api.depends('kpi_ids', 'kpi_ids.state')
    def _compute_kpi_metrics(self):
        for kra in self:
            kra.kpi_count = len(kra.kpi_ids)
            kra.completed_kpi_count = len(kra.kpi_ids.filtered(lambda k: k.state == 'completed'))

    def _compute_daily_metrics(self):
        today = fields.Date.context_today(self)
        for kra in self:
            today_kpis = kra.kpi_ids.filtered(lambda k: k.date == today)
            kra.daily_kpi_total = len(today_kpis)
            kra.daily_kpi_completed = len(today_kpis.filtered(lambda k: k.state == 'completed'))
            kra.daily_completion_rate = (
                (kra.daily_kpi_completed / kra.daily_kpi_total * 100.0) if kra.daily_kpi_total else 0.0
            )

    @api.depends('kpi_ids.weekly_weightage', 'kpi_ids.weekly_target', 'kpi_ids.weekly_achievement',
                 'kpi_ids.weekly_progress', 'kpi_ids.weekly_weighted_score')
    def _compute_weekly_metrics(self):
        for kra in self:
            kpis = kra.kpi_ids
            kra.weekly_target_total = sum(kpis.mapped('weekly_target'))
            kra.weekly_achievement = sum(kpis.mapped('weekly_achievement'))
            kra.weekly_weightage_total = sum(kpis.mapped('weekly_weightage'))
            kra.kpi_weight_total = kra.weekly_weightage_total

            if kpis:
                total_weight = kra.weekly_weightage_total or 100.0
                weighted_sum = sum(kpi.weekly_progress * (kpi.weekly_weightage / total_weight) for kpi in kpis)
                kra.weekly_progress = min(max(weighted_sum, 0.0), 100.0)
            else:
                kra.weekly_progress = 100.0 if kra.state == 'completed' else 0.0
            kra.weighted_kpi_score = kra.weekly_progress

    @api.depends('kpi_ids.monthly_achievement', 'kpi_ids.weekly_weightage', 'weekly_progress')
    def _compute_monthly_metrics(self):
        for kra in self:
            kpis = kra.kpi_ids
            if kpis:
                total_weight = sum(kpis.mapped('weekly_weightage')) or 100.0
                # User requirement:
                # "for monthly weightage target is 100 based on weekly achievement it fills,
                #  weekly connected to daily, monthly connected to week results"
                score = sum(kpi.monthly_achievement * (kpi.weekly_weightage / total_weight) for kpi in kpis)
                kra.monthly_achievement = min(max(score, 0.0), 100.0)
            else:
                kra.monthly_achievement = 100.0 if kra.state == 'completed' else 0.0

    @api.depends('monthly_achievement', 'weekly_progress', 'state')
    def _compute_overall_progress(self):
        for kra in self:
            if kra.state == 'completed':
                kra.progress_percentage = 100.0
                kra.achievement = 100.0
            elif kra.kpi_ids:
                kra.progress_percentage = kra.monthly_achievement
                kra.achievement = kra.monthly_achievement
            else:
                kra.progress_percentage = 0.0
                kra.achievement = 0.0

    @api.depends('entry_ids')
    def _compute_entry_count(self):
        for kra in self:
            kra.entry_count = len(kra.entry_ids)

    @api.depends('task_ids.performance_status')
    def _compute_task_metrics(self):
        for kra in self:
            tasks = kra.task_ids
            kra.task_count = len(tasks)
            kra.completed_task_count = len(tasks.filtered(lambda t: t.performance_status == 'completed'))
            kra.pending_task_count = len(tasks.filtered(lambda t: t.performance_status in ('pending', 'in_progress')))
            kra.on_hold_task_count = len(tasks.filtered(lambda t: t.performance_status == 'on_hold'))
            kra.task_completion_percentage = (
                kra.completed_task_count / len(tasks) * 100 if tasks else 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        Stage = self.env['business.project.kra.stage']
        for vals in vals_list:
            if not vals.get('reference') or vals.get('reference') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('business.project.kra') or 'KRA'
            if vals.get('stage_id') and not vals.get('state'):
                st = Stage.browse(vals['stage_id'])
                if st.code:
                    vals['state'] = st.code
            elif vals.get('state') and not vals.get('stage_id'):
                st = Stage.search([('code', '=', vals['state'])], limit=1)
                if st:
                    vals['stage_id'] = st.id
            elif not vals.get('stage_id') and not vals.get('state'):
                def_st = self._default_stage_id()
                if def_st:
                    vals['stage_id'] = def_st.id
                    vals['state'] = def_st.code or 'new'
        records = super().create(vals_list)
        for kra in records:
            kra.action_generate_daily_repeating_kpis()
        return records

    def write(self, vals):
        Stage = self.env['business.project.kra.stage']
        if 'stage_id' in vals and 'state' not in vals:
            st = Stage.browse(vals['stage_id'])
            if st and st.code:
                vals['state'] = st.code
        elif 'state' in vals and 'stage_id' not in vals:
            st = Stage.search([('code', '=', vals['state'])], limit=1)
            if st:
                vals['stage_id'] = st.id
        return super().write(vals)

    def init(self):
        super().init()
        self._normalize_stages()
        try:
            self.env.cr.execute("""
                UPDATE business_project_kra 
                SET state = CASE 
                    WHEN state IN ('not_started', 'draft') THEN 'new'
                    WHEN state IN ('active', 'in_progress') THEN 'ongoing'
                    WHEN state IN ('postponed', 'cancelled') THEN 'on_hold'
                    WHEN state = 'completed' THEN 'completed'
                    ELSE 'new'
                END
                WHERE state NOT IN ('new', 'ongoing', 'completed', 'on_hold') OR state IS NULL;
            """)
            self.env.cr.execute("""
                UPDATE business_project_kra kra
                SET stage_id = st.id
                FROM business_project_kra_stage st
                WHERE kra.state = st.code AND (kra.stage_id IS NULL OR kra.stage_id != st.id);
            """)
        except Exception:
            pass

    # Stage actions: New, Ongoing, Completed, On Hold
    def action_set_new(self):
        st = self.env['business.project.kra.stage'].search([('code', '=', 'new')], limit=1)
        vals = {'state': 'new'}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_ongoing(self):
        st = self.env['business.project.kra.stage'].search([('code', '=', 'ongoing')], limit=1)
        vals = {'state': 'ongoing'}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_completed(self):
        st = self.env['business.project.kra.stage'].search([('code', '=', 'completed')], limit=1)
        vals = {'state': 'completed'}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_on_hold(self):
        st = self.env['business.project.kra.stage'].search([('code', '=', 'on_hold')], limit=1)
        vals = {'state': 'on_hold'}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    # Backward compatibility aliases
    def action_set_not_started(self):
        self.action_set_new()

    def action_set_in_progress(self):
        self.action_set_ongoing()

    def action_set_postponed(self):
        self.action_set_on_hold()

    def action_activate(self):
        self.action_set_ongoing()

    def action_complete(self):
        self.action_set_completed()

    def action_cancel(self):
        self.action_set_on_hold()

    def action_generate_daily_repeating_kpis(self, target_date=None):
        """
        User Requirement:
        "In the Kra some tasks are daily repeating task and some are not repeating
         i want to manage that option also the repeating task should come daily
         and need option to add new tasks also, the daily repeating tasks should need
         to be automatically added under the kra as kpi."
        """
        self.ensure_one()
        target_date = target_date or fields.Date.context_today(self)

        # Repeating tasks can be either marked as is_daily_repeating without parent
        # or distinct repeating task templates under this KRA
        repeating_kpis = self.kpi_ids.filtered(lambda k: k.is_daily_repeating)
        # Unique master templates (either master records with no recurring_template_id, or template targets)
        master_templates = {}
        for k in repeating_kpis:
            key = k.recurring_template_id.id if k.recurring_template_id else k.id
            if key not in master_templates:
                master_templates[key] = k.recurring_template_id or k

        created_count = 0
        KPI = self.env['business.project.kpi']
        for master_id, master in master_templates.items():
            # Check if today's instance for this repeating task exists under this KRA
            exists = KPI.search([
                ('kra_id', '=', self.id),
                ('date', '=', target_date),
                '|',
                ('id', '=', master_id),
                ('recurring_template_id', '=', master_id),
            ], limit=1)

            if not exists:
                KPI.create({
                    'name': master.name,
                    'code': self.env['ir.sequence'].next_by_code('business.project.kpi') or 'KPI',
                    'kra_id': self.id,
                    'project_id': self.project_id.id if self.project_id else False,
                    'department_id': self.department_id.id if self.department_id else False,
                    'employee_id': master.employee_id.id if master.employee_id else self.env.user.id,
                    'is_daily_repeating': True,
                    'recurring_template_id': master_id,
                    'date': target_date,
                    'state': 'not_started',
                    'weekly_target': master.weekly_target or 6.0,
                    'weekly_weightage': master.weekly_weightage or 100.0,
                    'daily_target': master.daily_target or 1.0,
                    'daily_achievement': 0.0,
                    'unit': master.unit or 'units',
                })
                created_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Repeating KPIs Generated',
                'message': f"{created_count} daily repeating task(s) added under KRA '{self.name}' for {target_date}.",
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def _cron_generate_daily_repeating_kpis(self):
        """Cron job to automatically generate daily repeating tasks under active KRAs."""
        today = fields.Date.context_today(self)
        active_kras = self.search([
            ('active', '=', True),
            ('state', 'in', ['new', 'ongoing', 'not_started', 'in_progress'])
        ])
        for kra in active_kras:
            kra.action_generate_daily_repeating_kpis(target_date=today)
        return True

    def action_view_kpis(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - KPIs',
            'res_model': 'business.project.kpi',
            'view_mode': 'kanban,list,form,pivot,graph',
            'domain': [('kra_id', '=', self.id)],
            'context': {
                'default_kra_id': self.id,
                'default_project_id': self.project_id.id if self.project_id else False,
                'default_manager_id': self.manager_id.id if self.manager_id else False,
                'default_department_id': self.department_id.id if self.department_id else False,
                'search_default_kra_id': self.id,
                'search_default_group_stage_id': 1,
            },
        }

    def action_view_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Performance Entries',
            'res_model': 'business.project.kra.entry',
            'view_mode': 'list,kanban,form,pivot,graph',
            'domain': [('kra_id', '=', self.id)],
            'context': {
                'default_kra_id': self.id,
                'default_department_id': self.department_id.id if self.department_id else False,
                'default_project_id': self.project_id.id if self.project_id else False,
            },
        }


class BusinessProjectKPI(models.Model):
    _name = 'business.project.kpi'
    _description = 'Business Project & Department KPI (Sub-Task)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, sequence, id desc'

    name = fields.Char(string='KPI Name', required=True, tracking=True)
    code = fields.Char(string='KPI Code', copy=False, default='New')
    kra_id = fields.Many2one(
        'business.project.kra', string='KRA', required=True,
        ondelete='cascade', index=True, tracking=True)

    project_id = fields.Many2one(
        'business.project', string='Project',
        compute='_compute_kra_details', store=True, readonly=False, index=True, tracking=True,
        help='Project automatically filled when KRA is chosen.')
    manager_id = fields.Many2one(
        'res.users', string='KRA Manager',
        compute='_compute_kra_details', store=True, readonly=False, index=True, tracking=True,
        help='KRA Manager automatically filled when KRA is chosen.')
    kra_manager_id = fields.Many2one(
        'res.users', string='KRA Manager', related='manager_id', readonly=True)
    department_id = fields.Many2one(
        'hr.department', string='Department',
        compute='_compute_kra_details', store=True, readonly=False, index=True)

    employee_ids = fields.Many2many(
        'res.users', 'business_project_kpi_user_rel', 'kpi_id', 'user_id',
        string='Assigned Employees', tracking=True)
    employee_id = fields.Many2one(
        'res.users', string='Assigned Employee',
        compute='_compute_employee_id', inverse='_inverse_employee_id',
        store=True, index=True, tracking=True)
    hr_employee_ids = fields.Many2many(
        'hr.employee', 'business_project_kpi_hr_employee_rel', 'kpi_id', 'employee_id',
        string='Assigned HR Employees', compute='_compute_hr_employee_ids', inverse='_inverse_hr_employee_ids',
        store=True, tracking=True)

    # Stages: Many2one for kanban ordering & drag, synced with state
    stage_id = fields.Many2one(
        'business.project.kpi.stage',
        string='Stage',
        default=lambda self: self._default_stage_id(),
        group_expand='_read_group_stage_ids',
        tracking=True,
        index=True,
        copy=False,
    )
    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='not_started', required=True, index=True, tracking=True)

    def _default_stage_id(self):
        stage = self.env['business.project.kpi.stage'].search([('code', '=', 'not_started')], order='sequence, id', limit=1)
        if not stage:
            stage = self.env['business.project.kpi.stage'].search([], order='sequence, id', limit=1)
        return stage

    @api.model
    def _normalize_stages(self):
        """Ensures exactly the 5 canonical KPI stages exist with correct names, codes, and sequences."""
        canonical_specs = [
            ('not_started', ['not_started', 'draft', 'new'], 'Not Started', 10, False, 'Task has not been started yet'),
            ('in_progress', ['in_progress', 'ongoing', 'active'], 'In Progress', 20, False, 'Task is currently in progress'),
            ('completed', ['completed', 'done', 'closed'], 'Completed', 30, False, 'Task has been completed'),
            ('on_hold', ['on_hold', 'hold', 'paused', 'postponed'], 'On Hold', 40, False, 'Task is temporarily paused'),
            ('cancelled', ['cancelled', 'cancel', 'rejected'], 'Cancelled', 50, True, 'Task has been cancelled'),
        ]
        Stage = self.env['business.project.kpi.stage']
        kept_ids = []

        try:
            with self.env.cr.savepoint():
                for code, aliases, name, seq, folded, desc in canonical_specs:
                    domain = ['|', ('code', 'in', aliases), ('name', 'ilike', name)]
                    matching = Stage.search(domain, order='id asc')

                    if matching:
                        primary = matching[0]
                        for st in matching:
                            self.env.cr.execute("""
                                SELECT id FROM ir_model_data
                                WHERE model = 'business.project.kpi.stage' AND res_id = %s
                                LIMIT 1;
                            """, (st.id,))
                            if self.env.cr.fetchone():
                                primary = st
                                break

                        primary.write({
                            'name': name,
                            'code': code,
                            'sequence': seq,
                            'folded': folded,
                            'description': desc,
                            'active': True,
                        })
                        kept_ids.append(primary.id)

                        duplicates = matching.filtered(lambda s: s.id != primary.id)
                        if duplicates:
                            dup_ids = tuple(duplicates.ids)
                            self.env.cr.execute("""
                                UPDATE business_project_kpi
                                SET stage_id = %s
                                WHERE stage_id IN %s;
                            """, (primary.id, dup_ids))
                            self.env.cr.execute("""
                                DELETE FROM ir_model_data
                                WHERE model = 'business.project.kpi.stage' AND res_id IN %s;
                            """, (dup_ids,))
                            self.env.cr.execute("""
                                DELETE FROM business_project_kpi_stage
                                WHERE id IN %s;
                            """, (dup_ids,))
                    else:
                        st = Stage.create({
                            'name': name,
                            'code': code,
                            'sequence': seq,
                            'folded': folded,
                            'description': desc,
                            'active': True,
                        })
                        kept_ids.append(st.id)

                if kept_ids:
                    orphan_stages = Stage.search([('id', 'not in', kept_ids)])
                    if orphan_stages:
                        default_stage_id = kept_ids[0]
                        orphan_ids = tuple(orphan_stages.ids)
                        self.env.cr.execute("""
                            UPDATE business_project_kpi
                            SET stage_id = %s
                            WHERE stage_id IN %s;
                        """, (default_stage_id, orphan_ids))
                        self.env.cr.execute("""
                            DELETE FROM ir_model_data
                            WHERE model = 'business.project.kpi.stage' AND res_id IN %s;
                        """, (orphan_ids,))
                        self.env.cr.execute("""
                            DELETE FROM business_project_kpi_stage
                            WHERE id IN %s;
                        """, (orphan_ids,))

                self.env.cr.execute("""
                    UPDATE business_project_kpi kpi
                    SET stage_id = st.id
                    FROM business_project_kpi_stage st
                    WHERE kpi.state = st.code AND (kpi.stage_id IS NULL OR kpi.stage_id != st.id);
                """)
                self.env.cr.execute("""
                    UPDATE business_project_kpi kpi
                    SET state = st.code
                    FROM business_project_kpi_stage st
                    WHERE kpi.stage_id = st.id AND kpi.state != st.code;
                """)
        except Exception:
            pass

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        self._normalize_stages()
        return self.env['business.project.kpi.stage'].search(
            [('active', '=', True), ('code', 'in', ['not_started', 'in_progress', 'completed', 'on_hold', 'cancelled'])],
            order='sequence asc, id asc'
        )

    is_daily_repeating = fields.Boolean(
        string='Repeating Task', default=False, tracking=True,
        help='If checked, this task is a repeating task.')
    is_repeating = fields.Boolean(
        string='Repeating Task', related='is_daily_repeating', readonly=False)
    recurring_template_id = fields.Many2one(
        'business.project.kpi', string='Repeating Source Template',
        ondelete='set null', index=True)

    # Progress bar with sliding option up to 100
    progress = fields.Float(string='Progress (%)', default=0.0, tracking=True)

    # Timesheets
    timesheet_ids = fields.One2many(
        'account.analytic.line', 'kpi_id', string='Timesheets')
    total_hours_spent = fields.Float(
        string='Recorded Hours', compute='_compute_total_hours_spent', store=True)

    # Date & Period
    date = fields.Date(
        string='Date', default=fields.Date.context_today, required=True, index=True)
    day_name = fields.Selection([
        ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
        ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
    ], string='Day of Week', compute='_compute_period_dates', store=True)
    week_start = fields.Date(
        string='Week Starting', compute='_compute_period_dates', store=True, index=True)
    week_number = fields.Char(
        string='Week', compute='_compute_period_dates', store=True, index=True)
    month_start = fields.Date(
        string='Month', compute='_compute_period_dates', store=True, index=True)
    month_name = fields.Char(
        string='Month Name', compute='_compute_period_dates', store=True)

    is_today = fields.Boolean(
        string="Today's Task", compute='_compute_period_flags', search='_search_is_today')
    is_this_week = fields.Boolean(
        string="This Week's Task", compute='_compute_period_flags', search='_search_is_this_week')
    is_this_month = fields.Boolean(
        string="This Month's Task", compute='_compute_period_flags', search='_search_is_this_month')

    # Daily values
    daily_target = fields.Float(string='Daily Target', default=1.0)
    daily_achievement = fields.Float(string='Daily Achievement', default=0.0)

    # User Requirement:
    # "the weightage and taarget are assigned by weekly, when the dailly tasks is complted
    #  they achieve the targets calculate based on that."
    weekly_target = fields.Float(
        string='Weekly Target', default=5.0, required=True,
        help='Assigned weekly target (e.g. 5 completions, 1 deliverable). Daily tasks achieve this target.')
    weekly_weightage = fields.Float(
        string='Weekly Weightage (%)', default=100.0, required=True,
        help='Assigned weekly weightage percentage of this KPI.')
    unit = fields.Char(string='Unit', default='units')

    weekly_achievement = fields.Float(
        string='Weekly Achievement', compute='_compute_weekly_performance', store=True,
        help='Calculated based on daily completed tasks in this week.')
    weekly_progress = fields.Float(
        string='Weekly Progress (%)', compute='_compute_weekly_performance', store=True)
    weekly_weighted_score = fields.Float(
        string='Weekly Weighted Score (%)', compute='_compute_weekly_performance', store=True)

    # User Requirement:
    # "for monthly weightage target is 100 based on weekly achievement it fills,
    #  weekly connected to daily, monthly connected to week results"
    monthly_target = fields.Float(
        string='Monthly Weightage Target', default=100.0, readonly=True)
    monthly_achievement = fields.Float(
        string='Monthly Achievement (/100)', compute='_compute_monthly_performance', store=True,
        help='Monthly target is 100. It fills based on weekly achievement results.')
    performance_percentage = fields.Float(
        string='Performance Score (%)', compute='_compute_performance_percentage', store=True)

    # Legacy compatibility fields
    measurement_type = fields.Selection([
        ('quantity', 'Quantity / Count'),
        ('percentage', 'Percentage (%)'),
        ('quality', 'Quality Score (Rating)'),
        ('timeliness', 'Timeliness (Hours/Days)'),
    ], string='Measurement Type', default='quantity')
    target = fields.Float(string='Target (Legacy)', related='weekly_target', readonly=False)
    weight = fields.Float(string='Weight (Legacy)', related='weekly_weightage', readonly=False)
    frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Frequency', default='daily')
    achievement = fields.Float(string='Achievement (Legacy)', related='weekly_achievement')
    weighted_contribution = fields.Float(string='Weighted Contribution (Legacy)', related='weekly_weighted_score')
    entry_ids = fields.One2many(
        'business.project.kra.entry', 'kpi_id', string='Performance Entries')
    entry_count = fields.Integer(compute='_compute_entry_count', string='Entries')
    description = fields.Text(string='Measurement Description')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    def init(self):
        super().init()
        try:
            self.env.cr.execute("""
                UPDATE business_project_kpi 
                SET state = CASE 
                    WHEN state = 'postponed' THEN 'on_hold'
                    WHEN state IN ('not_started', 'in_progress', 'completed', 'on_hold', 'cancelled') THEN state
                    ELSE 'not_started'
                END
                WHERE state NOT IN ('not_started', 'in_progress', 'completed', 'on_hold', 'cancelled');
            """)
        except Exception:
            pass

    @api.depends('kra_id', 'kra_id.project_id', 'kra_id.manager_id', 'kra_id.responsible_user_id', 'kra_id.department_id')
    def _compute_kra_details(self):
        for kpi in self:
            if kpi.kra_id:
                kpi.project_id = kpi.kra_id.project_id
                kpi.manager_id = kpi.kra_id.manager_id or kpi.kra_id.responsible_user_id
                kpi.department_id = kpi.kra_id.department_id
            else:
                if not kpi.project_id:
                    kpi.project_id = False
                if not kpi.manager_id:
                    kpi.manager_id = False
                if not kpi.department_id:
                    kpi.department_id = False

    @api.onchange('kra_id')
    def _onchange_kra_id(self):
        if self.kra_id:
            self.project_id = self.kra_id.project_id
            self.manager_id = self.kra_id.manager_id or self.kra_id.responsible_user_id
            if self.kra_id.department_id:
                self.department_id = self.kra_id.department_id

    @api.depends('employee_ids')
    def _compute_employee_id(self):
        for kpi in self:
            if kpi.employee_ids and not kpi.employee_id:
                kpi.employee_id = kpi.employee_ids[0]
            elif not kpi.employee_ids:
                kpi.employee_id = False

    def _inverse_employee_id(self):
        for kpi in self:
            if kpi.employee_id and kpi.employee_id not in kpi.employee_ids:
                kpi.employee_ids = [(4, kpi.employee_id.id)]

    @api.depends('employee_ids')
    def _compute_hr_employee_ids(self):
        Employee = self.env['hr.employee']
        for kpi in self:
            if kpi.employee_ids:
                linked_emps = Employee.search([('user_id', 'in', kpi.employee_ids.ids)])
                manual_emps = kpi.hr_employee_ids.filtered(lambda e: not e.user_id)
                kpi.hr_employee_ids = linked_emps | manual_emps
            else:
                manual_emps = kpi.hr_employee_ids.filtered(lambda e: not e.user_id)
                kpi.hr_employee_ids = manual_emps

    def _inverse_hr_employee_ids(self):
        for kpi in self:
            user_ids = kpi.hr_employee_ids.mapped('user_id')
            if user_ids:
                kpi.employee_ids = [(6, 0, user_ids.ids)]

    @api.depends('timesheet_ids.unit_amount')
    def _compute_total_hours_spent(self):
        for kpi in self:
            kpi.total_hours_spent = sum(kpi.timesheet_ids.mapped('unit_amount'))

    @api.onchange('progress')
    def _onchange_progress(self):
        if self.progress >= 100.0 and self.state in ('not_started', 'in_progress', 'on_hold'):
            self.state = 'completed'
            self.progress = 100.0
        elif 0.0 < self.progress < 100.0 and self.state in ('not_started', 'completed'):
            self.state = 'in_progress'
        elif self.progress <= 0.0 and self.state == 'completed':
            self.state = 'not_started'
            self.progress = 0.0

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'completed' and self.progress < 100.0:
            self.progress = 100.0
        elif self.state == 'not_started' and self.progress > 0.0:
            self.progress = 0.0

    @api.depends('date')
    def _compute_period_dates(self):
        for kpi in self:
            d = fields.Date.to_date(kpi.date or fields.Date.context_today(kpi))
            if d:
                kpi.day_name = str(d.weekday())
                mon = d - timedelta(days=d.weekday())
                kpi.week_start = mon
                kpi.week_number = f"W{d.isocalendar()[1]}-{d.year}"
                kpi.month_start = d.replace(day=1)
                kpi.month_name = d.strftime('%B %Y')
            else:
                kpi.day_name = False
                kpi.week_start = False
                kpi.week_number = False
                kpi.month_start = False
                kpi.month_name = False

    def _compute_period_flags(self):
        today = fields.Date.context_today(self)
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        m_start = today.replace(day=1)
        next_m = (m_start + timedelta(days=32)).replace(day=1)
        for kpi in self:
            kpi.is_today = (kpi.date == today)
            kpi.is_this_week = (mon <= kpi.date <= sun) if kpi.date else False
            kpi.is_this_month = (m_start <= kpi.date < next_m) if kpi.date else False

    def _search_is_today(self, operator, value):
        today = fields.Date.context_today(self)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return [('date', '=', today)]
        return [('date', '!=', today)]

    def _search_is_this_week(self, operator, value):
        today = fields.Date.context_today(self)
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return [('date', '>=', mon), ('date', '<=', sun)]
        return ['|', ('date', '<', mon), ('date', '>', sun)]

    def _search_is_this_month(self, operator, value):
        today = fields.Date.context_today(self)
        first_day = today.replace(day=1)
        next_month = (first_day + timedelta(days=32)).replace(day=1)
        last_day = next_month - timedelta(days=1)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return [('date', '>=', first_day), ('date', '<=', last_day)]
        return ['|', ('date', '<', first_day), ('date', '>', last_day)]

    @api.depends('state', 'daily_achievement', 'weekly_target', 'weekly_weightage',
                 'is_daily_repeating', 'recurring_template_id', 'date', 'week_start')
    def _compute_weekly_performance(self):
        for kpi in self:
            if kpi.is_daily_repeating and kpi.week_start:
                template_id = kpi.recurring_template_id.id or kpi.id
                # Search all instances of this repeating task in the same week
                domain = [
                    ('kra_id', '=', kpi.kra_id.id),
                    ('week_start', '=', kpi.week_start),
                    '|', ('id', '=', template_id), ('recurring_template_id', '=', template_id),
                ]
                week_kpis = self.env['business.project.kpi'].search(domain)
                completed_count = len(week_kpis.filtered(lambda r: r.state == 'completed'))
                # Also include daily achievement sum if explicitly specified
                ach_sum = sum(r.daily_achievement for r in week_kpis.filtered(lambda r: r.state == 'completed'))
                kpi.weekly_achievement = max(completed_count, ach_sum)
            else:
                if kpi.state == 'completed' or kpi.progress >= 100.0:
                    kpi.weekly_achievement = kpi.weekly_target or 1.0
                elif kpi.state == 'in_progress' or kpi.progress > 0.0:
                    prog_ratio = (kpi.progress / 100.0) if kpi.progress else 0.5
                    kpi.weekly_achievement = kpi.daily_achievement or ((kpi.weekly_target or 1.0) * prog_ratio)
                else:
                    kpi.weekly_achievement = kpi.daily_achievement or 0.0

            target = kpi.weekly_target or 1.0
            prog = (kpi.weekly_achievement / target * 100.0) if target > 0 else 0.0
            if kpi.progress > 0:
                prog = max(prog, kpi.progress)
            kpi.weekly_progress = min(max(prog, 0.0), 100.0)
            kpi.weekly_weighted_score = kpi.weekly_progress * (kpi.weekly_weightage / 100.0)

    @api.depends('weekly_progress', 'week_start', 'month_start', 'kra_id',
                 'is_daily_repeating', 'recurring_template_id')
    def _compute_monthly_performance(self):
        for kpi in self:
            if not kpi.month_start:
                kpi.monthly_achievement = kpi.weekly_progress or 0.0
                continue

            template_id = kpi.recurring_template_id.id or kpi.id if kpi.is_daily_repeating else kpi.id
            domain = [
                ('kra_id', '=', kpi.kra_id.id),
                ('month_start', '=', kpi.month_start),
            ]
            if kpi.is_daily_repeating:
                domain += ['|', ('id', '=', template_id), ('recurring_template_id', '=', template_id)]
            else:
                domain += [('id', '=', kpi.id)]

            month_kpis = self.env['business.project.kpi'].search(domain)
            unique_weeks = list(set(month_kpis.mapped('week_start')))

            if unique_weeks:
                # Average weekly achievement across weeks in this month
                week_scores = []
                for w in unique_weeks:
                    w_kpis = month_kpis.filtered(lambda r: r.week_start == w)
                    week_scores.append(max(w_kpis.mapped('weekly_progress')) if w_kpis else 0.0)
                avg_weekly = sum(week_scores) / len(week_scores) if week_scores else 0.0
                # Monthly target is 100; fills based on weekly achievements
                kpi.monthly_achievement = min(max(avg_weekly, 0.0), 100.0)
            else:
                kpi.monthly_achievement = kpi.weekly_progress or 0.0

    @api.depends('monthly_achievement', 'weekly_progress')
    def _compute_performance_percentage(self):
        for kpi in self:
            kpi.performance_percentage = kpi.monthly_achievement

    @api.depends('entry_ids')
    def _compute_entry_count(self):
        for kpi in self:
            kpi.entry_count = len(kpi.entry_ids)

    @api.model_create_multi
    def create(self, vals_list):
        Stage = self.env['business.project.kpi.stage']
        for vals in vals_list:
            if not vals.get('code') or vals.get('code') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('business.project.kpi') or 'KPI'
            if vals.get('stage_id') and not vals.get('state'):
                st = Stage.browse(vals['stage_id'])
                if st.code:
                    vals['state'] = st.code
            elif vals.get('state') and not vals.get('stage_id'):
                st = Stage.search([('code', '=', vals['state'])], limit=1)
                if st:
                    vals['stage_id'] = st.id
            elif not vals.get('stage_id') and not vals.get('state'):
                def_st = self._default_stage_id()
                if def_st:
                    vals['stage_id'] = def_st.id
                    vals['state'] = def_st.code or 'not_started'

            if vals.get('state') == 'completed':
                if 'daily_achievement' not in vals:
                    vals['daily_achievement'] = vals.get('daily_target', 1.0)
                if 'progress' not in vals:
                    vals['progress'] = 100.0
        records = super().create(vals_list)
        for kpi in records:
            if kpi.state in ('in_progress', 'completed'):
                kpi._sync_to_kra_entry()
        return records

    def write(self, vals):
        Stage = self.env['business.project.kpi.stage']
        if 'stage_id' in vals and 'state' not in vals:
            st = Stage.browse(vals['stage_id'])
            if st and st.code:
                vals['state'] = st.code
        elif 'state' in vals and 'stage_id' not in vals:
            st = Stage.search([('code', '=', vals['state'])], limit=1)
            if st:
                vals['stage_id'] = st.id

        if 'state' in vals:
            if vals['state'] == 'completed':
                if 'daily_achievement' not in vals:
                    vals['daily_achievement'] = 1.0
                if 'progress' not in vals:
                    vals['progress'] = 100.0
            elif vals['state'] in ('not_started', 'on_hold', 'cancelled', 'postponed') and 'daily_achievement' not in vals:
                vals['daily_achievement'] = 0.0
                if vals['state'] == 'not_started' and 'progress' not in vals:
                    vals['progress'] = 0.0
            elif vals['state'] == 'in_progress':
                if 'progress' not in vals and not any(self.mapped('progress')):
                    vals['progress'] = 25.0

        if 'progress' in vals:
            if vals['progress'] >= 100.0 and vals.get('state') not in ('completed', 'cancelled'):
                vals['state'] = 'completed'
                st = Stage.search([('code', '=', 'completed')], limit=1)
                if st:
                    vals['stage_id'] = st.id
            elif vals['progress'] <= 0.0 and vals.get('state') == 'completed':
                vals['state'] = 'not_started'
                st = Stage.search([('code', '=', 'not_started')], limit=1)
                if st:
                    vals['stage_id'] = st.id

        res = super().write(vals)
        if 'state' in vals or 'stage_id' in vals or 'daily_achievement' in vals:
            for kpi in self:
                kpi._sync_to_kra_entry()
        return res

    def init(self):
        super().init()
        self._normalize_stages()
        try:
            self.env.cr.execute("""
                UPDATE business_project_kpi 
                SET state = CASE 
                    WHEN state = 'postponed' THEN 'on_hold'
                    WHEN state IN ('not_started', 'in_progress', 'completed', 'on_hold', 'cancelled') THEN state
                    ELSE 'not_started'
                END
                WHERE state NOT IN ('not_started', 'in_progress', 'completed', 'on_hold', 'cancelled') OR state IS NULL;
            """)
            self.env.cr.execute("""
                UPDATE business_project_kpi kpi
                SET stage_id = st.id
                FROM business_project_kpi_stage st
                WHERE kpi.state = st.code AND (kpi.stage_id IS NULL OR kpi.stage_id != st.id);
            """)
        except Exception:
            pass

    def _sync_to_kra_entry(self):
        """Maintains backward compatibility with entry logs for dashboard stats."""
        for kpi in self:
            entry = self.env['business.project.kra.entry'].search([
                ('kpi_id', '=', kpi.id),
                ('date', '=', kpi.date),
            ], limit=1)
            status_map = {
                'not_started': 'pending',
                'in_progress': 'in_progress',
                'completed': 'completed',
                'on_hold': 'on_hold',
                'cancelled': 'cancelled',
                'postponed': 'on_hold',
            }
            entry_vals = {
                'name': f"{kpi.name} ({kpi.state.replace('_', ' ').title()})",
                'kra_id': kpi.kra_id.id,
                'kpi_id': kpi.id,
                'project_id': kpi.project_id.id if kpi.project_id else False,
                'department_id': kpi.department_id.id if kpi.department_id else False,
                'employee_id': kpi.employee_id.id if kpi.employee_id else self.env.user.id,
                'date': kpi.date,
                'target': kpi.weekly_target,
                'achievement': kpi.daily_achievement,
                'task_status': status_map.get(kpi.state, 'completed'),
                'state': 'approved' if kpi.state == 'completed' else 'draft',
            }
            if entry:
                entry.write(entry_vals)
            elif kpi.state in ('in_progress', 'completed'):
                self.env['business.project.kra.entry'].create(entry_vals)

    # 5 Stage actions: Not Started, In Progress, Completed, On Hold, Cancelled
    def action_set_not_started(self):
        st = self.env['business.project.kpi.stage'].search([('code', '=', 'not_started')], limit=1)
        vals = {'state': 'not_started', 'daily_achievement': 0.0, 'progress': 0.0}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_in_progress(self):
        st = self.env['business.project.kpi.stage'].search([('code', '=', 'in_progress')], limit=1)
        vals = {'state': 'in_progress'}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_completed(self):
        st = self.env['business.project.kpi.stage'].search([('code', '=', 'completed')], limit=1)
        vals = {'state': 'completed', 'daily_achievement': 1.0, 'progress': 100.0}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_on_hold(self):
        st = self.env['business.project.kpi.stage'].search([('code', '=', 'on_hold')], limit=1)
        vals = {'state': 'on_hold'}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_cancelled(self):
        st = self.env['business.project.kpi.stage'].search([('code', '=', 'cancelled')], limit=1)
        vals = {'state': 'cancelled'}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_postponed(self):
        self.action_set_on_hold()

    def action_view_timesheets(self):
        self.ensure_one()
        acc = self.env['account.analytic.line']._find_or_create_project_analytic_account(self.project_id)
        ctx = {
            'default_kpi_id': self.id,
            'default_business_project_id': self.project_id.id if self.project_id else False,
            'default_name': f'Work on {self.name}',
        }
        if acc:
            ctx['default_account_id'] = acc.id
        if self.project_id and self.project_id.project_id:
            ctx['default_project_id'] = self.project_id.project_id.id
        return {
            'type': 'ir.actions.act_window',
            'name': f'Timesheets - {self.name}',
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form',
            'domain': [('kpi_id', '=', self.id)],
            'context': ctx,
        }

    def action_view_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Entries',
            'res_model': 'business.project.kra.entry',
            'view_mode': 'list,form',
            'domain': [('kpi_id', '=', self.id)],
            'context': {
                'default_kpi_id': self.id,
                'default_kra_id': self.kra_id.id,
                'default_department_id': self.department_id.id if self.department_id else False,
                'default_project_id': self.project_id.id if self.project_id else False,
                'default_employee_id': self.employee_id.id if self.employee_id else self.env.user.id,
            },
        }


class BusinessProjectKRAEntry(models.Model):
    _name = 'business.project.kra.entry'
    _description = 'Performance Entry Log'
    _order = 'date desc, id desc'

    name = fields.Char(string='Work / Achievement Summary', required=True)
    kra_id = fields.Many2one(
        'business.project.kra', string='KRA', required=True,
        ondelete='cascade', index=True)
    kpi_id = fields.Many2one(
        'business.project.kpi', string='KPI (Optional)',
        ondelete='cascade', index=True, domain="[('kra_id', '=', kra_id)]")
    task_id = fields.Many2one(
        'project.task', string='Project Task',
        ondelete='cascade', index=True)

    department_id = fields.Many2one(
        'hr.department', string='Department', compute='_compute_hierarchy',
        store=True, readonly=False, index=True)
    project_id = fields.Many2one(
        'business.project', string='Business Project', compute='_compute_hierarchy',
        store=True, readonly=False, index=True)

    employee_id = fields.Many2one(
        'res.users', string='Employee / Contributor', required=True,
        default=lambda self: self.env.user, index=True)
    user_id = fields.Many2one(
        'res.users', string='Employee Link', related='employee_id',
        store=True, readonly=True, index=True)

    date = fields.Date(
        string='Date', required=True, default=fields.Date.context_today,
        index=True)
    day = fields.Selection([
        ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
        ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
    ], string='Day', compute='_compute_period', store=True)
    week_start = fields.Date(
        string='Week', compute='_compute_period', store=True, index=True)
    month_start = fields.Date(
        string='Month', compute='_compute_period', store=True, index=True)

    period_type = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Performance Period', required=True, default='monthly', index=True)

    target = fields.Float(string='Target for Period', required=True, default=0.0)
    achievement = fields.Float(string='Actual Achievement', required=True, default=0.0)
    progress_percentage = fields.Float(
        string='Progress (%)', compute='_compute_percentage', store=True)
    unit = fields.Char(string='Unit', default='units')

    task_status = fields.Selection([
        ('pending', 'Pending'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'), ('on_hold', 'On Hold'),
        ('blocked', 'Blocked'), ('cancelled', 'Cancelled'),
    ], string='Task Status', required=True, default='completed', index=True)
    completion_date = fields.Date(string='Completion Date')
    notes = fields.Text(string='Notes / Justification')

    state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Submitted'),
        ('approved', 'Approved'), ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, index=True)

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True)

    @api.depends('kra_id', 'kpi_id')
    def _compute_hierarchy(self):
        for entry in self:
            if entry.kpi_id:
                entry.department_id = entry.kpi_id.department_id
                entry.project_id = entry.kpi_id.project_id
            elif entry.kra_id:
                entry.department_id = entry.kra_id.department_id
                entry.project_id = entry.kra_id.project_id

    @api.depends('date')
    def _compute_period(self):
        for entry in self:
            date = fields.Date.to_date(entry.date)
            entry.day = str(date.weekday()) if date else False
            entry.week_start = date - timedelta(days=date.weekday()) if date else False
            entry.month_start = date.replace(day=1) if date else False

    @api.depends('achievement', 'target')
    def _compute_percentage(self):
        for entry in self:
            percentage = (entry.achievement / entry.target * 100) if entry.target else 0.0
            entry.progress_percentage = min(max(percentage, 0.0), 100.0)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})
