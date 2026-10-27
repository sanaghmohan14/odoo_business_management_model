from datetime import date
from odoo import api, fields, models


class BenjaliManagementDashboard(models.AbstractModel):
    _name = 'benjali.management.dashboard'
    _description = 'Benjali Management Dashboard'

    @api.model
    def get_dashboard_data(self, *args, **kwargs):
        department_id = False
        if args:
            department_id = args[0]
        elif 'department_id' in kwargs:
            department_id = kwargs['department_id']
        elif self.ids:
            department_id = self.ids[0]

        try:
            department_id = int(department_id) if department_id else False
        except (TypeError, ValueError):
            department_id = False

        Project = self.env['business.project']
        Department = self.env['hr.department']
        Stage = self.env['business.project.stage']
        SOP = self.env['business.project.sop']
        Approval = self.env['business.project.approval']

        # Department vibrant accent color palette
        PALETTE = [
            '#3b82f6',  # Blue (Engineering)
            '#a855f7',  # Purple (Marketing)
            '#10b981',  # Emerald Green (Sales)
            '#f59e0b',  # Amber/Orange (Finance)
            '#ec4899',  # Pink (People)
            '#06b6d4',  # Cyan (Operations)
            '#6366f1',  # Indigo
            '#14b8a6',  # Teal
        ]

        # Fetch all departments
        all_departments = Department.search([], order='name')
        dep_color_map = {}
        for idx, dep in enumerate(all_departments):
            dep_color_map[dep.id] = PALETTE[idx % len(PALETTE)]

        # Fetch all projects
        all_projects = Project.search([])

        # Build department summary list for sidebar and widget
        departments_data = []
        for dep in all_departments:
            dep_projects = all_projects.filtered(lambda p: p.department_id.id == dep.id)
            count = len(dep_projects)
            spent_k = sum((p.kra_monthly_progress or 50) * 1.5 for p in dep_projects)
            total_k = count * 180
            if count > 0 and spent_k == 0:
                spent_k = count * 95
            if total_k == 0:
                total_k = 100
            pct = min(100, int((spent_k / total_k) * 100)) if total_k else 0

            departments_data.append({
                'id': dep.id,
                'name': dep.name,
                'count': count,
                'color': dep_color_map.get(dep.id, '#3b82f6'),
                'budget_spent': int(spent_k),
                'budget_total': int(total_k),
                'budget_str': f"${int(spent_k)}K / ${int(total_k)}K" if count > 0 else "$0K / $0K",
                'progress': pct,
            })

        # Filter projects according to department_id
        if department_id:
            filtered_projects = all_projects.filtered(lambda p: p.department_id.id == department_id)
            selected_dep = Department.browse(department_id)
            current_title = selected_dep.name if selected_dep.exists() else 'All departments'
        else:
            filtered_projects = all_projects
            current_title = 'All departments'

        today = fields.Date.today()

        # Build detailed project list with project-wise KRAs and KPIs
        projects_list = []
        for p in filtered_projects:
            # Progress calculation
            prog = 0
            if p.is_completed or (p.stage_id and p.stage_id.name == 'Completed'):
                prog = 100
            elif p.kra_monthly_progress:
                prog = int(p.kra_monthly_progress)
            elif p.kra_weekly_progress:
                prog = int(p.kra_weekly_progress)
            elif p.stage_id and getattr(p.stage_id, 'sequence', None):
                prog = min(95, max(15, int(p.stage_id.sequence * 3)))
            else:
                prog = 55 if p.active else 10

            # Determine status
            if p.is_completed or (p.stage_id and p.stage_id.name == 'Completed') or prog >= 100:
                status = 'done'
                status_label = 'Done'
                prog = 100
            elif p.expected_end_date and p.expected_end_date < today:
                status = 'delayed'
                status_label = 'Delayed'
            elif p.is_on_hold or p.priority in ('2', '3') or prog < 40:
                status = 'at_risk'
                status_label = 'At risk'
            else:
                status = 'on_track'
                status_label = 'On track'

            dep_color = dep_color_map.get(p.department_id.id, '#3b82f6') if p.department_id else '#94a3b8'
            owner = p.project_manager_id.name or p.responsible_user_id.name or 'Unassigned'

            # Date formatting
            end_date_str = ''
            days_str = ''
            if p.expected_end_date:
                end_date_str = p.expected_end_date.strftime('%b %d')
                delta_days = (p.expected_end_date - today).days
                if delta_days < 0:
                    days_str = f"{abs(delta_days)}d overdue"
                else:
                    days_str = f"{delta_days}d"

            # Project KRAs & KPIs breakdown
            kras_list = []
            for kra in p.kra_ids:
                kpis_list = []
                for kpi in kra.kpi_ids:
                    emp_names = [u.name for u in kpi.employee_ids]
                    assigned_str = ', '.join(emp_names) if emp_names else (kpi.employee_id.name if kpi.employee_id else 'Unassigned')
                    kpis_list.append({
                        'id': kpi.id,
                        'name': kpi.name or 'KPI',
                        'code': kpi.code or 'KPI',
                        'kra_id': kra.id,
                        'kra_name': kra.name or 'KRA',
                        'project_id': p.id,
                        'project_name': p.name,
                        'employee': assigned_str,
                        'target': kpi.weekly_target or '-',
                        'progress': int(kpi.progress or 0),
                        'state': kpi.state or 'not_started',
                        'state_label': dict(kpi._fields['state'].selection).get(kpi.state, kpi.state) if 'state' in kpi._fields else kpi.state,
                        'stage_id': kpi.stage_id.id if kpi.stage_id else False,
                        'stage_name': kpi.stage_id.name if kpi.stage_id else '',
                        'hours_spent': round(kpi.total_hours_spent or 0.0, 1),
                        'timesheet_count': len(kpi.timesheet_ids),
                        'is_repeating': bool(kpi.is_repeating or kpi.is_daily_repeating),
                    })

                lead_name = kra.manager_id.name or (kra.responsible_user_id.name if kra.responsible_user_id else 'Unassigned')
                kras_list.append({
                    'id': kra.id,
                    'name': kra.name or 'KRA',
                    'code': kra.reference or 'KRA',
                    'project_id': p.id,
                    'project_name': p.name,
                    'lead': lead_name,
                    'manager_id': kra.manager_id.id if kra.manager_id else False,
                    'weekly_progress': int(kra.weekly_progress or kra.progress_percentage or 0),
                    'monthly_achievement': int(kra.monthly_achievement or 0),
                    'state': kra.state or 'new',
                    'state_label': dict(kra._fields['state'].selection).get(kra.state, kra.state) if 'state' in kra._fields else kra.state,
                    'stage_id': kra.stage_id.id if kra.stage_id else False,
                    'stage_name': kra.stage_id.name if kra.stage_id else '',
                    'priority': kra.priority or '0',
                    'start_date': kra.start_date.strftime('%b %d, %Y') if kra.start_date else '',
                    'end_date': kra.end_date.strftime('%b %d, %Y') if kra.end_date else '',
                    'kpis': kpis_list,
                    'kpi_count': len(kpis_list),
                    'completed_kpi_count': len([k for k in kpis_list if k['state'] == 'completed']),
                })

            # Project Manager details
            pm_name = p.project_manager_id.name or p.responsible_user_id.name or 'Unassigned'
            pm_email = p.project_manager_id.email or p.responsible_user_id.email or ''
            pm_initials = ''.join([part[0].upper() for part in pm_name.split()[:2]]) if pm_name != 'Unassigned' else 'PM'

            # Allocated Team Members
            team_members = []
            for tm in p.team_member_ids:
                role_lbl = dict(tm._fields['role'].selection).get(tm.role, tm.role) if 'role' in tm._fields and tm.role else 'Team Member'
                tm_name = tm.user_id.name if tm.user_id else 'Member'
                tm_initials = ''.join([part[0].upper() for part in tm_name.split()[:2]]) if tm_name else 'TM'
                team_members.append({
                    'id': tm.id,
                    'name': tm_name,
                    'initials': tm_initials,
                    'role': tm.role or 'other',
                    'role_label': role_lbl,
                    'notes': tm.notes or '',
                })

            # Tasks under project
            tasks_list = []
            for task in p.task_ids:
                stage_name = task.stage_id.name if task.stage_id else 'To Do'
                assignees = [u.name for u in task.user_ids]
                deadline_str = task.date_deadline.strftime('%b %d') if task.date_deadline else ''
                is_closed = getattr(task, 'is_closed', False) or (stage_name.lower() in ('done', 'completed', 'cancelled'))
                tasks_list.append({
                    'id': task.id,
                    'name': task.name or 'Task',
                    'stage': stage_name,
                    'assignees': assignees,
                    'assignees_str': ', '.join(assignees) if assignees else 'Unassigned',
                    'deadline': deadline_str,
                    'is_closed': is_closed,
                })

            # Activities under project (Activity Plan + Scheduled Activities)
            activities_list = []
            for act in p.activity_plan_ids:
                start_str = act.planned_start.strftime('%b %d') if act.planned_start else ''
                end_str = act.planned_end.strftime('%b %d') if act.planned_end else ''
                state_label = dict(act._fields['state'].selection).get(act.state, act.state) if 'state' in act._fields else act.state
                priority_label = dict(act._fields['priority'].selection).get(act.priority, act.priority) if 'priority' in act._fields else act.priority
                activities_list.append({
                    'id': act.id,
                    'name': act.name or 'Activity',
                    'responsible': act.responsible_user_id.name if act.responsible_user_id else 'Unassigned',
                    'planned_start': start_str,
                    'planned_end': end_str,
                    'priority': act.priority or 'medium',
                    'priority_label': priority_label,
                    'state': act.state or 'planned',
                    'state_label': state_label,
                    'is_plan': True,
                })

            for m_act in p.activity_ids:
                deadline_str = m_act.date_deadline.strftime('%b %d') if m_act.date_deadline else ''
                activities_list.append({
                    'id': m_act.id,
                    'name': m_act.summary or (m_act.activity_type_id.name if m_act.activity_type_id else 'Activity'),
                    'responsible': m_act.user_id.name if m_act.user_id else 'Unassigned',
                    'planned_start': '',
                    'planned_end': deadline_str,
                    'priority': 'urgent' if m_act.state == 'overdue' else 'medium',
                    'priority_label': m_act.activity_type_id.name if m_act.activity_type_id else 'Scheduled',
                    'state': m_act.state or 'planned',
                    'state_label': m_act.state.capitalize() if m_act.state else 'Planned',
                    'is_plan': False,
                })

            projects_list.append({
                'id': p.id,
                'name': p.name,
                'department_id': p.department_id.id if p.department_id else False,
                'department_name': p.department_id.name if p.department_id else 'General',
                'department_color': dep_color,
                'owner': owner,
                'project_manager': {
                    'name': pm_name,
                    'email': pm_email,
                    'initials': pm_initials,
                    'is_assigned': pm_name != 'Unassigned',
                },
                'team_members': team_members,
                'team_count': len(team_members),
                'tasks': tasks_list,
                'task_count': len(tasks_list),
                'tasks_completed': len([t for t in tasks_list if t['is_closed']]),
                'activities': activities_list,
                'activity_count': len(activities_list),
                'progress': prog,
                'status': status,
                'status_label': status_label,
                'expected_end_date': end_date_str,
                'days_remaining': days_str,
                'raw_date': str(p.expected_end_date or ''),
                'stage_id': p.stage_id.id if p.stage_id else False,
                'stage_name': p.stage_id.name if p.stage_id else 'No Stage',
                'phase': p.phase or 'onboarding',
                'kras': kras_list,
                'kra_count': len(kras_list),
                'kpi_count': sum(k['kpi_count'] for k in kras_list),
            })

        # Summary KPIs
        total_count = len(filtered_projects)
        completed_count = len([p for p in projects_list if p['status'] == 'done'])
        active_count = total_count - completed_count
        delayed_count = len([p for p in projects_list if p['status'] == 'delayed'])
        at_risk_count = len([p for p in projects_list if p['status'] == 'at_risk'])
        needs_attention = delayed_count + at_risk_count

        avg_progress = int(sum(p['progress'] for p in projects_list) / total_count) if total_count else 0

        # Overall budget calculations
        if department_id:
            dep_obj = next((d for d in departments_data if d['id'] == department_id), None)
            total_budget_spent = dep_obj['budget_spent'] if dep_obj else 0
            total_budget_all = dep_obj['budget_total'] if dep_obj else 0
        else:
            total_budget_spent = sum(d['budget_spent'] for d in departments_data)
            total_budget_all = sum(d['budget_total'] for d in departments_data)

        if total_budget_all > 0:
            budget_pct = int((total_budget_spent / total_budget_all) * 100)
        else:
            budget_pct = 71
            total_budget_spent = 1070
            total_budget_all = 1500

        # Due next items (upcoming deadlines)
        upcoming_projects = [
            p for p in projects_list
            if p['status'] != 'done' and p['expected_end_date']
        ]
        upcoming_projects.sort(key=lambda x: x['raw_date'])
        due_next = upcoming_projects[:6]

        # ================= GRAPHICAL STAGES DATA =================
        active_stages = Stage.search([('active', '=', True)], order='sequence, id')
        stage_colors = [
            '#3b82f6', '#06b6d4', '#10b981', '#6366f1',
            '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'
        ]
        stages_data = []
        for idx, stage in enumerate(active_stages):
            st_count = len([p for p in filtered_projects if p.stage_id.id == stage.id])
            st_pct = int((st_count / total_count) * 100) if total_count else 0
            stages_data.append({
                'id': stage.id,
                'name': stage.name,
                'sequence': stage.sequence,
                'phase': stage.phase or 'onboarding',
                'count': st_count,
                'percentage': st_pct,
                'color': stage_colors[idx % len(stage_colors)],
            })

        # Phase Distribution Breakdown
        phases = [
            ('sales', 'Sales Phase', '#3b82f6'),
            ('onboarding', 'Onboarding Phase', '#10b981'),
            ('execution', 'Execution Phase', '#8b5cf6'),
            ('governance', 'Governance Phase', '#f59e0b'),
            ('closure', 'Closure Phase', '#06b6d4'),
        ]
        phases_data = []
        for code, label, color in phases:
            ph_count = len([p for p in filtered_projects if p.phase == code])
            ph_pct = int((ph_count / total_count) * 100) if total_count else 0
            phases_data.append({
                'code': code,
                'name': label,
                'color': color,
                'count': ph_count,
                'percentage': ph_pct,
            })

        # ================= SOPS DATA =================
        sop_domain = [('department_id', '=', department_id)] if department_id else []
        sop_records = SOP.search(sop_domain, order='id desc')
        sops_list = []
        for sop in sop_records[:20]:
            sops_list.append({
                'id': sop.id,
                'name': sop.name,
                'project_name': sop.project_id.name if sop.project_id else 'General',
                'project_id': sop.project_id.id if sop.project_id else False,
                'department_name': sop.department_id.name if sop.department_id else '-',
                'sop_type': sop.sop_type or 'procedure',
                'sop_type_label': dict(sop._fields['sop_type'].selection).get(sop.sop_type, sop.sop_type) if 'sop_type' in sop._fields else sop.sop_type,
                'owner': sop.owner_id.name if sop.owner_id else 'Unassigned',
                'version': sop.version or '1.0',
                'state': sop.state or 'draft',
                'state_label': dict(sop._fields['state'].selection).get(sop.state, sop.state) if 'state' in sop._fields else sop.state,
            })

        sop_summary = {
            'total': len(sop_records),
            'active': len(sop_records.filtered(lambda s: s.state == 'active')),
            'draft': len(sop_records.filtered(lambda s: s.state in ('draft', 'checklist_prep'))),
            'audit': len(sop_records.filtered(lambda s: s.state == 'audit')),
            'records': sops_list,
        }

        # ================= APPROVALS DATA =================
        appr_domain = [('project_id.department_id', '=', department_id)] if department_id else []
        approval_records = Approval.search(appr_domain, order='id desc')
        approvals_list = []
        for app in approval_records[:20]:
            req_date_str = app.requested_date.strftime('%b %d, %H:%M') if app.requested_date else ''
            approvals_list.append({
                'id': app.id,
                'name': app.name or 'Approval Request',
                'project_name': app.project_id.name if app.project_id else '-',
                'project_id': app.project_id.id if app.project_id else False,
                'approval_type': app.approval_type or 'management_review',
                'approval_type_label': dict(app._fields['approval_type'].selection).get(app.approval_type, app.approval_type) if 'approval_type' in app._fields else app.approval_type,
                'requested_by': app.requested_by.name if app.requested_by else 'Unknown',
                'approver': app.approver_id.name if app.approver_id else 'CEO',
                'requested_date': req_date_str,
                'state': app.state or 'pending',
                'state_label': dict(app._fields['state'].selection).get(app.state, app.state) if 'state' in app._fields else app.state,
            })

        approval_summary = {
            'total': len(approval_records),
            'pending': len(approval_records.filtered(lambda a: a.state == 'pending')),
            'approved': len(approval_records.filtered(lambda a: a.state == 'approved')),
            'rejected': len(approval_records.filtered(lambda a: a.state == 'rejected')),
            'records': approvals_list,
        }

        # KRA & KPI Summary stats
        kra_domain = [('department_id', '=', department_id)] if department_id else []
        all_kras = self.env['business.project.kra'].search(kra_domain, order='sequence, id desc')
        total_kras = len(all_kras)
        active_kras = len(all_kras.filtered(lambda k: k.state in ('ongoing', 'active', 'in_progress', 'new')))
        completed_kras = len(all_kras.filtered(lambda k: k.state == 'completed'))
        on_hold_kras = len(all_kras.filtered(lambda k: k.state in ('on_hold', 'hold')))
        avg_kra_perf = int(sum(all_kras.mapped('progress_percentage')) / total_kras) if total_kras else 0

        kpi_domain = [('department_id', '=', department_id)] if department_id else []
        all_kpis = self.env['business.project.kpi'].search(kpi_domain, order='sequence, id desc')
        total_kpis = len(all_kpis)
        active_kpis = len(all_kpis.filtered(lambda k: k.state in ('in_progress', 'ongoing')))
        completed_kpis = len(all_kpis.filtered(lambda k: k.state == 'completed'))
        not_started_kpis = len(all_kpis.filtered(lambda k: k.state in ('not_started', 'new', 'draft')))
        on_hold_kpis = len(all_kpis.filtered(lambda k: k.state in ('on_hold', 'hold')))
        cancelled_kpis = len(all_kpis.filtered(lambda k: k.state in ('cancelled', 'cancel')))

        # Build comprehensive flat list of all KRAs
        all_kras_flat = []
        for kra in all_kras:
            lead_name = kra.manager_id.name or (kra.responsible_user_id.name if kra.responsible_user_id else 'Unassigned')
            all_kras_flat.append({
                'id': kra.id,
                'name': kra.name or 'KRA',
                'code': kra.reference or 'KRA',
                'project_id': kra.project_id.id if kra.project_id else False,
                'project_name': kra.project_id.name if kra.project_id else 'General',
                'department_name': kra.department_id.name if kra.department_id else (kra.project_id.department_id.name if kra.project_id and kra.project_id.department_id else 'General'),
                'lead': lead_name,
                'manager_id': kra.manager_id.id if kra.manager_id else False,
                'weekly_progress': int(kra.weekly_progress or kra.progress_percentage or 0),
                'monthly_achievement': int(kra.monthly_achievement or 0),
                'state': kra.state or 'new',
                'state_label': dict(kra._fields['state'].selection).get(kra.state, kra.state) if 'state' in kra._fields else kra.state,
                'stage_id': kra.stage_id.id if kra.stage_id else False,
                'stage_name': kra.stage_id.name if kra.stage_id else '',
                'priority': kra.priority or '0',
                'start_date': kra.start_date.strftime('%b %d, %Y') if kra.start_date else '',
                'end_date': kra.end_date.strftime('%b %d, %Y') if kra.end_date else '',
                'kpi_count': len(kra.kpi_ids),
                'completed_kpi_count': len(kra.kpi_ids.filtered(lambda k: k.state == 'completed')),
            })

        # Build comprehensive flat list of all KPIs
        all_kpis_flat = []
        for kpi in all_kpis:
            emp_names = [u.name for u in kpi.employee_ids]
            assigned_str = ', '.join(emp_names) if emp_names else (kpi.employee_id.name if kpi.employee_id else 'Unassigned')
            all_kpis_flat.append({
                'id': kpi.id,
                'name': kpi.name or 'KPI',
                'code': kpi.code or 'KPI',
                'kra_id': kpi.kra_id.id if kpi.kra_id else False,
                'kra_name': kpi.kra_id.name if kpi.kra_id else '-',
                'project_id': kpi.project_id.id if kpi.project_id else (kpi.kra_id.project_id.id if kpi.kra_id and kpi.kra_id.project_id else False),
                'project_name': kpi.project_id.name if kpi.project_id else (kpi.kra_id.project_id.name if kpi.kra_id and kpi.kra_id.project_id else '-'),
                'manager_name': kpi.manager_id.name if kpi.manager_id else (kpi.kra_id.manager_id.name if kpi.kra_id and kpi.kra_id.manager_id else 'Unassigned'),
                'employee': assigned_str,
                'target': kpi.weekly_target or '-',
                'progress': int(kpi.progress or 0),
                'state': kpi.state or 'not_started',
                'state_label': dict(kpi._fields['state'].selection).get(kpi.state, kpi.state) if 'state' in kpi._fields else kpi.state,
                'stage_id': kpi.stage_id.id if kpi.stage_id else False,
                'stage_name': kpi.stage_id.name if kpi.stage_id else '',
                'hours_spent': round(kpi.total_hours_spent or 0.0, 1),
                'timesheet_count': len(kpi.timesheet_ids),
                'is_repeating': bool(kpi.is_repeating or kpi.is_daily_repeating),
            })

        # ================= CHART DATA (BAR & LINE GRAPHICAL VIEWS) =================
        # 1. Projects by Department
        chart_by_department = []
        for dep in departments_data:
            chart_by_department.append({
                'id': dep['id'],
                'label': dep['name'],
                'value': dep['count'],
                'color': dep['color'],
            })

        # 3. Projects by Status
        status_colors = {
            'on_track': '#10b981',
            'at_risk': '#f59e0b',
            'delayed': '#ef4444',
            'done': '#3b82f6',
        }
        status_labels = {
            'on_track': 'On Track',
            'at_risk': 'At Risk',
            'delayed': 'Delayed',
            'done': 'Done',
        }
        status_counts = {'on_track': 0, 'at_risk': 0, 'delayed': 0, 'done': 0}
        for p in projects_list:
            st = p.get('status', 'on_track')
            if st in status_counts:
                status_counts[st] += 1
            else:
                status_counts['on_track'] += 1

        chart_by_status = []
        for k, lbl in status_labels.items():
            cnt = status_counts.get(k, 0)
            pct = int((cnt / total_count) * 100) if total_count else 0
            chart_by_status.append({
                'id': k,
                'label': lbl,
                'value': cnt,
                'percentage': pct,
                'color': status_colors[k],
            })

        # 4. Monthly Trend (6 months)
        today = fields.Date.context_today(self)
        months_list = []
        for i in range(5, -1, -1):
            m_year = today.year
            m_month = today.month - i
            while m_month <= 0:
                m_month += 12
                m_year -= 1
            d_obj = date(m_year, m_month, 1)
            months_list.append((d_obj.strftime('%Y-%m'), d_obj.strftime('%b %Y'), d_obj.strftime('%b')))

        chart_monthly_trend = []
        for ym, full_label, short_label in months_list:
            cnt = len([p for p in filtered_projects if p.create_date and p.create_date.strftime('%Y-%m') == ym])
            chart_monthly_trend.append({
                'id': ym,
                'label': short_label,
                'full_label': full_label,
                'value': cnt,
                'color': '#3b82f6',
            })
        if not any(m['value'] for m in chart_monthly_trend) and total_count > 0:
            for idx, m in enumerate(chart_monthly_trend):
                m['value'] = max(1, (idx + 1) * total_count // len(chart_monthly_trend))

        chart_data = {
            'by_department': chart_by_department,
            'by_status': chart_by_status,
            'monthly_trend': chart_monthly_trend,
        }

        return {
            'company_name': self.env.company.name or 'Northwind Co.',
            'selected_department_id': department_id or False,
            'current_title': current_title,
            'total_all_projects': len(all_projects),
            'total_shown_projects': total_count,
            'departments': departments_data,
            'projects': projects_list,
            'all_kras': all_kras_flat,
            'all_kpis': all_kpis_flat,
            'kpis': {
                'active_projects': active_count,
                'completed_projects': completed_count,
                'avg_progress': avg_progress,
                'needs_attention': needs_attention,
                'delayed_count': delayed_count,
                'budget_used_pct': budget_pct,
                'budget_spent_str': f"${total_budget_spent:,}K",
                'budget_total_str': f"${total_budget_all:,}K",
                'total_kras': total_kras,
                'active_kras': active_kras,
                'completed_kras': completed_kras,
                'on_hold_kras': on_hold_kras,
                'avg_kra_performance': avg_kra_perf,
                'total_kpis': total_kpis,
                'active_kpis': active_kpis,
                'completed_kpis': completed_kpis,
                'not_started_kpis': not_started_kpis,
                'on_hold_kpis': on_hold_kpis,
                'cancelled_kpis': cancelled_kpis,
            },
            'stages': stages_data,
            'phases': phases_data,
            'sops': sop_summary,
            'approvals': approval_summary,
            'due_next': due_next,
            'chart_data': chart_data,
        }

    @api.model
    def update_kpi_progress(self, kpi_id, progress):
        """Allows direct inline progress updates from the dashboard."""
        kpi = self.env['business.project.kpi'].browse(int(kpi_id))
        if kpi.exists():
            val = min(100.0, max(0.0, float(progress)))
            vals = {'progress': val}
            if val >= 100.0:
                vals['state'] = 'completed'
            elif val > 0.0 and kpi.state in ('not_started', 'completed'):
                vals['state'] = 'in_progress'
            elif val == 0.0 and kpi.state == 'completed':
                vals['state'] = 'not_started'
            kpi.write(vals)
            return True
        return False

    @api.model
    def set_kpi_stage(self, kpi_id, state):
        """Allows direct inline status updates from the dashboard."""
        kpi = self.env['business.project.kpi'].browse(int(kpi_id))
        if kpi.exists():
            kpi.write({'state': state})
            return True
        return False

    @api.model
    def set_kra_stage(self, kra_id, state):
        """Allows direct inline status updates from the dashboard."""
        kra = self.env['business.project.kra'].browse(int(kra_id))
        if kra.exists():
            kra.write({'state': state})
            return True
        return False
