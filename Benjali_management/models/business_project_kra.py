from datetime import timedelta
import calendar

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, UserError



class BusinessProjectKRAStage(models.Model):
    _name = 'business.project.kra.stage'
    _description = 'Scope Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    code = fields.Selection([
        ('new', 'New'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ], string='Stage Code', required=True)
    folded = fields.Boolean(string='Folded in Kanban', default=False)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')


class BusinessProjectKPIStage(models.Model):
    _name = 'business.project.kpi.stage'
    _description = 'Task Stage'
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
    _description = 'Project Scope'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, sequence, id desc'

    name = fields.Char(string='Scope Name', required=True, tracking=True)
    reference = fields.Char(string='Scope Code', required=True, copy=False,
                            default='New', index=True)

    project_id = fields.Many2one(
        'business.project', string='Project', required=True,
        ondelete='cascade', index=True, tracking=True,
        help='Project this Scope belongs to.')
    department_id = fields.Many2one(
        'hr.department', string='Department', required=False, index=True,
        compute='_compute_department_id', store=True, readonly=False,
        help='Department responsible for this Scope.')
    company_id = fields.Many2one(
        'res.company', string='Company', related='project_id.company_id',
        store=True, readonly=True)
    approval_pending = fields.Boolean(
        string='Approval Pending', default=False, copy=False, tracking=True)
    approval_status = fields.Char(
        string='Approval Status', compute='_compute_approval_status', store=True)

    @api.depends('approval_pending')
    def _compute_approval_status(self):
        for rec in self:
            rec.approval_status = 'Approval Pending' if rec.approval_pending else False

    responsible_user_id = fields.Many2one(
        'res.users', string='Responsible User', index=True,
        compute='_compute_responsible_user_id', store=True, readonly=False, tracking=True,
        help='Project Responsible person (Team Lead) for this project and Scope.')
    project_responsible_id = fields.Many2one(
        'res.users', string='Project Responsible',
        related='responsible_user_id', readonly=False)
    project_manager_id = fields.Many2one(
        'res.users', string='Project Manager',
        related='project_id.project_manager_id', store=True, readonly=True,
        help='Project Manager in charge of this project.')
    user_id = fields.Many2one(
        'res.users', string='Assigned User',
        related='responsible_user_id', store=True, readonly=False, index=True)

    @api.depends('project_id', 'project_id.responsible_user_id')
    def _compute_responsible_user_id(self):
        for kra in self:
            if kra.project_id and kra.project_id.responsible_user_id:
                kra.responsible_user_id = kra.project_id.responsible_user_id
            elif not kra.responsible_user_id:
                kra.responsible_user_id = False

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            if self.project_id.responsible_user_id:
                self.responsible_user_id = self.project_id.responsible_user_id
            if self.project_id.department_id:
                self.department_id = self.project_id.department_id

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
        ('cancelled', 'Cancelled'),
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
            ('on_hold', ['on_hold', 'hold', 'paused', 'postponed'], 'On Hold', 40, False, 'KRA is temporarily paused'),
            ('cancelled', ['cancelled', 'cancel'], 'Cancelled', 50, True, 'KRA is cancelled'),
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
            [('active', '=', True), ('code', 'in', ['new', 'ongoing', 'completed', 'on_hold', 'cancelled'])],
            order='sequence asc, id asc'
        )
    priority = fields.Selection([
        ('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Very High'),
    ], string='Priority', default='0', index=True)
    active = fields.Boolean(string='Active', default=True)

    start_date = fields.Date(
        string='Start Date', default=fields.Date.context_today, index=True, tracking=True)
    completed_date = fields.Date(
        string='Completed Date', index=True, tracking=True)
    end_date = fields.Date(
        string='End Date', related='completed_date', readonly=False, store=True)
    deadline = fields.Date(
        string='Deadline', index=True, tracking=True)
    is_today = fields.Boolean(
        string="Today's Scope", compute='_compute_period_flags', search='_search_is_today')
    is_tomorrow = fields.Boolean(
        string="Tomorrow's Scope", compute='_compute_period_flags', search='_search_is_tomorrow')
    is_this_week = fields.Boolean(
        string="This Week's Scope", compute='_compute_period_flags', search='_search_is_this_week')
    is_overdue = fields.Boolean(
        string="Overdue Scope", compute='_compute_period_flags', search='_search_is_overdue')

    @api.onchange('start_date')
    def _onchange_start_date(self):
        today = fields.Date.context_today(self)
        if self.start_date:
            if self.start_date < today:
                self.start_date = today
                return {
                    'warning': {
                        'title': _("Invalid Start Date"),
                        'message': _("Start Date cannot be a previous date. Only today's date or future dates are allowed."),
                    }
                }
        if self.completed_date and self.start_date and self.completed_date < self.start_date:
            self.completed_date = self.start_date

    @api.onchange('completed_date')
    def _onchange_completed_date(self):
        if self.completed_date and self.start_date and self.completed_date < self.start_date:
            self.completed_date = self.start_date
            return {
                'warning': {
                    'title': _("Invalid Completed Date"),
                    'message': _("Completed Date must be greater than or equal to Start Date."),
                }
            }

    def init(self):
        super().init()
        cr = self.env.cr
        if tools.sql.column_exists(cr, 'business_project_kra', 'completed_date') and \
                tools.sql.column_exists(cr, 'business_project_kra', 'start_date'):
            cr.execute("""
                UPDATE business_project_kra
                SET completed_date = start_date
                WHERE completed_date IS NOT NULL AND start_date IS NOT NULL AND completed_date < start_date;
            """)
        if tools.sql.column_exists(cr, 'business_project_kra', 'end_date') and \
                tools.sql.column_exists(cr, 'business_project_kra', 'start_date'):
            cr.execute("""
                UPDATE business_project_kra
                SET end_date = start_date
                WHERE end_date IS NOT NULL AND start_date IS NOT NULL AND end_date < start_date;
            """)

    @api.constrains('start_date', 'completed_date')
    def _check_dates_consistency(self):
        if not self.env.registry.ready or self.env.context.get('install_mode') or self.env.context.get('upgrade_mode'):
            return
        for kra in self:
            if kra.start_date:
                if kra.completed_date and kra.completed_date < kra.start_date:
                    raise ValidationError(_("Completed Date (%s) must be greater than or equal to Start Date (%s).") % (kra.completed_date, kra.start_date))

    def _compute_period_flags(self):
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        for kra in self:
            s_date = kra.start_date or (kra.create_date.date() if kra.create_date else today)
            e_date = kra.deadline or kra.completed_date or kra.end_date or s_date
            kra.is_today = bool(s_date and e_date and s_date <= today <= e_date)
            kra.is_tomorrow = bool(s_date and e_date and s_date <= tomorrow <= e_date)
            kra.is_this_week = bool(s_date and e_date and s_date <= sun and e_date >= mon)
            kra.is_overdue = bool((kra.deadline or kra.completed_date or kra.end_date) and (kra.deadline or kra.completed_date or kra.end_date) < today and kra.state not in ('completed', 'cancelled'))

    def _search_is_today(self, operator, value):
        today = fields.Date.context_today(self)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return ['|', '&', ('start_date', '<=', today), ('end_date', '>=', today), ('start_date', '=', today)]
        return ['|', ('start_date', '>', today), '&', ('end_date', '!=', False), ('end_date', '<', today)]

    def _search_is_tomorrow(self, operator, value):
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return ['|', '&', ('start_date', '<=', tomorrow), ('end_date', '>=', tomorrow), ('start_date', '=', tomorrow)]
        return ['|', ('start_date', '>', tomorrow), '&', ('end_date', '!=', False), ('end_date', '<', tomorrow)]

    def _search_is_this_week(self, operator, value):
        today = fields.Date.context_today(self)
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return ['|', '&', ('start_date', '<=', sun), ('end_date', '>=', mon), '&', ('start_date', '>=', mon), ('start_date', '<=', sun)]
        return ['|', ('start_date', '>', sun), '&', ('end_date', '!=', False), ('end_date', '<', mon)]

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return [('end_date', '!=', False), ('end_date', '<', today), ('state', '!=', 'completed')]
        return ['|', ('end_date', '=', False), '|', ('end_date', '>=', today), ('state', '=', 'completed')]

    description = fields.Text(string='Description / Strategic Objective')
    objective = fields.Text(string='Objective Details')
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True)

    # Tasks
    kpi_ids = fields.One2many(
        'business.project.kpi', 'kra_id', string='Tasks', copy=True)
    entry_ids = fields.One2many(
        'business.project.kra.entry', 'kra_id', string='Performance Entries', copy=False)
    task_ids = fields.One2many('project.task', 'kra_id', string='Project Tasks')
    employee_ids = fields.Many2many(
        'res.users', 'business_project_kra_employee_rel', 'kra_id', 'user_id',
        string='Assigned Employees', compute='_compute_assigned_employees', store=True)

    # Metrics
    kpi_count = fields.Integer(compute='_compute_kpi_metrics', string='Total Tasks', store=True)
    completed_kpi_count = fields.Integer(compute='_compute_kpi_metrics', string='Completed Tasks', store=True)

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
    task_count = fields.Integer(compute='_compute_task_metrics', string='Task Count')
    completed_task_count = fields.Integer(compute='_compute_task_metrics', string='Completed Task Count')
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
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if not vals.get('reference') or vals.get('reference') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('business.project.kra') or 'KRA'
            if not vals.get('start_date'):
                vals['start_date'] = today
            elif fields.Date.to_date(vals['start_date']) < today:
                raise ValidationError(_("Start Date cannot be a previous date. Only today's date or future dates are allowed."))
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
            if vals.get('state') == 'completed' and not vals.get('completed_date'):
                vals['completed_date'] = today
        records = super().create(vals_list)
        for kra in records:
            kra.action_generate_daily_repeating_kpis()
        return records

    def init(self):
        super().init()
        try:
            with self.env.cr.savepoint():
                self._normalize_stages()
                self.env.cr.execute("""
                    UPDATE business_project_kra 
                    SET state = CASE 
                        WHEN state IN ('not_started', 'draft') THEN 'new'
                        WHEN state IN ('active', 'in_progress') THEN 'ongoing'
                        WHEN state = 'cancelled' THEN 'cancelled'
                        WHEN state IN ('postponed', 'on_hold') THEN 'on_hold'
                        WHEN state = 'completed' THEN 'completed'
                        ELSE 'new'
                    END
                    WHERE state NOT IN ('new', 'ongoing', 'completed', 'on_hold', 'cancelled') OR state IS NULL;
                """)
                self.env.cr.execute("""
                    UPDATE business_project_kra kra
                    SET stage_id = st.id
                    FROM business_project_kra_stage st
                    WHERE kra.state = st.code AND (kra.stage_id IS NULL OR kra.stage_id != st.id);
                """)
        except Exception:
            pass

    def write(self, vals):
        is_tl = (
            self.env.user.has_group('Benjali_management.group_Team_lead') or
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin() or
            self.env.su
        )
        is_pm = (
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin() or
            self.env.su
        )
        today = fields.Date.context_today(self)
        if 'start_date' in vals and vals.get('start_date'):
            start_date_val = fields.Date.to_date(vals['start_date'])
            if start_date_val < today:
                raise ValidationError(_("Start Date cannot be a previous date. Only today's date or future dates are allowed."))

        Stage = self.env['business.project.kra.stage']
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
                if not is_tl:
                    raise UserError("Only the Team Lead / Project Responsible can complete or submit Scope completion.")
                if not is_pm:
                    raise UserError("Completing a Scope requires approval from the Project Manager. Please click 'Mark Completed' to submit an approval request.")
                if not vals.get('completed_date'):
                    vals['completed_date'] = today
            elif vals['state'] == 'new':
                if 'completed_date' not in vals:
                    vals['completed_date'] = False

        return super().write(vals)

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
        is_tl = (
            self.env.user.has_group('Benjali_management.group_Team_lead') or
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin()
        )
        if not is_tl:
            raise UserError("Only the Team Lead / Project Responsible can complete or submit Scope completion.")

        is_pm = (
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin()
        )
        if is_pm:
            self._do_mark_completed()
            return

        for kra in self:
            if kra.approval_pending:
                raise UserError(f'An approval request for "{kra.name}" has already been submitted to the Project Manager and is pending approval.')

            approver = kra.project_id.project_manager_id if kra.project_id else False
            if not approver or approver == self.env.user:
                pm_users = self.env['res.users'].search([('share', '=', False)]).filtered(
                    lambda u: u.has_group('Benjali_management.group_project_manager')
                )
                if pm_users:
                    other_pms = pm_users.filtered(lambda u: u != self.env.user)
                    approver = other_pms[0] if other_pms else pm_users[0]

            if not approver:
                approver = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user

            approval = self.env['business.project.approval'].create({
                'project_id': kra.project_id.id if kra.project_id else False,
                'kra_id': kra.id,
                'approval_type': 'kra_completion',
                'approver_id': approver.id,
                'requested_by': self.env.user.id,
                'requires_approval': True,
                'company_id': kra.company_id.id if kra.company_id else self.env.company.id,
            })
            kra.write({'approval_pending': True})
            kra.message_post(
                body=(
                    f'Scope completion approval request <b>{approval.name}</b> sent to '
                    f'Project Manager <b>{approver.name}</b> by {self.env.user.name}.'
                )
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Approval Requested',
                'message': 'Scope completion approval request has been sent to the Project Manager.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _do_mark_completed(self):
        today = fields.Date.context_today(self)
        st = self.env['business.project.kra.stage'].search([('code', '=', 'completed')], limit=1)
        vals = {
            'state': 'completed',
            'approval_pending': False,
            'completed_date': today,
        }
        if st:
            vals['stage_id'] = st.id
        self.sudo().write(vals)
        for kra in self:
            pending_approvals = self.env['business.project.approval'].search([
                ('kra_id', '=', kra.id),
                ('approval_type', '=', 'kra_completion'),
                ('state', '=', 'pending'),
            ])
            if pending_approvals:
                pending_approvals.sudo().write({
                    'state': 'approved',
                    'approval_date': fields.Datetime.now(),
                })

    def action_set_on_hold(self):
        st = self.env['business.project.kra.stage'].search([('code', '=', 'on_hold')], limit=1)
        vals = {'state': 'on_hold'}
        if st:
            vals['stage_id'] = st.id
        self.write(vals)

    def action_set_cancelled(self):
        st = self.env['business.project.kra.stage'].search([('code', '=', 'cancelled')], limit=1)
        vals = {'state': 'cancelled'}
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
    _description = 'Project Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date desc, sequence, id desc'

    name = fields.Char(string='Task Name', required=True, tracking=True)
    code = fields.Char(string='Task Code', copy=False, default='New')
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Very High'),
    ], string='Priority', default='0', index=True, tracking=True)
    kra_id = fields.Many2one(
        'business.project.kra', string='Scope', required=True,
        ondelete='cascade', index=True, tracking=True)

    project_id = fields.Many2one(
        'business.project', string='Project',
        compute='_compute_kra_details', store=True, readonly=False, index=True, tracking=True,
        help='Project automatically filled when Scope is chosen.')
    responsible_user_id = fields.Many2one(
        'res.users', string='Responsible User',
        compute='_compute_kra_details', store=True, readonly=False, index=True, tracking=True,
        help='Project Responsible person (Team Lead) for this Task.')
    project_responsible_id = fields.Many2one(
        'res.users', string='Project Responsible',
        related='responsible_user_id', readonly=False)
    project_manager_id = fields.Many2one(
        'res.users', string='Project Manager',
        related='project_id.project_manager_id', store=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department', string='Department',
        compute='_compute_kra_details', store=True, readonly=False, index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='project_id.company_id',
        store=True, readonly=True)
    approval_pending = fields.Boolean(
        string='Approval Pending', default=False, copy=False, tracking=True)
    approval_status = fields.Char(
        string='Approval Status', compute='_compute_approval_status', store=True)

    @api.depends('approval_pending')
    def _compute_approval_status(self):
        for rec in self:
            rec.approval_status = 'Approval Pending' if rec.approval_pending else False

    employee_ids = fields.Many2many(
        'res.users', 'business_project_kpi_user_rel', 'kpi_id', 'user_id',
        string='Assigned Employees', tracking=True)
    employee_id = fields.Many2one(
        'res.users', string='Assigned Employee',
        compute='_compute_employee_id', inverse='_inverse_employee_id',
        store=True, index=True, tracking=True)

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
        string='Repeating Task Alias', related='is_daily_repeating', readonly=False)
    recurring_template_id = fields.Many2one(
        'business.project.kpi', string='Repeating Source Template',
        ondelete='set null', index=True)

    # Subtasks
    subtask_ids = fields.One2many(
        'business.project.kpi.subtask', 'kpi_id', string='Subtasks')
    subtask_count = fields.Integer(
        string='Subtask Count', compute='_compute_subtask_metrics')
    subtask_completed_count = fields.Integer(
        string='Completed Subtasks', compute='_compute_subtask_metrics')

    # Progress bar with sliding option up to 100 (auto-calculated from subtasks if present)
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_progress',
        store=True,
        readonly=False,
        tracking=True)

    # Timesheets
    timesheet_ids = fields.One2many(
        'account.analytic.line', 'kpi_id', string='Timesheets')
    total_hours_spent = fields.Float(
        string='Recorded Hours', compute='_compute_total_hours_spent', store=True)

    # Date & Period
    date = fields.Date(
        string='Date', default=fields.Date.context_today, required=True, index=True)
    start_date = fields.Date(
        string='Start Date', default=fields.Date.context_today, index=True, tracking=True)
    completed_date = fields.Date(
        string='Completed Date', index=True, tracking=True)
    end_date = fields.Date(
        string='End Date', related='completed_date', readonly=False, store=True)
    date_completed = fields.Date(
        string='Completed Date Reference', related='completed_date', readonly=False)
    deadline = fields.Date(
        string='Deadline', index=True, tracking=True)
    date_deadline = fields.Date(
        string='Deadline Reference', related='deadline', readonly=False)
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
    is_tomorrow = fields.Boolean(
        string="Tomorrow's Task", compute='_compute_period_flags', search='_search_is_tomorrow')
    is_this_week = fields.Boolean(
        string="This Week's Task", compute='_compute_period_flags', search='_search_is_this_week')
    is_this_month = fields.Boolean(
        string="This Month's Task", compute='_compute_period_flags', search='_search_is_this_month')
    is_overdue = fields.Boolean(
        string="Overdue Task", compute='_compute_period_flags', search='_search_is_overdue')

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

    @api.depends('kra_id', 'kra_id.project_id', 'kra_id.responsible_user_id', 'kra_id.department_id')
    def _compute_kra_details(self):
        for kpi in self:
            if kpi.kra_id:
                kpi.project_id = kpi.kra_id.project_id
                kpi.responsible_user_id = kpi.kra_id.responsible_user_id or (kpi.kra_id.project_id and kpi.kra_id.project_id.responsible_user_id)
                kpi.department_id = kpi.kra_id.department_id
            else:
                if not kpi.project_id:
                    kpi.project_id = False
                if not kpi.responsible_user_id:
                    kpi.responsible_user_id = False
                if not kpi.department_id:
                    kpi.department_id = False

    @api.onchange('kra_id')
    def _onchange_kra_id(self):
        if self.kra_id:
            self.project_id = self.kra_id.project_id
            self.responsible_user_id = self.kra_id.responsible_user_id or (self.kra_id.project_id and self.kra_id.project_id.responsible_user_id)
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

    @api.depends('timesheet_ids.unit_amount')
    def _compute_total_hours_spent(self):
        for kpi in self:
            kpi.total_hours_spent = sum(kpi.timesheet_ids.mapped('unit_amount'))

    @api.depends('subtask_ids', 'subtask_ids.state')
    def _compute_subtask_metrics(self):
        for kpi in self:
            subtasks = kpi.subtask_ids
            kpi.subtask_count = len(subtasks)
            kpi.subtask_completed_count = len(subtasks.filtered(lambda s: s.state == 'completed'))

    @api.depends('subtask_ids.progress', 'subtask_ids.state', 'state')
    def _compute_progress(self):
        for kpi in self:
            if kpi.subtask_ids:
                total_prog = sum(kpi.subtask_ids.mapped('progress'))
                kpi.progress = round(total_prog / len(kpi.subtask_ids), 2)
            else:
                if kpi.state == 'completed':
                    kpi.progress = 100.0
                elif kpi.state == 'not_started' and not kpi.progress:
                    kpi.progress = 0.0
                else:
                    kpi.progress = kpi.progress or 0.0

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

    @api.onchange('start_date')
    def _onchange_start_date(self):
        today = fields.Date.context_today(self)
        if self.start_date:
            if self.start_date < today:
                self.start_date = today
                self.date = today
                return {
                    'warning': {
                        'title': _("Invalid Start Date"),
                        'message': _("Start Date cannot be a previous date. Only today's date or future dates are allowed."),
                    }
                }
            self.date = self.start_date
        if self.completed_date and self.start_date and self.completed_date < self.start_date:
            self.completed_date = self.start_date

    @api.onchange('completed_date')
    def _onchange_completed_date(self):
        if self.completed_date and self.start_date and self.completed_date < self.start_date:
            self.completed_date = self.start_date
            return {
                'warning': {
                    'title': _("Invalid Completed Date"),
                    'message': _("Completed Date must be greater than or equal to Start Date."),
                }
            }

    def init(self):
        super().init()
        cr = self.env.cr
        if tools.sql.column_exists(cr, 'business_project_kpi', 'completed_date') and \
                tools.sql.column_exists(cr, 'business_project_kpi', 'start_date'):
            cr.execute("""
                UPDATE business_project_kpi
                SET completed_date = start_date
                WHERE completed_date IS NOT NULL AND start_date IS NOT NULL AND completed_date < start_date;
            """)
        if tools.sql.column_exists(cr, 'business_project_kpi', 'end_date') and \
                tools.sql.column_exists(cr, 'business_project_kpi', 'start_date'):
            cr.execute("""
                UPDATE business_project_kpi
                SET end_date = start_date
                WHERE end_date IS NOT NULL AND start_date IS NOT NULL AND end_date < start_date;
            """)

    @api.constrains('start_date', 'completed_date')
    def _check_dates_consistency(self):
        if not self.env.registry.ready or self.env.context.get('install_mode') or self.env.context.get('upgrade_mode'):
            return
        for kpi in self:
            if kpi.start_date:
                if kpi.completed_date and kpi.completed_date < kpi.start_date:
                    raise ValidationError(_("Completed Date (%s) must be greater than or equal to Start Date (%s).") % (kpi.completed_date, kpi.start_date))

    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        if self.stage_id and self.stage_id.code:
            self.state = self.stage_id.code
            if self.stage_id.code == 'completed':
                if self.progress < 100.0:
                    self.progress = 100.0
                if not self.completed_date:
                    self.completed_date = fields.Date.context_today(self)
            elif self.stage_id.code == 'not_started':
                self.completed_date = False

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'completed':
            if self.progress < 100.0:
                self.progress = 100.0
            if not self.completed_date:
                self.completed_date = fields.Date.context_today(self)
        elif self.state == 'not_started':
            if self.progress > 0.0:
                self.progress = 0.0
            self.completed_date = False

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
        tomorrow = today + timedelta(days=1)
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        m_start = today.replace(day=1)
        next_m = (m_start + timedelta(days=32)).replace(day=1)
        for kpi in self:
            kpi.is_today = (kpi.date == today)
            kpi.is_tomorrow = (kpi.date == tomorrow)
            kpi.is_this_week = (mon <= kpi.date <= sun) if kpi.date else False
            kpi.is_this_month = (m_start <= kpi.date < next_m) if kpi.date else False
            kpi.is_overdue = bool(kpi.date and kpi.date < today and kpi.state not in ('completed', 'cancelled'))

    def _search_is_today(self, operator, value):
        today = fields.Date.context_today(self)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return [('date', '=', today)]
        return [('date', '!=', today)]

    def _search_is_tomorrow(self, operator, value):
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return [('date', '=', tomorrow)]
        return [('date', '!=', tomorrow)]

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

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return [('date', '!=', False), ('date', '<', today), ('state', 'not in', ('completed', 'cancelled'))]
        return ['|', ('date', '=', False), '|', ('date', '>=', today), ('state', 'in', ('completed', 'cancelled'))]

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
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if not vals.get('code') or vals.get('code') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('business.project.kpi') or 'KPI'
            if not vals.get('start_date'):
                vals['start_date'] = today
            elif fields.Date.to_date(vals['start_date']) < today:
                raise ValidationError(_("Start Date cannot be a previous date. Only today's date or future dates are allowed."))
            if not vals.get('date'):
                vals['date'] = vals['start_date']
            elif not vals.get('start_date'):
                vals['start_date'] = vals['date']

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
                if not vals.get('completed_date'):
                    vals['completed_date'] = today
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
        is_manager = (
            self.env.user.has_group('Benjali_management.group_Team_lead') or
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin() or
            self.env.su
        )
        if not is_manager:
            for kpi in self:
                is_assigned = (self.env.user in kpi.employee_ids or kpi.employee_id == self.env.user)
                if not is_assigned:
                    raise UserError(f'You cannot modify KPI "{kpi.name}" because it is not assigned to you.')
        Stage = self.env['business.project.kpi.stage']
        if 'stage_id' in vals and 'state' not in vals:
            st = Stage.browse(vals['stage_id'])
            if st and st.code:
                vals['state'] = st.code
        elif 'state' in vals and 'stage_id' not in vals:
            st = Stage.search([('code', '=', vals['state'])], limit=1)
            if st:
                vals['stage_id'] = st.id

        if 'start_date' in vals:
            if vals.get('start_date') and vals['start_date'] < fields.Date.context_today(self):
                raise ValidationError(_("Start Date cannot be a previous date. Only today's date or future dates are allowed."))
            if 'date' not in vals:
                vals['date'] = vals['start_date']
        elif 'date' in vals and 'start_date' not in vals:
            vals['start_date'] = vals['date']

        if 'state' in vals:
            if vals['state'] == 'completed':
                if not is_manager:
                    raise UserError("Completing a KPI requires approval from the Team Lead. Please click 'Mark Completed' to submit an approval request.")
                if not vals.get('completed_date'):
                    vals['completed_date'] = fields.Date.context_today(self)
                if 'daily_achievement' not in vals:
                    vals['daily_achievement'] = 1.0
                if 'progress' not in vals:
                    vals['progress'] = 100.0
            elif vals['state'] == 'not_started':
                if 'completed_date' not in vals:
                    vals['completed_date'] = False
                if 'daily_achievement' not in vals:
                    vals['daily_achievement'] = 0.0
                if 'progress' not in vals:
                    vals['progress'] = 0.0
            elif vals['state'] in ('on_hold', 'cancelled', 'postponed') and 'daily_achievement' not in vals:
                vals['daily_achievement'] = 0.0
            elif vals['state'] == 'in_progress':
                if 'progress' not in vals and not any(self.mapped('progress')):
                    vals['progress'] = 25.0

        if 'progress' in vals:
            if vals['progress'] >= 100.0 and vals.get('state') not in ('completed', 'cancelled'):
                if not is_manager:
                    raise UserError("Completing a KPI requires approval from the Team Lead. Please click 'Mark Completed' to submit an approval request.")
                vals['state'] = 'completed'
                if not vals.get('completed_date'):
                    vals['completed_date'] = fields.Date.context_today(self)
                st = Stage.search([('code', '=', 'completed')], limit=1)
                if st:
                    vals['stage_id'] = st.id
            elif vals['progress'] <= 0.0 and vals.get('state') == 'completed':
                vals['state'] = 'not_started'
                if 'completed_date' not in vals:
                    vals['completed_date'] = False
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
        try:
            with self.env.cr.savepoint():
                self._normalize_stages()
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
        is_manager = (
            self.env.user.has_group('Benjali_management.group_Team_lead') or
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin()
        )
        if is_manager:
            self._do_mark_completed()
            return

        for kpi in self:
            if not is_manager:
                is_assigned = (self.env.user in kpi.employee_ids or kpi.employee_id == self.env.user)
                if not is_assigned:
                    raise UserError(f'You cannot complete KPI "{kpi.name}" because it is not assigned to you. You can only complete your own assigned tasks.')

            if kpi.approval_pending:
                raise UserError(f'An approval request for "{kpi.name}" has already been submitted to the Team Lead and is pending approval.')

            approver = (
                kpi.responsible_user_id or
                (kpi.kra_id and kpi.kra_id.responsible_user_id) or
                (kpi.project_id and kpi.project_id.responsible_user_id) or
                kpi.project_manager_id
            )
            if not approver or approver == self.env.user:
                tl_users = self.env['res.users'].search([('share', '=', False)]).filtered(
                    lambda u: u.has_group('Benjali_management.group_Team_lead')
                )
                if tl_users:
                    other_tls = tl_users.filtered(lambda u: u != self.env.user)
                    approver = other_tls[0] if other_tls else tl_users[0]

            if not approver:
                approver = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user

            approval = self.env['business.project.approval'].create({
                'project_id': kpi.project_id.id if kpi.project_id else False,
                'kra_id': kpi.kra_id.id if kpi.kra_id else False,
                'kpi_id': kpi.id,
                'approval_type': 'kpi_completion',
                'approver_id': approver.id,
                'requested_by': self.env.user.id,
                'requires_approval': True,
                'company_id': kpi.company_id.id if kpi.company_id else self.env.company.id,
            })
            kpi.sudo().write({'approval_pending': True})
            kpi.message_post(
                body=(
                    f'KPI completion approval request <b>{approval.name}</b> sent to '
                    f'Project Responsible <b>{approver.name}</b> by {self.env.user.name}.'
                )
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Approval Requested',
                'message': 'KPI completion approval request has been sent to the Project Responsible.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _do_mark_completed(self):
        st = self.env['business.project.kpi.stage'].search([('code', '=', 'completed')], limit=1)
        today = fields.Date.context_today(self)
        vals = {
            'state': 'completed',
            'daily_achievement': 1.0,
            'progress': 100.0,
            'approval_pending': False,
            'completed_date': today,
        }
        if st:
            vals['stage_id'] = st.id
        for kpi in self:
            kpi.sudo().write(vals)
        for kpi in self:
            kpi.subtask_ids.filtered(lambda s: s.state != 'completed').sudo().write({
                'state': 'completed',
                'progress': 100.0,
                'approval_pending': False,
            })
            pending_approvals = self.env['business.project.approval'].search([
                ('kpi_id', '=', kpi.id),
                ('approval_type', '=', 'kpi_completion'),
                ('state', '=', 'pending'),
            ])
            if pending_approvals:
                pending_approvals.sudo().write({
                    'state': 'approved',
                    'approval_date': fields.Datetime.now(),
                })

    def action_view_subtasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Subtasks - {self.name}',
            'res_model': 'business.project.kpi.subtask',
            'view_mode': 'list,form',
            'domain': [('kpi_id', '=', self.id)],
            'context': {
                'default_kpi_id': self.id,
                'default_kra_id': self.kra_id.id if self.kra_id else False,
                'default_project_id': self.project_id.id if self.project_id else False,
            },
        }

    def action_mark_all_subtasks_complete(self):
        is_manager = (
            self.env.user.has_group('Benjali_management.group_Team_lead') or
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin()
        )
        if not is_manager:
            raise UserError("Only the Team Lead / Project Responsible can mark all subtasks complete at once.")
        for kpi in self:
            kpi.subtask_ids.write({'state': 'completed', 'progress': 100.0})
            kpi.action_set_completed()

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


