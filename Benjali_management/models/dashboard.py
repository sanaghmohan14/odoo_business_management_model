from odoo import models


class BenjaliManagementDashboard(models.AbstractModel):
    _name = 'benjali.management.dashboard'
    _description = 'Benjali Management Dashboard'

    def get_dashboard_data(self, department_id=False):
        """
        Return dynamic dashboard information.

        department_id:
            If provided, all project-related statistics are filtered
            by that department.
        """

        Project = self.env['business.project']
        Stage = self.env['business.project.stage']
        KRA = self.env['business.project.kra']
        Activity = self.env['business.project.activity']
        DataCollection = self.env['business.project.data.collection']
        Team = self.env['business.project.team']
        Timesheet = self.env['account.analytic.line']
        Lead = self.env['crm.lead']

        # ---------------------------------------------------------
        # PROJECT DOMAIN
        # ---------------------------------------------------------

        project_domain = []

        if department_id:
            project_domain.append(
                ('department_id', '=', department_id)
            )

        # ---------------------------------------------------------
        # PROJECT COUNTS
        # ---------------------------------------------------------

        total_projects = Project.search_count(project_domain)

        active_projects = Project.search_count(
            project_domain + [('active', '=', True)]
        )

        completed_projects = Project.search_count(
            project_domain + [('stage_id.name', '=', 'Completed')]
        )

        on_hold_projects = Project.search_count(
            project_domain + [('stage_id.name', '=', 'On Hold')]
        )

        cancelled_projects = Project.search_count(
            project_domain + [('stage_id.name', '=', 'Cancelled')]
        )

        # ---------------------------------------------------------
        # PROJECTS BY STAGE
        # ---------------------------------------------------------

        stages = Stage.search(
            [('active', '=', True)],
            order='sequence, id'
        )

        stage_data = []

        for stage in stages:
            count = Project.search_count(
                project_domain + [
                    ('stage_id', '=', stage.id)
                ]
            )

            stage_data.append({
                'id': stage.id,
                'name': stage.name,
                'sequence': stage.sequence,
                'phase': stage.phase,
                'phase_label': dict(
                    stage._fields['phase'].selection
                ).get(stage.phase, ''),
                'count': count,
                'folded': stage.folded,
                'requires_approval': stage.requires_approval,
            })

        # ---------------------------------------------------------
        # PROJECTS BY PHASE
        # ---------------------------------------------------------

        phase_selection = dict(
            Stage._fields['phase'].selection
        )

        phase_data = []

        for phase_code, phase_name in phase_selection.items():

            phase_stage_ids = stages.filtered(
                lambda stage: stage.phase == phase_code
            ).ids

            if phase_stage_ids:
                count = Project.search_count(
                    project_domain + [
                        ('stage_id', 'in', phase_stage_ids)
                    ]
                )
            else:
                count = 0

            phase_data.append({
                'code': phase_code,
                'name': phase_name,
                'count': count,
            })

        # ---------------------------------------------------------
        # KRA
        # ---------------------------------------------------------

        kra_domain = []

        if department_id:
            kra_domain.append(
                ('project_id.department_id', '=', department_id)
            )

        total_kras = KRA.search_count(kra_domain)

        active_kras = KRA.search_count(
            kra_domain + [('active', '=', True)]
        )

        projects_with_kra = Project.search_count(
            project_domain + [
                ('kra_ids', '!=', False)
            ]
        )

        # ---------------------------------------------------------
        # ACTIVITIES
        # ---------------------------------------------------------

        activity_domain = []

        if department_id:
            activity_domain.append(
                ('project_id.department_id', '=', department_id)
            )

        total_activities = Activity.search_count(activity_domain)

        planned_activities = Activity.search_count(
            activity_domain + [
                ('state', '=', 'planned')
            ]
        )

        in_progress_activities = Activity.search_count(
            activity_domain + [
                ('state', '=', 'in_progress')
            ]
        )

        completed_activities = Activity.search_count(
            activity_domain + [
                ('state', '=', 'completed')
            ]
        )

        cancelled_activities = Activity.search_count(
            activity_domain + [
                ('state', '=', 'cancelled')
            ]
        )

        # ---------------------------------------------------------
        # DATA COLLECTION
        # ---------------------------------------------------------

        data_collection_domain = []

        if department_id:
            data_collection_domain.append(
                ('project_id.department_id', '=', department_id)
            )

        total_data_collection = DataCollection.search_count(
            data_collection_domain
        )

        planned_data_collection = DataCollection.search_count(
            data_collection_domain + [
                ('state', '=', 'planned')
            ]
        )

        in_progress_data_collection = DataCollection.search_count(
            data_collection_domain + [
                ('state', '=', 'in_progress')
            ]
        )

        collected_data_collection = DataCollection.search_count(
            data_collection_domain + [
                ('state', '=', 'collected')
            ]
        )

        verified_data_collection = DataCollection.search_count(
            data_collection_domain + [
                ('state', '=', 'verified')
            ]
        )

        # ---------------------------------------------------------
        # TEAM
        # ---------------------------------------------------------

        team_domain = []

        if department_id:
            team_domain.append(
                ('project_id.department_id', '=', department_id)
            )

        total_team_members = Team.search_count(
            team_domain + [('active', '=', True)]
        )

        # ---------------------------------------------------------
        # TIMESHEETS
        # ---------------------------------------------------------

        timesheet_domain = []

        if department_id:
            timesheet_domain.append(
                ('business_project_id.department_id', '=', department_id)
            )

        total_timesheets = Timesheet.search_count(
            timesheet_domain
        )

        total_timesheet_hours = sum(
            Timesheet.search(
                timesheet_domain
            ).mapped('unit_amount')
        )

        # ---------------------------------------------------------
        # CRM
        # ---------------------------------------------------------

        crm_domain = []

        if department_id:
            crm_domain.append(
                ('department_id', '=', department_id)
            )

        total_crm = Lead.search_count(crm_domain)

        crm_with_project = Lead.search_count(
            crm_domain + [
                ('business_project_id', '!=', False)
            ]
        )

        crm_without_project = Lead.search_count(
            crm_domain + [
                ('business_project_id', '=', False)
            ]
        )

        # ---------------------------------------------------------
        # RETURN DATA
        # ---------------------------------------------------------

        return {
            'projects': {
                'total': total_projects,
                'active': active_projects,
                'completed': completed_projects,
                'on_hold': on_hold_projects,
                'cancelled': cancelled_projects,
            },

            'stages': stage_data,

            'phases': phase_data,

            'kra': {
                'total': total_kras,
                'active': active_kras,
                'projects_with_kra': projects_with_kra,
            },

            'activities': {
                'total': total_activities,
                'planned': planned_activities,
                'in_progress': in_progress_activities,
                'completed': completed_activities,
                'cancelled': cancelled_activities,
            },

            'data_collection': {
                'total': total_data_collection,
                'planned': planned_data_collection,
                'in_progress': in_progress_data_collection,
                'collected': collected_data_collection,
                'verified': verified_data_collection,
            },

            'team': {
                'total_active_members': total_team_members,
            },

            'timesheets': {
                'total': total_timesheets,
                'total_hours': total_timesheet_hours,
            },

            'crm': {
                'total': total_crm,
                'with_business_project': crm_with_project,
                'without_business_project': crm_without_project,
            },
        }