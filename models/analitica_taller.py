# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AnaliticaTaller(models.Model):
    _name = 'analitica.taller'
    _description = 'Analítica y Rentabilidad de Taller G2'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_inicio desc, id desc'

    name = fields.Char(
        string='Referencia / Código',
        required=True,
        copy=False,
        default=lambda self: _('Nuevo'),
        tracking=True,
    )
    taller_nombre = fields.Char(
        string='Nombre del Centro / Área de Taller',
        required=True,
        tracking=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Cuenta Analítica',
        tracking=True,
        help='Cuenta analítica de Odoo asociada para acumular ingresos y costos automáticamente.'
    )
    analytic_line_count = fields.Integer(
        string='Apuntes Analíticos',
        compute='_compute_analytic_line_count',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env['res.company'].search([('name', 'ilike', 'GRUPO 2')], limit=1) or self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Moneda',
        readonly=True,
    )
    responsable_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
    )
    fecha_inicio = fields.Date(
        string='Fecha Inicio',
        default=fields.Date.context_today,
        tracking=True,
    )
    fecha_fin = fields.Date(
        string='Fecha Fin',
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('in_progress', 'En Progreso'),
        ('done', 'Finalizado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='draft', required=True, tracking=True)

    costo_estimado = fields.Monetary(
        string='Costo Presupuestado',
        currency_field='currency_id',
        tracking=True,
        help='Costo proyectado o presupuesto asignado para este centro de costo o trabajo.'
    )
    costo_real = fields.Monetary(
        string='Costo Real (Egresos)',
        currency_field='currency_id',
        compute='_compute_reales_desde_analitica',
        store=True,
        readonly=False,
        precompute=True,
        tracking=True,
        help='Monto total de costos y egresos deducidos de la cuenta analítica o capturados manualmente.'
    )
    ingreso_estimado = fields.Monetary(
        string='Ingreso Proyectado',
        currency_field='currency_id',
        tracking=True,
        help='Meta o proyección de facturación para este centro de costos.'
    )
    ingreso_real = fields.Monetary(
        string='Ingreso Real (Ventas)',
        currency_field='currency_id',
        compute='_compute_reales_desde_analitica',
        store=True,
        readonly=False,
        precompute=True,
        tracking=True,
        help='Monto total facturado deducido de la cuenta analítica o capturado manualmente.'
    )
    margen_real = fields.Monetary(
        string='Margen Operativo',
        currency_field='currency_id',
        compute='_compute_margen_real',
        store=True,
        tracking=True,
        help='Diferencia entre Ingresos Reales y Costos Reales.'
    )
    porcentaje_margen = fields.Float(
        string='% Margen',
        compute='_compute_margen_real',
        store=True,
        help='Porcentaje de rentabilidad: Margen / Ingreso Real.'
    )
    notas = fields.Html(string='Notas / Observaciones')

    @api.depends('analytic_account_id')
    def _compute_analytic_line_count(self):
        for rec in self:
            if rec.analytic_account_id:
                rec.analytic_line_count = self.env['account.analytic.line'].search_count([
                    ('account_id', '=', rec.analytic_account_id.id)
                ])
            else:
                rec.analytic_line_count = 0

    @api.depends('analytic_account_id', 'fecha_inicio', 'fecha_fin')
    def _compute_reales_desde_analitica(self):
        for record in self:
            if record.analytic_account_id:
                domain = [('account_id', '=', record.analytic_account_id.id)]
                if record.fecha_inicio:
                    domain.append(('date', '>=', record.fecha_inicio))
                if record.fecha_fin:
                    domain.append(('date', '<=', record.fecha_fin))
                lines = self.env['account.analytic.line'].search(domain)
                
                # En líneas analíticas de Odoo:
                # amount > 0 = Ingreso / Crédito
                # amount < 0 = Gasto / Débito
                ingresos = sum(l.amount for l in lines if l.amount > 0)
                costos = abs(sum(l.amount for l in lines if l.amount < 0))
                
                record.ingreso_real = ingresos
                record.costo_real = costos

    @api.depends('ingreso_real', 'costo_real')
    def _compute_margen_real(self):
        for record in self:
            margen = (record.ingreso_real or 0.0) - (record.costo_real or 0.0)
            record.margen_real = margen
            if record.ingreso_real:
                record.porcentaje_margen = (margen / record.ingreso_real)
            else:
                record.porcentaje_margen = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.name or rec.name == _('Nuevo'):
                rec.name = f"ATG2-{rec.id:04d}"
        return records

    def action_create_analytic_account(self):
        """Crea automáticamente una cuenta analítica vinculada al plan de proyectos."""
        self.ensure_one()
        if not self.analytic_account_id:
            plan = self.env['account.analytic.plan'].search([], limit=1)
            account_vals = {
                'name': f"{self.name} - {self.taller_nombre}",
                'company_id': self.company_id.id if self.company_id else False,
            }
            if plan:
                account_vals['plan_id'] = plan.id
            analytic_acc = self.env['account.analytic.account'].create(account_vals)
            self.analytic_account_id = analytic_acc.id
            self.message_post(body=_(
                "Cuenta analítica creada automáticamente: <b>%s</b>"
            ) % analytic_acc.name)

    def action_view_analytic_lines(self):
        """Abre la lista de apuntes analíticos contables de este centro de costos."""
        self.ensure_one()
        domain = [('account_id', '=', self.analytic_account_id.id)] if self.analytic_account_id else [('id', '=', 0)]
        return {
            'name': _('Apuntes Analíticos - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form,pivot,graph',
            'domain': domain,
            'context': {
                'default_account_id': self.analytic_account_id.id if self.analytic_account_id else False,
            }
        }

    def action_recalculate_metrics(self):
        """Fuerza la sincronización y cálculo de ingresos, costos y márgenes."""
        self._compute_reales_desde_analitica()
        self._compute_margen_real()
        for record in self:
            record.message_post(body=_(
                "Métricas actualizadas desde contabilidad analítica:<br/>"
                "• <b>Ingreso Real:</b> %s<br/>"
                "• <b>Costo Real:</b> %s<br/>"
                "• <b>Margen Operativo:</b> %s (%.2f%%)"
            ) % (
                record.ingreso_real,
                record.costo_real,
                record.margen_real,
                (record.porcentaje_margen or 0.0) * 100
            ))

    def action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})
