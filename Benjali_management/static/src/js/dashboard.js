/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class BenjaliDashboard extends Component {

    static template = "BenjaliManagement.Dashboard";

    setup() {
        // Odoo ORM service
        this.orm = useService("orm");

        // Dashboard state
        this.state = useState({
            loading: true,
            error: false,
            data: null,
        });

        // Load dashboard data before rendering
        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;
            this.state.error = false;

            const data = await this.orm.call(
                "benjali.management.dashboard",
                "get_dashboard_data",
                [false]
            );

            this.state.data = data;

        } catch (error) {
            console.error(
                "Benjali Management Dashboard Error:",
                error
            );

            this.state.error = true;

        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("actions").add(
    "benjali_management_dashboard",
    BenjaliDashboard
);