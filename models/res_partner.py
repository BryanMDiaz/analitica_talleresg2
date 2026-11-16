# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta


class ResPartner(models.Model):
    _inherit = 'res.partner'

    taller_currency_id = fields.Many2one(
        'res.currency',
        string="Moneda (Talleres G2)",
        compute='_compute_taller_currency_id'
    )

    @api.depends('company_id')
    def _compute_taller_currency_id(self):
        g2_company = self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')], limit=1)
        default_currency = (g2_company and g2_company.currency_id) or self.env.company.currency_id
        for partner in self:
            partner.taller_currency_id = default_currency

    taller_last_purchase_date = fields.Date(
        string="Fecha Últ. Servicio",
        compute="_compute_taller_purchase_stats",
        store=True,
    )
    taller_last_purchase_amount = fields.Monetary(
        string="Monto Últ. Servicio",
        compute="_compute_taller_purchase_stats",
        currency_field='taller_currency_id',
        store=True,
    )
    taller_total_purchase = fields.Monetary(
        string="Total Histórico",
        compute="_compute_taller_purchase_stats",
        currency_field='taller_currency_id',
        store=True,
    )
    taller_purchase_count = fields.Integer(
        string="Cant. Facturas",
        compute="_compute_taller_purchase_stats",
        store=True,
    )
    taller_average_ticket = fields.Monetary(
        string="Gasto Promedio",
        compute="_compute_taller_purchase_stats",
        currency_field='taller_currency_id',
        store=True,
    )
    taller_days_since_purchase = fields.Integer(
        string="Días sin Servicio",
        compute="_compute_taller_purchase_stats",
        search="_search_taller_days_since_purchase",
        store=True,
    )
    taller_next_purchase_prob = fields.Date(
        string="Próximo Servicio Estimado",
        compute="_compute_taller_purchase_stats",
        store=True,
    )
    taller_avg_days_between = fields.Float(
        string="Frecuencia Habitual (Días)",
        compute="_compute_taller_purchase_stats",
        store=True,
    )
    es_cliente_taller = fields.Boolean(
        string="Es Cliente de Taller",
        compute="_compute_es_cliente_taller",
        store=True,
        index=True,
        help="Indica si el contacto tiene etiqueta de taller o registra facturas/servicios automotrices."
    )

    @api.depends('category_id', 'taller_purchase_count')
    def _compute_es_cliente_taller(self):
        for partner in self:
            is_tagged = any('talleres' in (cat.name or '').lower() for cat in partner.category_id)
            partner.es_cliente_taller = bool(is_tagged or (partner.taller_purchase_count and partner.taller_purchase_count > 0))

    taller_invoice_ids = fields.One2many(
        'account.move',
        'partner_id',
        string="Facturas de Talleres G2",
        domain=[
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('company_id.name', 'ilike', 'GRUPO 2'),
            ('es_taller', '=', True),
        ]
    )

    @api.depends(
        'taller_invoice_ids',
        'taller_invoice_ids.state',
        'taller_invoice_ids.move_type',
        'taller_invoice_ids.invoice_date',
        'taller_invoice_ids.amount_untaxed_signed',
        'taller_invoice_ids.company_id',
        'taller_invoice_ids.es_taller',
    )
    def _compute_taller_purchase_stats(self):
        partner_ids = set(self.ids)
        commercial_ids = set(self.mapped('commercial_partner_id').ids)
        all_target_ids = list(partner_ids | commercial_ids)

        g2_company = self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')], limit=1)
        company_domain = [('company_id', '=', g2_company.id)] if g2_company else []

        if all_target_ids:
            all_invoices = self.env['account.move'].search([
                '|',
                ('commercial_partner_id', 'in', all_target_ids),
                ('partner_id', 'in', all_target_ids),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
                ('es_taller', '=', True),
            ] + company_domain, order='invoice_date desc, id desc')
        else:
            all_invoices = self.env['account.move']

        invoices_by_comm_id = {}
        invoices_by_partner_id = {}
        for inv in all_invoices:
            c_id = inv.commercial_partner_id.id
            p_id = inv.partner_id.id
            if c_id:
                invoices_by_comm_id.setdefault(c_id, []).append(inv)
            if p_id:
                invoices_by_partner_id.setdefault(p_id, []).append(inv)

        today = fields.Date.today()

        for partner in self:
            partner_invs = []
            seen_ids = set()
            candidate_invs = (
                invoices_by_partner_id.get(partner.id, []) +
                invoices_by_comm_id.get(partner.commercial_partner_id.id, [])
            )
            for inv in candidate_invs:
                if inv.id not in seen_ids:
                    seen_ids.add(inv.id)
                    partner_invs.append(inv)

            partner_invs.sort(key=lambda x: (x.invoice_date or fields.Date.min, x.id), reverse=True)
            sales_invoices = [inv for inv in partner_invs if inv.move_type == 'out_invoice']

            if not sales_invoices:
                partner.taller_last_purchase_date = False
                partner.taller_last_purchase_amount = 0.0
                partner.taller_total_purchase = 0.0
                partner.taller_purchase_count = 0
                partner.taller_average_ticket = 0.0
                partner.taller_days_since_purchase = False
                partner.taller_next_purchase_prob = False
                partner.taller_avg_days_between = 0.0
                continue

            partner.taller_last_purchase_date = sales_invoices[0].invoice_date
            partner.taller_last_purchase_amount = sales_invoices[0].amount_untaxed_signed
            partner.taller_total_purchase = sum(inv.amount_untaxed_signed for inv in partner_invs)
            partner.taller_purchase_count = len(sales_invoices)
            partner.taller_average_ticket = (
                partner.taller_total_purchase / partner.taller_purchase_count
                if partner.taller_purchase_count else 0.0
            )

            if partner.taller_last_purchase_date:
                delta = today - partner.taller_last_purchase_date
                partner.taller_days_since_purchase = delta.days
            else:
                partner.taller_days_since_purchase = False

            days_diffs = []
            if len(sales_invoices) > 1:
                for i in range(len(sales_invoices) - 1):
                    d1 = sales_invoices[i].invoice_date
                    d2 = sales_invoices[i + 1].invoice_date
                    if d1 and d2:
                        days_diffs.append(abs((d1 - d2).days))

            avg_days = sum(days_diffs) / len(days_diffs) if days_diffs else 0.0
            partner.taller_avg_days_between = avg_days
            if avg_days > 0 and partner.taller_last_purchase_date:
                partner.taller_next_purchase_prob = partner.taller_last_purchase_date + timedelta(days=int(avg_days))
            else:
                partner.taller_next_purchase_prob = False

    def _search_taller_days_since_purchase(self, operator, value):
        target_date = fields.Date.today() - timedelta(days=value)
        g2_company = self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')], limit=1)
        comp_filter = f"AND company_id = {g2_company.id}" if g2_company else ""

        self.env.cr.execute(f"""
            SELECT commercial_partner_id, MAX(invoice_date) as last_date
            FROM account_move
            WHERE move_type = 'out_invoice' AND state = 'posted' AND es_taller = True AND commercial_partner_id IS NOT NULL {comp_filter}
            GROUP BY commercial_partner_id
        """)
        results = self.env.cr.dictfetchall()

        matched_partner_ids = []
        for row in results:
            last_date = row['last_date']
            if not last_date:
                continue

            if operator == '<=' and last_date >= target_date:
                matched_partner_ids.append(row['commercial_partner_id'])
            elif operator == '>' and last_date < target_date:
                matched_partner_ids.append(row['commercial_partner_id'])
            elif operator == '<' and last_date > target_date:
                matched_partner_ids.append(row['commercial_partner_id'])
            elif operator == '>=' and last_date <= target_date:
                matched_partner_ids.append(row['commercial_partner_id'])
            elif operator == '=' and last_date == target_date:
                matched_partner_ids.append(row['commercial_partner_id'])

        if operator in ('>', '>=') and value >= 90:
            self.env.cr.execute(f"""
                SELECT id FROM res_partner 
                WHERE id NOT IN (
                    SELECT DISTINCT commercial_partner_id FROM account_move WHERE move_type = 'out_invoice' AND state = 'posted' AND es_taller = True AND commercial_partner_id IS NOT NULL {comp_filter}
                )
            """)
            matched_partner_ids.extend([r[0] for r in self.env.cr.fetchall()])

        return [('id', 'in', matched_partner_ids)]

    def action_view_taller_invoices(self):
        self.ensure_one()
        view_id = self.env.ref('analitica_talleresg2.view_taller_reportes_ventas_list', raise_if_not_found=False)
        views = [(view_id.id, 'list')] if view_id else []
        views.append((False, 'form'))

        g2_company = self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')], limit=1)
        company_domain = [('company_id', '=', g2_company.id)] if g2_company else []

        return {
            'name': f'Facturas de {self.name} (GRUPO 2 S.A. DE C.V.)',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'views': views,
            'domain': [
                '|',
                ('partner_id', 'child_of', self.commercial_partner_id.id),
                ('commercial_partner_id', '=', self.commercial_partner_id.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
                ('es_taller', '=', True),
            ] + company_domain,
            'context': {
                'default_partner_id': self.id,
                'default_move_type': 'out_invoice',
                'default_company_id': g2_company.id if g2_company else False,
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

    def action_view_taller_vehicles(self):
        self.ensure_one()
        g2_company = self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')], limit=1)
        company_domain = [('company_id', '=', g2_company.id)] if g2_company else []
        return {
            'name': f'Vehículos de {self.name} (GRUPO 2 S.A. DE C.V.)',
            'type': 'ir.actions.act_window',
            'res_model': 'taller.bitacora.vehiculo',
            'view_mode': 'list,form',
            'domain': [
                '|',
                ('partner_id', 'child_of', self.commercial_partner_id.id),
                ('partner_id', '=', self.id),
            ] + company_domain,
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

    def get_registered_vehicles(self):
        """
        Retorna la lista de vehículos históricos pertenecientes a este cliente
        (consultando únicamente órdenes y facturas asociadas a su cuenta comercial).
        """
        self.ensure_one()
        partner_ids = tuple({self.id, self.commercial_partner_id.id} - {False})
        if not partner_ids:
            return []
        query = """
            WITH all_vehicles AS (
                SELECT 
                    s.x_placa_vehiculo,
                    s.clean_placa_vehiculo,
                    s.x_marca_vehiculo,
                    s.x_modelo_vehiculo,
                    s.x_ano_vehiculo,
                    s.x_tipo_vehiculo,
                    s.x_chasis_vehiculo,
                    s.x_motor_vehiculo,
                    s.x_vin,
                    s.x_nota_vehiculo,
                    s.date_order AS record_date
                FROM sale_order s
                WHERE s.partner_id IN %s 
                  AND s.clean_placa_vehiculo IS NOT NULL
                  AND s.clean_placa_vehiculo NOT IN ('NT', 'NA', 'SINPLACA')
                
                UNION ALL
                
                SELECT 
                    m.x_placa_vehiculo,
                    m.clean_placa_vehiculo,
                    m.x_marca_vehiculo,
                    m.x_modelo_vehiculo,
                    m.x_ano_vehiculo,
                    m.x_tipo_vehiculo,
                    m.x_chasis_vehiculo,
                    m.x_motor_vehiculo,
                    m.x_vin,
                    m.x_nota_vehiculo,
                    m.invoice_date::timestamp AS record_date
                FROM account_move m
                WHERE m.partner_id IN %s 
                  AND m.clean_placa_vehiculo IS NOT NULL
                  AND m.clean_placa_vehiculo NOT IN ('NT', 'NA', 'SINPLACA')
            )
            SELECT DISTINCT ON (clean_placa_vehiculo)
                x_placa_vehiculo AS placa,
                x_marca_vehiculo AS marca,
                x_modelo_vehiculo AS modelo,
                x_ano_vehiculo AS ano,
                x_tipo_vehiculo AS tipo_vehiculo,
                x_chasis_vehiculo AS chasis,
                x_motor_vehiculo AS motor,
                x_vin AS vin,
                x_nota_vehiculo AS nota
            FROM all_vehicles
            ORDER BY clean_placa_vehiculo, record_date DESC NULLS LAST;
        """
        self.env.cr.execute(query, (partner_ids, partner_ids))
        return self.env.cr.dictfetchall()

    @api.model
    def _cron_update_taller_purchase_stats(self):
        """Cron para recalcular campos sensibles al paso de los días para clientes de Talleres G2."""
        partners = self.search([
            '|',
            ('category_id.name', 'ilike', 'Talleres / Cliente'),
            ('es_cliente_taller', '=', True)
        ])
        partners._compute_taller_purchase_stats()

    def init(self):
        super().init()
        # 0. Verificar que la vista SQL taller_bitacora_vehiculo y columnas necesarias existan
        # para evitar error UndefinedTable en la instalación inicial o reinstalación del módulo
        self.env.cr.execute("SELECT to_regclass('taller_bitacora_vehiculo') IS NOT NULL;")
        if not self.env.cr.fetchone()[0]:
            return

        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'res_partner' AND column_name = 'es_cliente_taller';
        """)
        if not self.env.cr.fetchone():
            return

        # 1. Limpieza de etiquetas 'Talleres / Cliente' asignadas erróneamente a clientes de MasterShop sin servicios de taller
        self.env.cr.execute("""
            DELETE FROM res_partner_res_partner_category_rel rel
            USING res_partner_category cat
            WHERE cat.id = rel.category_id
              AND cat.name::text ILIKE '%Talleres / Cliente%'
              -- El contacto NO tiene vehículo en bitácora
              AND NOT EXISTS (
                  SELECT 1 FROM taller_bitacora_vehiculo tbv WHERE tbv.partner_id = rel.partner_id
              )
              -- El contacto NO tiene facturas de taller contabilizadas en Grupo 2
              AND NOT EXISTS (
                  SELECT 1 FROM account_move am
                  WHERE am.partner_id = rel.partner_id
                    AND am.move_type = 'out_invoice'
                    AND am.state = 'posted'
                    AND am.es_taller = True
                    AND (am.company_id IS NULL OR am.company_id IN (SELECT id FROM res_company WHERE name ILIKE '%GRUPO 2%'))
              )
              -- El contacto NO tiene cotizaciones/órdenes de taller con placa o mecánico
              AND NOT EXISTS (
                  SELECT 1 FROM sale_order so
                  WHERE so.partner_id = rel.partner_id
                    AND (
                        (so.x_placa_vehiculo IS NOT NULL AND TRIM(so.x_placa_vehiculo) != '' AND UPPER(TRIM(so.x_placa_vehiculo)) NOT IN ('NA', 'NT', 'SINPLACA'))
                        OR so.mecanico_id IS NOT NULL
                        OR so.x_detalle_mecanico IS NOT NULL
                    )
              );
        """)

        # 2. Sincronizar campo es_cliente_taller en SQL de forma estricta (solo clientes con vehículos o facturas de taller)
        self.env.cr.execute("""
            UPDATE res_partner
            SET es_cliente_taller = False;

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
