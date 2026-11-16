/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class TallerDashboard extends Component {
    static template = "analitica_talleresg2.TallerDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            selectedYear: null,
            selectedMonth: null,
            data: {
                selected_period: "",
                available_months: [],
                historico_mensual: [],
                mes_actual: {
                    nombre: "Mes Actual",
                    total: 0.0,
                    total_fmt: "$0.00",
                    mo: 0.0,
                    mo_fmt: "$0.00",
                    rep: 0.0,
                    rep_fmt: "$0.00",
                    ext: 0.0,
                    ext_fmt: "$0.00",
                    pct_ext: 0,
                    pct_mo: 0,
                    pct_rep: 0,
                    facturas: 0,
                },
                mes_anterior: {
                    nombre: "Mes Anterior",
                    total: 0.0,
                    total_fmt: "$0.00",
                    facturas: 0,
                },
                variacion: {
                    pct: 0.0,
                    positiva: true,
                },
                total_anual: {
                    anio: new Date().getFullYear(),
                    monto: 0.0,
                    monto_fmt: "$0.00",
                },
                flota: {
                    total_vehiculos: 0,
                    activos: 0,
                    alerta: 0,
                    riesgo: 0,
                },
                top_clientes: [],
                top_mecanicos: [],
                vehiculos_riesgo: [],
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData(year = null, month = null) {
        this.state.loading = true;
        try {
            const args = [];
            if (typeof year === "number" && typeof month === "number") {
                args.push(year, month);
                this.state.selectedYear = year;
                this.state.selectedMonth = month;
            } else if (this.state.selectedYear && this.state.selectedMonth) {
                args.push(this.state.selectedYear, this.state.selectedMonth);
            }
            const result = await this.orm.call("taller.bitacora.vehiculo", "get_dashboard_kpis", args);
            if (result && result.mes_actual) {
                this.state.data = result;
                if (!this.state.selectedYear && result.selected_year) {
                    this.state.selectedYear = result.selected_year;
                    this.state.selectedMonth = result.selected_month;
                }
            }
        } catch (e) {
            console.error("Error cargando KPIs del taller:", e);
        } finally {
            this.state.loading = false;
        }
    }

    onPeriodChange(ev) {
        const val = ev.target.value;
        if (!val) return;
        const [y, m] = val.split("-");
        this.loadData(parseInt(y), parseInt(m));
    }

    selectPeriod(year, month) {
        if (!year || !month) return;
        this.loadData(year, month);
    }

    openInvoicesMonth() {
        const domain = [
            ["move_type", "in", ["out_invoice", "out_refund"]],
            ["state", "=", "posted"],
            ["es_taller", "=", true],
        ];
        if (this.state.data.first_day && this.state.data.last_day) {
            domain.push(["invoice_date", ">=", this.state.data.first_day]);
            domain.push(["invoice_date", "<=", this.state.data.last_day]);
        }
        this.action.doAction({
            name: _t(`Facturas de Taller - ${this.state.data.mes_actual.nombre}`),
            type: "ir.actions.act_window",
            res_model: "account.move",
            views: [[false, "list"], [false, "form"]],
            view_mode: "list,form",
            domain: domain,
            context: {
                search_default_filter_invoices: 1,
            },
        });
    }

    openPartner(partnerId) {
        if (!partnerId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: partnerId,
            views: [[false, "form"]],
            view_mode: "form",
        });
    }

    openVehiclesRisk() {
        this.action.doAction({
            name: _t("Vehículos en Riesgo (> 90 días sin servicio)"),
            type: "ir.actions.act_window",
            res_model: "taller.bitacora.vehiculo",
            views: [[false, "list"], [false, "form"]],
            view_mode: "list,form",
            context: {
                search_default_filter_inactive: 1,
            },
        });
    }

    openAllVehicles(filterName = null) {
        const context = {};
        if (filterName) {
            context[filterName] = 1;
        }
        this.action.doAction({
            name: _t("Bitácora de Servicios por Vehículo"),
            type: "ir.actions.act_window",
            res_model: "taller.bitacora.vehiculo",
            views: [[false, "list"], [false, "pivot"], [false, "graph"], [false, "form"]],
            view_mode: "list,pivot,graph,form",
            context: context,
        });
    }

    openVehicleDetail(plate) {
        if (!plate) return;
        this.action.doAction({
            name: _t(`Historial del Vehículo ${plate}`),
            type: "ir.actions.act_window",
            res_model: "taller.bitacora.vehiculo",
            views: [[false, "list"], [false, "form"]],
            view_mode: "list,form",
            domain: [["placa", "=", plate]],
        });
    }
}

registry.category("actions").add("taller_dashboard", TallerDashboard);
