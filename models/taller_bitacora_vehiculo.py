# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools
from datetime import date, timedelta



class TallerBitacoraVehiculo(models.Model):
    _name = 'taller.bitacora.vehiculo'
    _description = 'Bitácora de Servicios por Vehículo'
    _auto = False
    _order = 'fecha_ultimo_servicio desc, id desc'

    placa = fields.Char(string='Placa', readonly=True)
    clean_plate = fields.Char(string='Placa Normalizada', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Propietario / Cliente', readonly=True)
    marca = fields.Char(string='Marca', readonly=True)
    modelo = fields.Char(string='Modelo', readonly=True)
    ano = fields.Char(string='Año', readonly=True)
    tipo_vehiculo = fields.Char(string='Tipo de Vehículo', readonly=True)
    vin = fields.Char(string='VIN', readonly=True)
    motor = fields.Char(string='Motor', readonly=True)
    chasis = fields.Char(string='Chasis', readonly=True)
    kilometraje = fields.Char(string='Kilometraje', readonly=True)
    
    latest_invoice_id = fields.Many2one('account.move', string='Última Factura', readonly=True)
    latest_order_id = fields.Many2one('sale.order', string='Último Presupuesto / Orden', readonly=True)
    monto_ultimo_presupuesto = fields.Monetary(
        string='Monto Últ. Presupuesto',
        currency_field='currency_id',
        readonly=True
    )

    ultimo_servicio_realizado = fields.Text(
        string='Último Trabajo Realizado',
        readonly=True,
        help='Mano de obra y servicios deducidos automáticamente de la última factura u orden de servicio.'
    )

    mecanico_id = fields.Many2one('hr.employee', string='Mecánico Asignado', readonly=True)
    mecanico_nombre = fields.Char(string='Nombre Mecánico', readonly=True)
    
    fecha_ultimo_servicio = fields.Date(string='Fecha Últ. Servicio', readonly=True)
    monto_ultima_factura = fields.Monetary(
        string='Monto Últ. Factura',
        currency_field='currency_id',
        readonly=True
    )
    monto_mano_obra = fields.Monetary(
        string='M/O Últ. Factura',
        currency_field='currency_id',
        readonly=True,
        help='Monto específico de mano de obra y servicios del último trabajo realizado.'
    )
    monto_repuestos = fields.Monetary(
        string='Repuestos Últ. Factura',
        currency_field='currency_id',
        readonly=True,
        help='Monto específico de repuestos y materiales de la última factura.'
    )
    total_facturado = fields.Monetary(
        string='Total Facturado',
        currency_field='currency_id',
        readonly=True
    )
    total_mano_obra = fields.Monetary(
        string='Total Mano de Obra',
        currency_field='currency_id',
        readonly=True,
        help='Suma total histórica facturada exclusivamente en conceptos de mano de obra y servicios técnicos.'
    )
    total_repuestos = fields.Monetary(
        string='Total Repuestos',
        currency_field='currency_id',
        readonly=True,
        help='Suma total histórica facturada en repuestos, partes mecánicas y consumibles.'
    )
    cantidad_facturas = fields.Integer(string='Cant. Facturas', readonly=True)
    cantidad_ordenes = fields.Integer(string='Cant. Servicios / Órdenes', readonly=True)


    dias_sin_servicio = fields.Integer(
        string='Días sin Servicio',
        compute='_compute_dias_sin_servicio',
        search='_search_dias_sin_servicio'
    )

    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)

    def _compute_dias_sin_servicio(self):
        today = fields.Date.today()
        for rec in self:
            if rec.fecha_ultimo_servicio:
                rec.dias_sin_servicio = (today - rec.fecha_ultimo_servicio).days
            else:
                rec.dias_sin_servicio = 0

    def _search_dias_sin_servicio(self, operator, value):
        today = fields.Date.today()
        target_date = today - timedelta(days=value)
        op_map = {
            '<=': '>=',
            '<': '>',
            '>=': '<=',
            '>': '<',
            '=': '=',
        }
        mapped_op = op_map.get(operator, '=')
        return [('fecha_ultimo_servicio', mapped_op, target_date)]

    def action_view_latest_service_detail(self):
        self.ensure_one()
        view_id = self.env.ref('analitica_talleresg2.view_taller_bitacora_servicio_modal').id
        return {
            'name': f'Detalle del Último Servicio - {self.placa}',
            'type': 'ir.actions.act_window',
            'res_model': 'taller.bitacora.vehiculo',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

    def action_open_latest_invoice(self):
        self.ensure_one()
        if self.latest_invoice_id:
            return {
                'name': f'Factura {self.latest_invoice_id.name}',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': self.latest_invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_open_latest_order(self):
        self.ensure_one()
        if self.latest_order_id:
            return {
                'name': f'Presupuesto / Orden {self.latest_order_id.name}',
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.latest_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_view_invoices(self):
        self.ensure_one()
        g2_company = self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')], limit=1)
        company_domain = [('company_id', '=', g2_company.id)] if g2_company else []
        return {
            'name': f'Facturas del Vehículo {self.placa}',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                '|',
                ('clean_placa_vehiculo', '=', self.clean_plate),
                ('x_placa_vehiculo', '=ilike', self.placa),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
                ('es_taller', '=', True),
            ] + company_domain,
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

    def action_view_orders(self):
        self.ensure_one()
        g2_company = self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')], limit=1)
        company_domain = [('company_id', '=', g2_company.id)] if g2_company else []
        return {
            'name': f'Servicios / Órdenes del Vehículo {self.placa}',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [
                '|',
                ('clean_placa_vehiculo', '=', self.clean_plate),
                ('x_placa_vehiculo', '=ilike', self.placa),
            ] + company_domain,
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

    @api.model
    def get_dashboard_kpis(self, selected_year=None, selected_month=None):
        """
        Retorna las métricas y datos consolidados para el Tablero de Control / Dashboard.
        Permite seleccionar cualquier mes histórico o el mes actual por defecto.
        """
        cr = self.env.cr
        today = fields.Date.today()
        year = int(selected_year) if selected_year else today.year
        month = int(selected_month) if selected_month else today.month

        first_this_month = date(year, month, 1)
        if month == 12:
            last_this_month = date(year, 12, 31)
        else:
            last_this_month = date(year, month + 1, 1) - timedelta(days=1)

        last_month_end = first_this_month - timedelta(days=1)
        first_last_month = last_month_end.replace(day=1)
        first_year = date(year, 1, 1)

        month_names = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        mes_actual_nombre = f"{month_names[month]} {year}"
        mes_anterior_nombre = f"{month_names[last_month_end.month]} {last_month_end.year}"

        # Obtener IDs de compañías de Grupo 2 de forma segura
        g2_companies = self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')])
        if g2_companies:
            ids_str = ",".join(str(cid) for cid in g2_companies.ids)
            comp_cond = f"AND (company_id IS NULL OR company_id IN ({ids_str}))"
            comp_cond_am = f"AND (am.company_id IS NULL OR am.company_id IN ({ids_str}))"
        else:
            comp_cond = ""
            comp_cond_am = ""

        # Importes en moneda de la compañía; el balance ya incluye el signo de las notas de crédito.
        # La última sección anterior determina la categoría hasta la próxima sección.
        category_join = """
            LEFT JOIN LATERAL (
                SELECT
                    SUM(-line.balance) FILTER (WHERE line.is_external) AS ext,
                    SUM(-line.balance) FILTER (WHERE NOT line.is_external AND line.es_mano_de_obra) AS mo,
                    SUM(-line.balance) FILTER (WHERE NOT line.is_external AND NOT COALESCE(line.es_mano_de_obra, FALSE)) AS rep
                FROM (
                    SELECT aml.balance, aml.es_mano_de_obra,
                        COALESCE((
                            SELECT UPPER(TRIM(section.name)) IN ('TRABAJOS EXTERNOS', 'TRABAJO EXTERNO')
                            FROM account_move_line section
                            WHERE section.move_id = aml.move_id
                              AND section.display_type = 'line_section'
                              AND (section.sequence, section.id) < (aml.sequence, aml.id)
                            ORDER BY section.sequence DESC, section.id DESC
                            LIMIT 1
                        ), FALSE) AS is_external
                    FROM account_move_line aml
                    WHERE aml.move_id = account_move.id AND aml.display_type = 'product'
                ) line
            ) amounts ON TRUE
        """

        # 1. Facturación Mes Seleccionado (Subtotal Base Imponible Sin IVA y Total Con IVA)
        query_now = f"""
            SELECT 
                COALESCE(SUM(amount_untaxed_signed), 0.0) as subtotal,
                COALESCE(SUM(amount_total_signed), 0.0) as total_con_iva,
                COALESCE(SUM(amounts.mo), 0.0) as mo,
                COALESCE(SUM(amounts.rep), 0.0) as rep,
                COALESCE(SUM(amounts.ext), 0.0) as ext,
                COUNT(id) as cant_facturas
            FROM account_move
            {category_join}
            WHERE move_type IN ('out_invoice', 'out_refund')
              AND state = 'posted'
              AND es_taller = True
              AND invoice_date >= %s AND invoice_date <= %s
              {comp_cond}
        """
        cr.execute(query_now, (first_this_month, last_this_month))
        row_now = cr.dictfetchone() or {}
        mes_actual_subtotal = float(row_now.get('subtotal') or 0.0)
        mes_actual_total_con_iva = float(row_now.get('total_con_iva') or 0.0)
        mes_actual_mo = float(row_now.get('mo') or 0.0)
        mes_actual_rep = float(row_now.get('rep') or 0.0)
        mes_actual_ext = float(row_now.get('ext') or 0.0)
        facturas_mes = int(row_now.get('cant_facturas') or 0)

        # 2. Facturación Mes Anterior
        query_prev = f"""
            SELECT 
                COALESCE(SUM(amount_untaxed_signed), 0.0) as subtotal,
                COALESCE(SUM(amount_total_signed), 0.0) as total_con_iva,
                COUNT(id) as cant_facturas
            FROM account_move
            WHERE move_type IN ('out_invoice', 'out_refund')
              AND state = 'posted'
              AND es_taller = True
              AND invoice_date >= %s AND invoice_date <= %s
              {comp_cond}
        """
        cr.execute(query_prev, (first_last_month, last_month_end))
        row_prev = cr.dictfetchone() or {}
        mes_anterior_subtotal = float(row_prev.get('subtotal') or 0.0)
        mes_anterior_total_con_iva = float(row_prev.get('total_con_iva') or 0.0)
        facturas_mes_anterior = int(row_prev.get('cant_facturas') or 0)

        # Variación % calculada sobre Base Imponible comparable
        if mes_anterior_subtotal > 0:
            var_pct = round(((mes_actual_subtotal - mes_anterior_subtotal) / mes_anterior_subtotal) * 100.0, 1)
        else:
            var_pct = 100.0 if mes_actual_subtotal > 0 else 0.0

        # Distribución de las tres categorías; sin actividad no hay proporciones.
        distribution_total = abs(mes_actual_mo) + abs(mes_actual_rep) + abs(mes_actual_ext)
        pct_mo = round(abs(mes_actual_mo) / distribution_total * 100, 1) if distribution_total else 0.0
        pct_rep = round(abs(mes_actual_rep) / distribution_total * 100, 1) if distribution_total else 0.0
        pct_ext = round(100 - pct_mo - pct_rep, 1) if distribution_total else 0.0

        # 3. Top 5 Clientes del Mes Seleccionado
        query_top_clients = f"""
            SELECT 
                rp.id,
                rp.name,
                COUNT(DISTINCT am.id) as cant_facturas,
                COUNT(DISTINCT UPPER(REGEXP_REPLACE(TRIM(am.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g'))) FILTER (WHERE am.x_placa_vehiculo IS NOT NULL AND TRIM(am.x_placa_vehiculo) != '') as cant_vehiculos,
                SUM(CASE WHEN am.move_type = 'out_invoice' THEN am.amount_total_signed WHEN am.move_type = 'out_refund' THEN -am.amount_total_signed ELSE 0 END) as total
            FROM account_move am
            JOIN res_partner rp ON rp.id = am.partner_id
            WHERE am.move_type IN ('out_invoice', 'out_refund')
              AND am.state = 'posted'
              AND am.es_taller = True
              AND am.invoice_date >= %s AND am.invoice_date <= %s
              {comp_cond_am}
            GROUP BY rp.id, rp.name
            ORDER BY total DESC
            LIMIT 5;
        """
        cr.execute(query_top_clients, (first_this_month, last_this_month))
        top_clientes = cr.dictfetchall() or []
        for c in top_clientes:
            c['total_fmt'] = f"${float(c.get('total') or 0.0):,.2f}"

        # 4. Top Mecánicos Productivos del Mes Seleccionado
        query_mecanicos = f"""
            SELECT 
                e.id,
                e.name,
                COUNT(DISTINCT am.id) as cant_servicios,
                SUM(COALESCE(am.taller_monto_mano_obra, 0.0)) as total_mo
            FROM account_move am
            JOIN hr_employee e ON e.id = am.mecanico_id
            WHERE am.move_type IN ('out_invoice', 'out_refund')
              AND am.state = 'posted'
              AND am.es_taller = True
              AND am.invoice_date >= %s AND am.invoice_date <= %s
              {comp_cond_am}
            GROUP BY e.id, e.name
            ORDER BY total_mo DESC
            LIMIT 5;
        """
        cr.execute(query_mecanicos, (first_this_month, last_this_month))
        top_mecanicos = cr.dictfetchall() or []
        for m in top_mecanicos:
            m['total_mo_fmt'] = f"${float(m.get('total_mo') or 0.0):,.2f}"

        # 5. Vehículos en Riesgo (> 90 días sin servicio)
        cr.execute("""
            SELECT 
                placa,
                clean_plate,
                partner_id,
                (SELECT name FROM res_partner WHERE id = tbv.partner_id) as partner_name,
                COALESCE(marca, 'N/D') as marca,
                COALESCE(modelo, '') as modelo,
                fecha_ultimo_servicio,
                total_facturado,
                total_mano_obra,
                (CURRENT_DATE - fecha_ultimo_servicio) as dias_sin_servicio
            FROM taller_bitacora_vehiculo tbv
            WHERE fecha_ultimo_servicio IS NOT NULL
              AND (CURRENT_DATE - fecha_ultimo_servicio) > 90
            ORDER BY dias_sin_servicio DESC, total_facturado DESC
            LIMIT 6;
        """)
        vehiculos_riesgo = cr.dictfetchall() or []
        for v in vehiculos_riesgo:
            v['total_facturado_fmt'] = f"${float(v.get('total_facturado') or 0.0):,.2f}"
            v['fecha_ultimo_servicio_fmt'] = v['fecha_ultimo_servicio'].strftime('%d/%m/%Y') if v.get('fecha_ultimo_servicio') else 'N/D'

        # 6. Resumen de Estados de Flota
        cr.execute("""
            SELECT 
                COUNT(*) as total_vehiculos,
                COUNT(*) FILTER (WHERE fecha_ultimo_servicio IS NOT NULL AND (CURRENT_DATE - fecha_ultimo_servicio) <= 30) as activos,
                COUNT(*) FILTER (WHERE fecha_ultimo_servicio IS NOT NULL AND (CURRENT_DATE - fecha_ultimo_servicio) > 30 AND (CURRENT_DATE - fecha_ultimo_servicio) <= 90) as alerta,
                COUNT(*) FILTER (WHERE fecha_ultimo_servicio IS NULL OR (CURRENT_DATE - fecha_ultimo_servicio) > 90) as riesgo
            FROM taller_bitacora_vehiculo;
        """)
        resumen_flota = cr.dictfetchone() or {
            'total_vehiculos': 0, 'activos': 0, 'alerta': 0, 'riesgo': 0
        }

        # 7. Total Anual Facturado Taller para el año del periodo seleccionado
        query_year = f"""
            SELECT 
                COALESCE(SUM(amount_untaxed_signed), 0.0) as subtotal_anual,
                COALESCE(SUM(amount_total_signed), 0.0) as total_anual
            FROM account_move
            WHERE move_type IN ('out_invoice', 'out_refund')
              AND state = 'posted'
              AND es_taller = True
              AND invoice_date >= %s AND invoice_date <= %s
              {comp_cond}
        """
        last_day_of_year = date(year, 12, 31)
        cr.execute(query_year, (first_year, last_day_of_year))
        row_year = cr.dictfetchone() or {}
        total_anual_subtotal = float(row_year.get('subtotal_anual') or 0.0)
        total_anual_con_iva = float(row_year.get('total_anual') or 0.0)

        # 8. Meses disponibles para el selector interactivo
        query_available_months = f"""
            SELECT DISTINCT
                EXTRACT(YEAR FROM invoice_date)::int as anio,
                EXTRACT(MONTH FROM invoice_date)::int as mes
            FROM account_move
            WHERE move_type IN ('out_invoice', 'out_refund')
              AND state = 'posted'
              AND es_taller = True
              AND invoice_date IS NOT NULL
              {comp_cond}
            ORDER BY anio DESC, mes DESC
            LIMIT 24;
        """
        cr.execute(query_available_months)
        available_months = []
        found_selected = False
        for r in cr.dictfetchall():
            y, m = r['anio'], r['mes']
            k = f"{y}-{m:02d}"
            if y == year and m == month:
                found_selected = True
            available_months.append({
                'key': k,
                'year': y,
                'month': m,
                'nombre': f"{month_names.get(m, str(m))} {y}",
                'selected': (y == year and m == month),
            })
        if not found_selected:
            k = f"{year}-{month:02d}"
            available_months.insert(0, {
                'key': k,
                'year': year,
                'month': month,
                'nombre': f"{month_names.get(month, str(month))} {year}",
                'selected': True,
            })

        # 9. Histórico mensual de los últimos 12 meses
        query_history = f"""
            SELECT 
                TO_CHAR(invoice_date, 'YYYY-MM') as ym,
                EXTRACT(YEAR FROM invoice_date)::int as anio,
                EXTRACT(MONTH FROM invoice_date)::int as mes,
                COUNT(id) as facturas,
                COALESCE(SUM(amount_untaxed_signed), 0.0) as subtotal,
                COALESCE(SUM(amount_total_signed), 0.0) as total,
                COALESCE(SUM(amounts.mo), 0.0) as mo,
                COALESCE(SUM(amounts.rep), 0.0) as rep,
                COALESCE(SUM(amounts.ext), 0.0) as ext
            FROM account_move
            {category_join}
            WHERE move_type IN ('out_invoice', 'out_refund')
              AND state = 'posted'
              AND es_taller = True
              AND invoice_date IS NOT NULL
              {comp_cond}
            GROUP BY ym, anio, mes
            ORDER BY ym DESC
            LIMIT 12;
        """
        cr.execute(query_history)
        historico_mensual = []
        for h in cr.dictfetchall():
            m_num = h['mes']
            y_num = h['anio']
            subtot = float(h['subtotal'] or 0.0)
            tot = float(h['total'] or 0.0)
            mo = float(h['mo'] or 0.0)
            rep = float(h['rep'] or 0.0)
            ext = float(h['ext'] or 0.0)
            historico_mensual.append({
                'key': h['ym'],
                'year': y_num,
                'month': m_num,
                'nombre': f"{month_names.get(m_num, str(m_num))} {y_num}",
                'facturas': int(h['facturas'] or 0),
                'subtotal': subtot,
                'subtotal_fmt': f"${subtot:,.2f}",
                'total': tot,
                'total_fmt': f"${tot:,.2f}",
                'mo_fmt': f"${mo:,.2f}",
                'rep_fmt': f"${rep:,.2f}",
                'ext_fmt': f"${ext:,.2f}",
                'pct_mo': round((mo / subtot * 100.0), 1) if subtot > 0 else 0.0,
                'is_selected': (y_num == year and m_num == month),
            })

        return {
            'selected_period': f"{year}-{month:02d}",
            'selected_year': year,
            'selected_month': month,
            'is_current_month': (year == today.year and month == today.month),
            'first_day': first_this_month.strftime('%Y-%m-%d'),
            'last_day': last_this_month.strftime('%Y-%m-%d'),
            'available_months': available_months,
            'historico_mensual': historico_mensual,
            'mes_actual': {
                'nombre': mes_actual_nombre,
                'total': mes_actual_subtotal,
                'total_fmt': f"${mes_actual_subtotal:,.2f}",
                'subtotal': mes_actual_subtotal,
                'subtotal_fmt': f"${mes_actual_subtotal:,.2f}",
                'total_con_iva': mes_actual_total_con_iva,
                'total_con_iva_fmt': f"${mes_actual_total_con_iva:,.2f}",
                'mo': mes_actual_mo,
                'mo_fmt': f"${mes_actual_mo:,.2f}",
                'rep': mes_actual_rep,
                'rep_fmt': f"${mes_actual_rep:,.2f}",
                'pct_mo': pct_mo,
                'pct_rep': pct_rep,
                'ext': mes_actual_ext,
                'ext_fmt': f"${mes_actual_ext:,.2f}",
                'pct_ext': pct_ext,
                'facturas': facturas_mes,
            },
            'mes_anterior': {
                'nombre': mes_anterior_nombre,
                'total': mes_anterior_subtotal,
                'total_fmt': f"${mes_anterior_subtotal:,.2f}",
                'subtotal': mes_anterior_subtotal,
                'subtotal_fmt': f"${mes_anterior_subtotal:,.2f}",
                'total_con_iva': mes_anterior_total_con_iva,
                'total_con_iva_fmt': f"${mes_anterior_total_con_iva:,.2f}",
                'facturas': facturas_mes_anterior,
            },
            'variacion': {
                'pct': round(abs(var_pct), 1),
                'positiva': var_pct >= 0,
                'texto': f"{'+' if var_pct >= 0 else '-'}{abs(var_pct):.1f}% vs mes anterior",
            },
            'total_anual': {
                'monto': total_anual_subtotal,
                'monto_fmt': f"${total_anual_subtotal:,.2f}",
                'monto_con_iva': total_anual_con_iva,
                'monto_con_iva_fmt': f"${total_anual_con_iva:,.2f}",
                'anio': year,
            },
            'flota': resumen_flota,
            'top_clientes': top_clientes,
            'top_mecanicos': top_mecanicos,
            'vehiculos_riesgo': vehiculos_riesgo,
        }

    def init(self):

        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            WITH invoice_labor AS (
                SELECT 
                    am.id AS invoice_id,
                    COALESCE(
                        (
                            SELECT E'• ' || string_agg(
                                DISTINCT regexp_replace(
                                    regexp_replace(aml.name, '^[0-9]+\.\s*', ''), 
                                    '^\\[[^\\]]+\\]\s*', ''
                                ), 
                                E'\\n• '
                            )
                            FROM account_move_line aml
                            WHERE aml.move_id = am.id 
                              AND aml.display_type = 'product'
                              AND aml.es_mano_de_obra = True
                        ),
                        (
                            SELECT E'• ' || string_agg(regexp_replace(aml.name, '^\\[[^\\]]+\\]\s*', ''), E'\\n• ')
                            FROM (
                                SELECT aml.name 
                                FROM account_move_line aml 
                                WHERE aml.move_id = am.id AND aml.display_type = 'product' 
                                ORDER BY aml.id 
                                LIMIT 3
                            ) aml
                        )
                    ) AS labor_description
                FROM account_move am
                WHERE am.x_placa_vehiculo IS NOT NULL 
                  AND TRIM(am.x_placa_vehiculo) != ''
                  AND am.move_type = 'out_invoice'
                  AND am.state = 'posted'
            ),
            invoice_lines_calc AS (
                SELECT 
                    am.id AS invoice_id,
                    COALESCE(SUM(aml.price_subtotal) FILTER (
                        WHERE aml.display_type = 'product'
                          AND aml.es_mano_de_obra = True
                    ), 0.0) AS labor_amount,
                    COALESCE(SUM(aml.price_subtotal) FILTER (
                        WHERE aml.display_type = 'product'
                          AND (aml.es_mano_de_obra IS NOT TRUE)
                    ), 0.0) AS parts_amount
                FROM account_move am
                JOIN account_move_line aml ON aml.move_id = am.id
                WHERE am.x_placa_vehiculo IS NOT NULL 
                  AND TRIM(am.x_placa_vehiculo) != ''
                  AND am.move_type = 'out_invoice'
                  AND am.state = 'posted'
                GROUP BY am.id
            ),
            order_labor AS (
                SELECT 
                    s.id AS order_id,
                    COALESCE(
                        (
                            SELECT E'• ' || string_agg(
                                DISTINCT regexp_replace(
                                    regexp_replace(sol.name, '^[0-9]+\.\s*', ''), 
                                    '^\\[[^\\]]+\\]\s*', ''
                                ), 
                                E'\\n• '
                            )
                            FROM sale_order_line sol
                            WHERE sol.order_id = s.id 
                              AND (sol.display_type IS NULL OR sol.display_type = '')
                              AND sol.es_mano_de_obra = True
                        ),
                        (
                            SELECT E'• ' || string_agg(regexp_replace(sol.name, '^\\[[^\\]]+\\]\s*', ''), E'\\n• ')
                            FROM (
                                SELECT sol.name 
                                FROM sale_order_line sol 
                                WHERE sol.order_id = s.id AND (sol.display_type IS NULL OR sol.display_type = '') 
                                ORDER BY sol.id 
                                LIMIT 3
                            ) sol
                        )
                    ) AS labor_description
                FROM sale_order s
                WHERE s.x_placa_vehiculo IS NOT NULL 
                  AND TRIM(s.x_placa_vehiculo) != ''
            ),
            order_lines_calc AS (
                SELECT 
                    s.id AS order_id,
                    COALESCE(SUM(sol.price_subtotal) FILTER (
                        WHERE (sol.display_type IS NULL OR sol.display_type = '')
                          AND sol.es_mano_de_obra = True
                    ), 0.0) AS labor_amount,
                    COALESCE(SUM(sol.price_subtotal) FILTER (
                        WHERE (sol.display_type IS NULL OR sol.display_type = '')
                          AND (sol.es_mano_de_obra IS NOT TRUE)
                    ), 0.0) AS parts_amount
                FROM sale_order s
                JOIN sale_order_line sol ON sol.order_id = s.id
                WHERE s.x_placa_vehiculo IS NOT NULL 
                  AND TRIM(s.x_placa_vehiculo) != ''
                GROUP BY s.id
            ),
            invoices_by_plate AS (
                SELECT 
                    UPPER(REGEXP_REPLACE(TRIM(am.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) AS clean_plate,
                    am.company_id,
                    MIN(am.id) AS min_inv_id,
                    (ARRAY_AGG(am.id ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.move_type = 'out_invoice'))[1] AS latest_invoice_id,
                    (ARRAY_AGG(am.x_placa_vehiculo ORDER BY am.invoice_date DESC, am.id DESC))[1] AS inv_placa,
                    (ARRAY_AGG(am.partner_id ORDER BY am.invoice_date DESC, am.id DESC))[1] AS inv_partner_id,
                    (ARRAY_AGG(am.x_marca_vehiculo ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_marca_vehiculo IS NOT NULL AND TRIM(am.x_marca_vehiculo) != ''))[1] AS inv_marca,
                    (ARRAY_AGG(am.x_modelo_vehiculo ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_modelo_vehiculo IS NOT NULL AND TRIM(am.x_modelo_vehiculo) != ''))[1] AS inv_modelo,
                    (ARRAY_AGG(am.x_ano_vehiculo ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_ano_vehiculo IS NOT NULL AND TRIM(am.x_ano_vehiculo) != ''))[1] AS inv_ano,
                    (ARRAY_AGG(am.x_tipo_vehiculo ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_tipo_vehiculo IS NOT NULL AND TRIM(am.x_tipo_vehiculo) != ''))[1] AS inv_tipo_vehiculo,
                    (ARRAY_AGG(am.x_vin ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_vin IS NOT NULL AND TRIM(am.x_vin) != ''))[1] AS inv_vin,
                    (ARRAY_AGG(am.x_motor_vehiculo ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_motor_vehiculo IS NOT NULL AND TRIM(am.x_motor_vehiculo) != ''))[1] AS inv_motor,
                    (ARRAY_AGG(am.x_chasis_vehiculo ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_chasis_vehiculo IS NOT NULL AND TRIM(am.x_chasis_vehiculo) != ''))[1] AS inv_chasis,
                    (ARRAY_AGG(am.x_klms_vehiculo ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_klms_vehiculo IS NOT NULL AND TRIM(am.x_klms_vehiculo) != ''))[1] AS inv_kilometraje,
                    MAX(am.invoice_date) AS max_invoice_date,
                    (ARRAY_AGG(am.amount_total_signed ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.move_type = 'out_invoice'))[1] AS monto_ultima_factura,
                    (ARRAY_AGG(COALESCE(ilc.labor_amount, 0.0) ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.move_type = 'out_invoice'))[1] AS monto_mano_obra,
                    (ARRAY_AGG(COALESCE(ilc.parts_amount, 0.0) ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.move_type = 'out_invoice'))[1] AS monto_repuestos,
                    (ARRAY_AGG(am.mecanico_id ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.mecanico_id IS NOT NULL))[1] AS inv_mecanico_id,
                    (ARRAY_AGG(am.x_detalle_mecanico ORDER BY am.invoice_date DESC, am.id DESC) FILTER (WHERE am.x_detalle_mecanico IS NOT NULL AND TRIM(am.x_detalle_mecanico) != ''))[1] AS inv_detalle_mecanico,
                    SUM(CASE WHEN am.move_type = 'out_invoice' THEN am.amount_untaxed_signed WHEN am.move_type = 'out_refund' THEN -am.amount_untaxed_signed ELSE 0 END) AS total_facturado,
                    SUM(COALESCE(ilc.labor_amount, 0.0)) AS total_mano_obra,
                    SUM(COALESCE(ilc.parts_amount, 0.0)) AS total_repuestos,
                    COUNT(DISTINCT am.id) FILTER (WHERE am.move_type = 'out_invoice') AS cant_facturas,
                    (ARRAY_AGG(am.currency_id ORDER BY am.invoice_date DESC, am.id DESC))[1] AS inv_currency_id
                FROM account_move am
                LEFT JOIN invoice_lines_calc ilc ON ilc.invoice_id = am.id
                WHERE am.x_placa_vehiculo IS NOT NULL 
                  AND TRIM(am.x_placa_vehiculo) != ''
                  AND UPPER(REGEXP_REPLACE(TRIM(am.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) NOT IN ('NT', 'NA', 'SINPLACA')
                  AND LENGTH(REGEXP_REPLACE(TRIM(am.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) >= 2
                  AND am.move_type IN ('out_invoice', 'out_refund')
                  AND am.state = 'posted'
                  AND am.es_taller = True
                GROUP BY UPPER(REGEXP_REPLACE(TRIM(am.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')), am.company_id
            ),
            orders_by_plate AS (
                SELECT 
                    UPPER(REGEXP_REPLACE(TRIM(s.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) AS clean_plate,
                    s.company_id,
                    MIN(s.id) AS min_id,
                    (ARRAY_AGG(s.id ORDER BY s.date_order DESC, s.id DESC))[1] AS latest_order_id,
                    (ARRAY_AGG(s.amount_total ORDER BY s.date_order DESC, s.id DESC))[1] AS monto_ultimo_presupuesto,
                    (ARRAY_AGG(COALESCE(olc.labor_amount, 0.0) ORDER BY s.date_order DESC, s.id DESC))[1] AS monto_mano_obra_ord,
                    (ARRAY_AGG(COALESCE(olc.parts_amount, 0.0) ORDER BY s.date_order DESC, s.id DESC))[1] AS monto_repuestos_ord,
                    (ARRAY_AGG(s.x_placa_vehiculo ORDER BY s.date_order DESC, s.id DESC))[1] AS placa,
                    (ARRAY_AGG(s.partner_id ORDER BY s.date_order DESC, s.id DESC))[1] AS partner_id,
                    (ARRAY_AGG(s.x_marca_vehiculo ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_marca_vehiculo IS NOT NULL AND TRIM(s.x_marca_vehiculo) != ''))[1] AS marca,
                    (ARRAY_AGG(s.x_modelo_vehiculo ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_modelo_vehiculo IS NOT NULL AND TRIM(s.x_modelo_vehiculo) != ''))[1] AS modelo,
                    (ARRAY_AGG(s.x_ano_vehiculo ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_ano_vehiculo IS NOT NULL AND TRIM(s.x_ano_vehiculo) != ''))[1] AS ano,
                    (ARRAY_AGG(s.x_tipo_vehiculo ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_tipo_vehiculo IS NOT NULL AND TRIM(s.x_tipo_vehiculo) != ''))[1] AS tipo_vehiculo,
                    (ARRAY_AGG(s.x_vin ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_vin IS NOT NULL AND TRIM(s.x_vin) != ''))[1] AS vin,
                    (ARRAY_AGG(s.x_motor_vehiculo ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_motor_vehiculo IS NOT NULL AND TRIM(s.x_motor_vehiculo) != ''))[1] AS motor,
                    (ARRAY_AGG(s.x_chasis_vehiculo ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_chasis_vehiculo IS NOT NULL AND TRIM(s.x_chasis_vehiculo) != ''))[1] AS chasis,
                    (ARRAY_AGG(s.x_klms_vehiculo ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_klms_vehiculo IS NOT NULL AND TRIM(s.x_klms_vehiculo) != ''))[1] AS kilometraje,
                    (ARRAY_AGG(s.mecanico_id ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.mecanico_id IS NOT NULL))[1] AS ord_mecanico_id,
                    (ARRAY_AGG(s.x_detalle_mecanico ORDER BY s.date_order DESC, s.id DESC) FILTER (WHERE s.x_detalle_mecanico IS NOT NULL AND TRIM(s.x_detalle_mecanico) != ''))[1] AS ord_detalle_mecanico,
                    MAX(s.date_order::date) AS max_order_date,
                    SUM(COALESCE(olc.labor_amount, 0.0)) AS total_mano_obra_ord,
                    SUM(COALESCE(olc.parts_amount, 0.0)) AS total_repuestos_ord,
                    COUNT(s.id) AS cant_ordenes,
                    (ARRAY_AGG(s.currency_id ORDER BY s.date_order DESC, s.id DESC))[1] AS currency_id
                FROM sale_order s
                LEFT JOIN order_lines_calc olc ON olc.order_id = s.id
                WHERE s.x_placa_vehiculo IS NOT NULL 
                  AND TRIM(s.x_placa_vehiculo) != ''
                  AND UPPER(REGEXP_REPLACE(TRIM(s.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) NOT IN ('NT', 'NA', 'SINPLACA')
                  AND LENGTH(REGEXP_REPLACE(TRIM(s.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) >= 2
                  AND s.es_taller = True
                GROUP BY UPPER(REGEXP_REPLACE(TRIM(s.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')), s.company_id
            )
            SELECT 
                COALESCE(o.min_id, i.min_inv_id + 50000000) AS id,
                COALESCE(o.placa, i.inv_placa) AS placa,
                COALESCE(o.clean_plate, i.clean_plate) AS clean_plate,
                COALESCE(o.partner_id, i.inv_partner_id) AS partner_id,
                COALESCE(o.marca, i.inv_marca) AS marca,
                COALESCE(o.modelo, i.inv_modelo) AS modelo,
                COALESCE(o.ano, i.inv_ano) AS ano,
                COALESCE(o.tipo_vehiculo, i.inv_tipo_vehiculo) AS tipo_vehiculo,
                COALESCE(o.vin, i.inv_vin) AS vin,
                COALESCE(o.motor, i.inv_motor) AS motor,
                COALESCE(o.chasis, i.inv_chasis) AS chasis,
                COALESCE(o.kilometraje, i.inv_kilometraje) AS kilometraje,
                i.latest_invoice_id AS latest_invoice_id,
                o.latest_order_id AS latest_order_id,
                COALESCE(o.monto_ultimo_presupuesto, 0.0) AS monto_ultimo_presupuesto,
                COALESCE(il.labor_description, ol.labor_description) AS ultimo_servicio_realizado,
                COALESCE(i.inv_mecanico_id, o.ord_mecanico_id) AS mecanico_id,
                COALESCE(i.inv_detalle_mecanico, o.ord_detalle_mecanico) AS mecanico_nombre,
                COALESCE(i.max_invoice_date, o.max_order_date) AS fecha_ultimo_servicio,
                COALESCE(i.monto_ultima_factura, 0.0) AS monto_ultima_factura,
                COALESCE(i.monto_mano_obra, o.monto_mano_obra_ord, 0.0) AS monto_mano_obra,
                COALESCE(i.monto_repuestos, o.monto_repuestos_ord, 0.0) AS monto_repuestos,
                COALESCE(i.total_facturado, 0.0) AS total_facturado,
                COALESCE(i.total_mano_obra, o.total_mano_obra_ord, 0.0) AS total_mano_obra,
                COALESCE(i.total_repuestos, o.total_repuestos_ord, 0.0) AS total_repuestos,
                COALESCE(i.cant_facturas, 0) AS cantidad_facturas,
                COALESCE(o.cant_ordenes, 0) AS cantidad_ordenes,
                COALESCE(o.company_id, i.company_id) AS company_id,
                COALESCE(o.currency_id, i.inv_currency_id) AS currency_id
            FROM orders_by_plate o
            FULL OUTER JOIN invoices_by_plate i 
              ON i.clean_plate = o.clean_plate 
             AND (i.company_id = o.company_id OR (i.company_id IS NULL AND o.company_id IS NULL))
            LEFT JOIN invoice_labor il ON il.invoice_id = i.latest_invoice_id
            LEFT JOIN order_labor ol ON ol.order_id = o.latest_order_id
        """)

        # Sincronizar clientes de taller en res_partner una vez creada la vista
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'res_partner' AND column_name = 'es_cliente_taller';
        """)
        if self.env.cr.fetchone():
            self.env.cr.execute("""
                UPDATE res_partner p
                SET es_cliente_taller = True
                WHERE EXISTS (
                    SELECT 1 FROM taller_bitacora_vehiculo tbv
                    WHERE tbv.partner_id = p.id
                )
                OR EXISTS (
                    SELECT 1 FROM account_move am
                    WHERE am.partner_id = p.id
                      AND am.move_type IN ('out_invoice', 'out_refund')
                      AND am.state = 'posted'
                      AND am.es_taller = True
                      AND (am.company_id IS NULL OR am.company_id IN (SELECT id FROM res_company WHERE name ILIKE '%GRUPO 2%'))
                );
            """)