class BusinessProjectKPISubtask(models.Model):
    _name = 'business.project.kpi.subtask'
    _description = 'Task Subtask'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id desc'

    name = fields.Char(string='Subtask Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)
    kpi_id = fields.Many2one(
        'business.project.kpi', string='Task', required=True,
        ondelete='cascade', index=True, tracking=True)
    kra_id = fields.Many2one(
        'business.project.kra', string='Scope', related='kpi_id.kra_id',
        store=True, readonly=True)
    project_id = fields.Many2one(
        'business.project', string='Project', related='kpi_id.project_id',
        store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='project_id.company_id',
        store=True, readonly=True)
    responsible_user_id = fields.Many2one(
        'res.users', string='Project Responsible', related='kpi_id.responsible_user_id',
        store=True, readonly=True)
    approval_pending = fields.Boolean(
        string='Approval Pending', default=False, copy=False, tracking=True)
    approval_status = fields.Char(
        string='Approval Status', compute='_compute_approval_status', store=True)

    @api.depends('approval_pending')
    def _compute_approval_status(self):
        for rec in self:
            rec.approval_status = 'Approval Pending' if rec.approval_pending else False
    user_id = fields.Many2one(
        'res.users', string='Assigned User', default=lambda self: self.env.user,
        index=True, tracking=True)
    start_date = fields.Date(
        string='Start Date', default=fields.Date.context_today, tracking=True)
    completed_date = fields.Date(string='Completed Date', tracking=True)
    end_date = fields.Date(
        string='End Date', related='completed_date', readonly=False, store=True)
    deadline = fields.Date(string='Deadline', tracking=True)
    is_today = fields.Boolean(
        string="Today's Subtask", compute='_compute_period_flags', search='_search_is_today')
    is_tomorrow = fields.Boolean(
        string="Tomorrow's Subtask", compute='_compute_period_flags', search='_search_is_tomorrow')
    is_this_week = fields.Boolean(
        string="This Week's Subtask", compute='_compute_period_flags', search='_search_is_this_week')
    is_overdue = fields.Boolean(
        string="Overdue Subtask", compute='_compute_period_flags', search='_search_is_overdue')

    def _compute_period_flags(self):
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        for sub in self:
            s_date = sub.start_date or today
            e_date = sub.end_date or s_date
            sub.is_today = bool(s_date and e_date and s_date <= today <= e_date)
            sub.is_tomorrow = bool(s_date and e_date and s_date <= tomorrow <= e_date)
            sub.is_this_week = bool(s_date and e_date and s_date <= sun and e_date >= mon)
            sub.is_overdue = bool(sub.end_date and sub.end_date < today and sub.state not in ('completed', 'cancelled'))

    def _search_is_today(self, operator, value):
        today = fields.Date.context_today(self)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return ['|', '&', ('start_date', '<=', today), ('end_date', '>=', today), ('start_date', '=', today)]
        return ['|', ('start_date', '>', today), '&', ('end_date', '!=', False), ('end_date', '<', today)]

    def _search_is_tomorrow(self, operator, value):
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return ['|', '&', ('start_date', '<=', tomorrow), ('end_date', '>=', tomorrow), ('start_date', '=', tomorrow)]
        return ['|', ('start_date', '>', tomorrow), '&', ('end_date', '!=', False), ('end_date', '<', tomorrow)]

    def _search_is_this_week(self, operator, value):
        today = fields.Date.context_today(self)
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return ['|', '&', ('start_date', '<=', sun), ('end_date', '>=', mon), '&', ('start_date', '>=', mon), ('start_date', '<=', sun)]
        return ['|', ('start_date', '>', sun), '&', ('end_date', '!=', False), ('end_date', '<', mon)]

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        if (operator in ('=', '!=') and value) or (operator in ('!=', '<>') and not value):
            return [('end_date', '!=', False), ('end_date', '<', today), ('state', 'not in', ('completed', 'cancelled'))]
        return ['|', ('end_date', '=', False), '|', ('end_date', '>=', today), ('state', 'in', ('completed', 'cancelled'))]
    progress = fields.Float(
        string='Progress (%)', default=0.0, tracking=True)
    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='not_started', required=True, index=True, tracking=True)
    description = fields.Text(string='Notes / Instructions')
    active = fields.Boolean(default=True)

    @api.onchange('progress')
    def _onchange_progress(self):
        if self.progress >= 100.0:
            self.state = 'completed'
            self.progress = 100.0
        elif 0.0 < self.progress < 100.0 and self.state in ('not_started', 'completed'):
            self.state = 'in_progress'
        elif self.progress <= 0.0 and self.state == 'completed':
            self.state = 'not_started'
            self.progress = 0.0

    @api.onchange('start_date')
    def _onchange_start_date(self):
        today = fields.Date.context_today(self)
        if self.start_date:
            if self.start_date < today:
                self.start_date = today
                return {
                    'warning': {
                        'title': _("Invalid Start Date"),
                        'message': _("Start Date cannot be a previous date. Only today's date or future dates are allowed."),
                    }
                }
        if self.completed_date and self.start_date and self.completed_date < self.start_date:
            self.completed_date = self.start_date

    @api.onchange('completed_date')
    def _onchange_completed_date(self):
        if self.completed_date and self.start_date and self.completed_date < self.start_date:
            self.completed_date = self.start_date
            return {
                'warning': {
                    'title': _("Invalid Completed Date"),
                    'message': _("Completed Date must be greater than or equal to Start Date."),
                }
            }

    def init(self):
        super().init()
        cr = self.env.cr
        if tools.sql.column_exists(cr, 'business_project_subtask', 'completed_date') and \
                tools.sql.column_exists(cr, 'business_project_subtask', 'start_date'):
            cr.execute("""
                UPDATE business_project_subtask
                SET completed_date = start_date
                WHERE completed_date IS NOT NULL AND start_date IS NOT NULL AND completed_date < start_date;
            """)
        if tools.sql.column_exists(cr, 'business_project_subtask', 'end_date') and \
                tools.sql.column_exists(cr, 'business_project_subtask', 'start_date'):
            cr.execute("""
                UPDATE business_project_subtask
                SET end_date = start_date
                WHERE end_date IS NOT NULL AND start_date IS NOT NULL AND end_date < start_date;
            """)

    @api.constrains('start_date', 'completed_date')
    def _check_dates_consistency(self):
        if not self.env.registry.ready or self.env.context.get('install_mode') or self.env.context.get('upgrade_mode'):
            return
        for sub in self:
            if sub.start_date:
                if sub.completed_date and sub.completed_date < sub.start_date:
                    raise ValidationError(_("Completed Date (%s) must be greater than or equal to Start Date (%s).") % (sub.completed_date, sub.start_date))

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'completed':
            if self.progress < 100.0:
                self.progress = 100.0
            if not self.completed_date:
                self.completed_date = fields.Date.context_today(self)
        elif self.state == 'not_started':
            if self.progress > 0.0:
                self.progress = 0.0
            self.completed_date = False

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if not vals.get('start_date'):
                vals['start_date'] = today
            elif fields.Date.to_date(vals['start_date']) < today:
                raise ValidationError(_("Start Date cannot be a previous date. Only today's date or future dates are allowed."))
            if vals.get('progress', 0.0) >= 100.0 and vals.get('state') != 'completed':
                vals['state'] = 'completed'
            elif vals.get('state') == 'completed' and vals.get('progress', 0.0) < 100.0:
                vals['progress'] = 100.0
            if vals.get('state') == 'completed':
                if not vals.get('completed_date'):
                    vals['completed_date'] = today
                if 'progress' not in vals:
                    vals['progress'] = 100.0
        return super().create(vals_list)

    def write(self, vals):
        vals_dict = dict(vals)
        is_manager = (
            self.env.user.has_group('Benjali_management.group_Team_lead') or
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin() or
            self.env.su
        )
        if 'start_date' in vals_dict and vals_dict.get('start_date'):
            if vals_dict['start_date'] < fields.Date.context_today(self):
                raise ValidationError(_("Start Date cannot be a previous date. Only today's date or future dates are allowed."))

        if not is_manager:
            for subtask in self:
                if subtask.user_id and subtask.user_id != self.env.user:
                    raise UserError(f'You cannot modify subtask "{subtask.name}" because it is assigned to {subtask.user_id.name}. You can only update your own assigned tasks.')

        if vals_dict.get('state') == 'completed':
            if not vals_dict.get('completed_date'):
                vals_dict['completed_date'] = fields.Date.context_today(self)
        elif vals_dict.get('state') == 'not_started':
            if 'completed_date' not in vals_dict:
                vals_dict['completed_date'] = False

        if ('state' in vals_dict and vals_dict['state'] == 'completed') or vals_dict.get('progress', 0.0) >= 100.0:
            if not is_manager:
                raise UserError("Completing a subtask requires approval from the Team Lead. Please click 'Mark Complete' to submit an approval request.")

        if 'progress' in vals_dict and 'state' not in vals_dict:
            if vals_dict['progress'] >= 100.0:
                vals_dict['state'] = 'completed'
        elif 'state' in vals_dict and 'progress' not in vals_dict:
            if vals_dict['state'] == 'completed':
                vals_dict['progress'] = 100.0
            elif vals_dict['state'] == 'not_started':
                vals_dict['progress'] = 0.0
        return super().write(vals_dict)

    def action_mark_complete(self):
        is_manager = (
            self.env.user.has_group('Benjali_management.group_Team_lead') or
            self.env.user.has_group('Benjali_management.group_project_manager') or
            self.env.user.has_group('Benjali_management.group_gvp') or
            self.env.user.has_group('Benjali_management.group_ceo') or
            self.env.is_admin()
        )
        if is_manager:
            self._do_mark_completed()
            return

        for subtask in self:
            if not is_manager and subtask.user_id and subtask.user_id != self.env.user:
                raise UserError(f'You cannot complete subtask "{subtask.name}" because it is assigned to {subtask.user_id.name}. You can only complete your own assigned tasks.')

            if subtask.approval_pending:
                raise UserError(f'An approval request for subtask "{subtask.name}" has already been submitted to the Team Lead and is pending approval.')

            approver = (
                subtask.responsible_user_id or
                (subtask.kpi_id and subtask.kpi_id.responsible_user_id) or
                (subtask.kra_id and subtask.kra_id.responsible_user_id) or
                (subtask.project_id and subtask.project_id.responsible_user_id) or
                (subtask.kpi_id and subtask.kpi_id.project_manager_id)
            )
            if not approver or approver == self.env.user:
                tl_users = self.env['res.users'].search([('share', '=', False)]).filtered(
                    lambda u: u.has_group('Benjali_management.group_Team_lead')
                )
                if tl_users:
                    other_tls = tl_users.filtered(lambda u: u != self.env.user)
                    approver = other_tls[0] if other_tls else tl_users[0]

            if not approver:
                approver = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user

            approval = self.env['business.project.approval'].create({
                'project_id': subtask.project_id.id if subtask.project_id else False,
                'kra_id': subtask.kra_id.id if subtask.kra_id else False,
                'kpi_id': subtask.kpi_id.id if subtask.kpi_id else False,
                'subtask_id': subtask.id,
                'approval_type': 'subtask_completion',
                'approver_id': approver.id,
                'requested_by': self.env.user.id,
                'requires_approval': True,
                'company_id': subtask.company_id.id if subtask.company_id else self.env.company.id,
            })
            subtask.sudo().write({'approval_pending': True})
            subtask.message_post(
                body=(
                    f'Subtask completion approval request <b>{approval.name}</b> sent to '
                    f'Project Responsible <b>{approver.name}</b> by {self.env.user.name}.'
                )
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Approval Requested',
                'message': 'Subtask completion approval request has been sent to the Project Responsible.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _do_mark_completed(self):
        today = fields.Date.context_today(self)
        for subtask in self:
            s_vals = {
                'state': 'completed',
                'progress': 100.0,
                'approval_pending': False,
                'completed_date': today,
            }
            subtask.sudo().write(s_vals)
        for subtask in self:
            pending_approvals = self.env['business.project.approval'].search([
                ('subtask_id', '=', subtask.id),
                ('approval_type', '=', 'subtask_completion'),
                ('state', '=', 'pending'),
            ])
            if pending_approvals:
                pending_approvals.sudo().write({
                    'state': 'approved',
                    'approval_date': fields.Datetime.now(),
                })
            kpi = subtask.kpi_id
            if kpi and kpi.subtask_ids:
                total_prog = sum(kpi.subtask_ids.mapped('progress'))
                kpi.sudo().write({'progress': round(total_prog / len(kpi.subtask_ids), 2)})
                if all(s.state == 'completed' for s in kpi.subtask_ids):
                    kpi._do_mark_completed()

    def action_mark_in_progress(self):
        for subtask in self:
            vals = {'state': 'in_progress'}
            if subtask.progress == 0.0:
                vals['progress'] = 10.0
            subtask.write(vals)

    def action_reset(self):
        self.write({
            'state': 'not_started',
            'progress': 0.0,
        })

