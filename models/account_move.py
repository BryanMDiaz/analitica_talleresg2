import re
import unicodedata
from odoo import models, fields, api
from .sale_order import is_mano_de_obra_section


class AccountMove(models.Model):
    _inherit = 'account.move'

    mecanico_id = fields.Many2one(
        'hr.employee',
        string='Mecánico',
        tracking=True,
        help='Mecánico asignado desde la lista de empleados'
    )
    x_detalle_mecanico = fields.Char(
        string='Detalle Mecánico',
        help='Nombre del mecánico asignado'
    )
    x_marca_vehiculo = fields.Char(string='Marca de Vehículo')
    x_modelo_vehiculo = fields.Char(string='Modelo de Vehículo')
    x_ano_vehiculo = fields.Char(string='Año de Vehículo')
    x_tipo_vehiculo = fields.Char(string='Tipo de Vehículo')
    x_placa_vehiculo = fields.Char(string='Placa de Vehículo')
    clean_placa_vehiculo = fields.Char(
        string='Placa Normalizada',
        compute='_compute_clean_placa_vehiculo',
        store=True,
        index=True,
        help='Placa unificada en mayúsculas y sin caracteres especiales para consolidar historial analítico.'
    )
    x_chasis_vehiculo = fields.Char(string='Chasis de Vehículo')
    x_motor_vehiculo = fields.Char(string='Motor de Vehículo')
    x_vin = fields.Char(string='VIN de Vehículo')
    x_nota_vehiculo = fields.Char(string='Información Adicional / Nota de Vehículo')
    x_klms_vehiculo = fields.Char(string='Kilometraje de Vehículo')
    x_millas_vehiculo = fields.Char(string='Millas de Vehículo')
    es_taller = fields.Boolean(
        string='Es Venta de Taller',
        compute='_compute_es_taller',
        store=True,
        index=True,
        help='Indica si la factura corresponde al Taller Automotriz (excluye ventas exclusivas de herramientas MasterShop).'
    )
    taller_monto_mano_obra = fields.Monetary(
        string='Monto Mano de Obra',
        compute='_compute_taller_montos',
        store=True,
        currency_field='currency_id',
        help='Monto subtotal correspondiente a mano de obra y servicios técnicos facturados.'
    )
    taller_monto_repuestos = fields.Monetary(
        string='Monto Repuestos / Insumos',
        compute='_compute_taller_montos',
        store=True,
        currency_field='currency_id',
        help='Monto subtotal correspondiente a repuestos, partes mecánicas y consumibles facturados.'
    )

    @api.depends('invoice_line_ids', 'invoice_line_ids.price_subtotal', 'invoice_line_ids.es_mano_de_obra', 'invoice_line_ids.display_type', 'move_type')
    def _compute_taller_montos(self):
        for move in self:
            sign = -1.0 if move.move_type == 'out_refund' else 1.0
            mo = 0.0
            rep = 0.0
            for line in move.invoice_line_ids:
                if line.display_type == 'product':
                    subtotal = (line.price_subtotal or 0.0) * sign
                    if line.es_mano_de_obra:
                        mo += subtotal
                    else:
                        rep += subtotal
            move.taller_monto_mano_obra = mo
            move.taller_monto_repuestos = rep


    @api.depends('x_placa_vehiculo')
    def _compute_clean_placa_vehiculo(self):
        for rec in self:
            if rec.x_placa_vehiculo:
                clean = re.sub(r'[^A-Za-z0-9]', '', rec.x_placa_vehiculo).upper()
                rec.clean_placa_vehiculo = clean if clean not in ('NT', 'NA', 'SINPLACA') and len(clean) >= 2 else False
            else:
                rec.clean_placa_vehiculo = False

    @api.depends('x_placa_vehiculo', 'mecanico_id', 'x_detalle_mecanico', 'invoice_line_ids', 'invoice_line_ids.product_id', 'invoice_line_ids.name')
    def _compute_es_taller(self):
        for move in self:
            # 1. Tiene placa de vehículo válida
            clean_plate = re.sub(r'[^A-Za-z0-9]', '', move.x_placa_vehiculo or '').upper()
            has_valid_plate = bool(clean_plate and clean_plate not in ('NT', 'NA', 'SINPLACA') and len(clean_plate) >= 2)

            # 2. Tiene mecánico asignado
            has_mecanico = bool(move.mecanico_id or (move.x_detalle_mecanico and move.x_detalle_mecanico.strip()))

            if has_valid_plate or has_mecanico:
                move.es_taller = True
                continue

            # 3. Analizar líneas para detectar si es venta de taller o de MasterShop
            has_workshop_labor = False
            has_mastershop_tool = False

            for line in move.invoice_line_ids:
                if line.display_type != 'product':
                    continue
                line_name = (line.name or '').upper()
                categ_name = (line.product_id.categ_id.name or '').upper() if line.product_id else ''
                prod_code = (line.product_id.default_code or '').upper() if line.product_id else ''

                if (
                    'MASTERSHOP' in line_name or
                    'HERRAMIENTAS MASTER SHOP' in line_name or
                    'HERRAMIENTA' in categ_name
                ):
                    has_mastershop_tool = True

                if (
                    line.es_mano_de_obra or
                    'SERVICIOS MOD' in categ_name or
                    prod_code.startswith('MOD') or
                    '[MOD' in line_name
                ):
                    has_workshop_labor = True

            # Si es herramienta de MasterShop sin placa ni mecánico, NO es taller
            if has_mastershop_tool:
                move.es_taller = False
            elif has_workshop_labor:
                move.es_taller = True
            else:
                move.es_taller = False

    @api.onchange('mecanico_id')
    def _onchange_mecanico_id(self):
        if self.mecanico_id:
            self.x_detalle_mecanico = self.mecanico_id.name

    @api.onchange('x_placa_vehiculo')
    def _onchange_x_placa_vehiculo_autocomplete(self):
        if not self.x_placa_vehiculo or not self.partner_id:
            return
        clean = re.sub(r'[^A-Za-z0-9]', '', str(self.x_placa_vehiculo)).upper()
        if not clean or clean in ('NT', 'NA', 'SINPLACA') or len(clean) < 2:
            return
            
        vehicles = self.partner_id.get_registered_vehicles()
        for v in vehicles:
            v_clean = re.sub(r'[^A-Za-z0-9]', '', str(v.get('placa') or '')).upper()
            if v_clean == clean:
                self.x_marca_vehiculo = v.get('marca') or False
                self.x_modelo_vehiculo = v.get('modelo') or False
                self.x_ano_vehiculo = v.get('ano') or False
                self.x_tipo_vehiculo = v.get('tipo_vehiculo') or False
                self.x_chasis_vehiculo = v.get('chasis') or False
                self.x_motor_vehiculo = v.get('motor') or False
                self.x_vin = v.get('vin') or False
                self.x_nota_vehiculo = v.get('nota') or False
                # Kilómetros y Millas siempre quedan vacíos
                self.x_klms_vehiculo = False
                self.x_millas_vehiculo = False
                break

    def action_open_vehicle_selector(self):
        self.ensure_one()
        if not self.partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Seleccionar Cliente',
                    'message': 'Por favor seleccione primero un cliente para ver sus vehículos registrados.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        vehicles = self.partner_id.get_registered_vehicles()
        if not vehicles:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Vehículos Previos',
                    'message': f'El cliente {self.partner_id.name} no tiene vehículos previos registrados. Puede ingresar los datos del nuevo vehículo directamente.',
                    'type': 'info',
                    'sticky': False,
                }
            }
            
        wizard = self.env['taller.seleccionar.vehiculo.wizard'].create({
            'move_id': self.id,
            'partner_id': self.partner_id.id,
            'line_ids': [(0, 0, v) for v in vehicles],
        })
        
        return {
            'name': f'Vehículos del Cliente - {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'taller.seleccionar.vehiculo.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.onchange('invoice_origin', 'invoice_line_ids')
    def _onchange_invoice_origin_vehiculo(self):
        sale_order = False
        if hasattr(self, 'invoice_line_ids') and self.invoice_line_ids:
            sale_lines = self.invoice_line_ids.mapped('sale_line_ids')
            if sale_lines:
                sale_order = sale_lines.mapped('order_id')
        if not sale_order and self.invoice_origin:
            origin = self.invoice_origin.split(',')[0].strip()
            sale_order = self.env['sale.order'].search([('name', '=', origin)], order='id desc', limit=1)
        if sale_order:
            self._copy_vehicle_data_from_sale(sale_order[0])

    def _copy_vehicle_data_from_sale(self, sale_order):
        fields_to_copy = [
            'mecanico_id', 'x_detalle_mecanico', 'x_marca_vehiculo',
            'x_modelo_vehiculo', 'x_ano_vehiculo', 'x_tipo_vehiculo',
            'x_placa_vehiculo', 'x_chasis_vehiculo', 'x_motor_vehiculo',
            'x_vin', 'x_nota_vehiculo', 'x_klms_vehiculo', 'x_millas_vehiculo'
        ]
        for f in fields_to_copy:
            if f in sale_order._fields and hasattr(self, f):
                val = getattr(sale_order, f)
                if f == 'mecanico_id':
                    setattr(self, f, val.id if val else False)
                else:
                    setattr(self, f, val)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('mecanico_id') and not vals.get('x_detalle_mecanico'):
                employee = self.env['hr.employee'].browse(vals['mecanico_id'])
                if employee.exists():
                    vals['x_detalle_mecanico'] = employee.name
            origin = vals.get('invoice_origin')
            if origin and not vals.get('x_placa_vehiculo') and not vals.get('mecanico_id'):
                clean_origin = origin.split(',')[0].strip()
                sale_order = self.env['sale.order'].search([('name', '=', clean_origin)], order='id desc', limit=1)
                if sale_order:
                    for f in [
                        'mecanico_id', 'x_detalle_mecanico', 'x_marca_vehiculo',
                        'x_modelo_vehiculo', 'x_ano_vehiculo', 'x_tipo_vehiculo',
                        'x_placa_vehiculo', 'x_chasis_vehiculo', 'x_motor_vehiculo',
                        'x_vin', 'x_nota_vehiculo', 'x_klms_vehiculo', 'x_millas_vehiculo'
                    ]:
                        if f in sale_order._fields and not vals.get(f):
                            val = getattr(sale_order, f)
                            vals[f] = val.id if f == 'mecanico_id' and val else val
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('mecanico_id'):
            employee = self.env['hr.employee'].browse(vals['mecanico_id'])
            if employee.exists():
                vals['x_detalle_mecanico'] = employee.name
        elif 'mecanico_id' in vals and not vals['mecanico_id']:
            vals['x_detalle_mecanico'] = False
        return super().write(vals)

    def init(self):
        super().init()
        # Sincronizar automáticamente facturas existentes desde sus pedidos de venta
        self.env.cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'account_move' AND column_name = 'x_placa_vehiculo';
        """)
        if self.env.cr.fetchone():
            # 1. Sincronización precisa por líneas de factura asociadas al pedido
            self.env.cr.execute("""
                UPDATE account_move m
                SET mecanico_id = COALESCE(so.mecanico_id, m.mecanico_id),
                    x_detalle_mecanico = COALESCE(so.x_detalle_mecanico, m.x_detalle_mecanico),
                    x_marca_vehiculo = COALESCE(so.x_marca_vehiculo, m.x_marca_vehiculo),
                    x_modelo_vehiculo = COALESCE(so.x_modelo_vehiculo, m.x_modelo_vehiculo),
                    x_ano_vehiculo = COALESCE(so.x_ano_vehiculo, m.x_ano_vehiculo),
                    x_tipo_vehiculo = COALESCE(so.x_tipo_vehiculo, m.x_tipo_vehiculo),
                    x_placa_vehiculo = COALESCE(so.x_placa_vehiculo, m.x_placa_vehiculo),
                    x_chasis_vehiculo = COALESCE(so.x_chasis_vehiculo, m.x_chasis_vehiculo),
                    x_motor_vehiculo = COALESCE(so.x_motor_vehiculo, m.x_motor_vehiculo),
                    x_vin = COALESCE(so.x_vin, m.x_vin),
                    x_nota_vehiculo = COALESCE(so.x_nota_vehiculo, m.x_nota_vehiculo),
                    x_klms_vehiculo = COALESCE(so.x_klms_vehiculo, m.x_klms_vehiculo),
                    x_millas_vehiculo = COALESCE(so.x_millas_vehiculo, m.x_millas_vehiculo)
                FROM (
                    SELECT DISTINCT ON (aml.move_id)
                        aml.move_id,
                        so.mecanico_id,
                        so.x_detalle_mecanico,
                        so.x_marca_vehiculo,
                        so.x_modelo_vehiculo,
                        so.x_ano_vehiculo,
                        so.x_tipo_vehiculo,
                        so.x_placa_vehiculo,
                        so.x_chasis_vehiculo,
                        so.x_motor_vehiculo,
                        so.x_vin,
                        so.x_nota_vehiculo,
                        so.x_klms_vehiculo,
                        so.x_millas_vehiculo
                    FROM account_move_line aml
                    JOIN sale_order_line_invoice_rel rel ON rel.invoice_line_id = aml.id
                    JOIN sale_order_line sol ON sol.id = rel.order_line_id
                    JOIN sale_order so ON so.id = sol.order_id
                    WHERE so.x_placa_vehiculo IS NOT NULL OR so.mecanico_id IS NOT NULL OR so.x_marca_vehiculo IS NOT NULL
                    ORDER BY aml.move_id, so.id DESC
                ) so
                WHERE m.id = so.move_id;
            """)
            # 2. Sincronización de respaldo por invoice_origin
            self.env.cr.execute("""
                UPDATE account_move m
                SET mecanico_id = COALESCE(m.mecanico_id, so.mecanico_id),
                    x_detalle_mecanico = COALESCE(m.x_detalle_mecanico, so.x_detalle_mecanico),
                    x_marca_vehiculo = COALESCE(m.x_marca_vehiculo, so.x_marca_vehiculo),
                    x_modelo_vehiculo = COALESCE(m.x_modelo_vehiculo, so.x_modelo_vehiculo),
                    x_ano_vehiculo = COALESCE(m.x_ano_vehiculo, so.x_ano_vehiculo),
                    x_tipo_vehiculo = COALESCE(m.x_tipo_vehiculo, so.x_tipo_vehiculo),
                    x_placa_vehiculo = COALESCE(m.x_placa_vehiculo, so.x_placa_vehiculo),
                    x_chasis_vehiculo = COALESCE(m.x_chasis_vehiculo, so.x_chasis_vehiculo),
                    x_motor_vehiculo = COALESCE(m.x_motor_vehiculo, so.x_motor_vehiculo),
                    x_vin = COALESCE(m.x_vin, so.x_vin),
                    x_nota_vehiculo = COALESCE(m.x_nota_vehiculo, so.x_nota_vehiculo),
                    x_klms_vehiculo = COALESCE(m.x_klms_vehiculo, so.x_klms_vehiculo),
                    x_millas_vehiculo = COALESCE(m.x_millas_vehiculo, so.x_millas_vehiculo)
                FROM (
                    SELECT DISTINCT ON (name) *
                    FROM sale_order
                    ORDER BY name, id DESC
                ) so
                WHERE (m.invoice_origin = so.name OR m.invoice_origin LIKE so.name || ',%')
                  AND (m.x_placa_vehiculo IS NULL AND m.mecanico_id IS NULL AND m.x_marca_vehiculo IS NULL);
            """)

        # 3. Sincronización del indicador de Taller vs MasterShop
        self.env.cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'account_move' AND column_name = 'es_taller';
        """)
        if self.env.cr.fetchone():
            self.env.cr.execute("""
                UPDATE account_move m
                SET es_taller = (
                    -- 1. Si tiene placa de vehículo registrada (excluyendo NA/NT/SINPLACA)
                    (
                        m.x_placa_vehiculo IS NOT NULL 
                        AND TRIM(m.x_placa_vehiculo) != ''
                        AND UPPER(REGEXP_REPLACE(TRIM(m.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) NOT IN ('NT', 'NA', 'SINPLACA')
                        AND LENGTH(REGEXP_REPLACE(TRIM(m.x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) >= 2
                    )
                    -- 2. O tiene mecánico asignado
                    OR (m.mecanico_id IS NOT NULL OR (m.x_detalle_mecanico IS NOT NULL AND TRIM(m.x_detalle_mecanico) != ''))
                    -- 3. O tiene servicios de taller (Servicios MOD o código MOD) y NO es venta exclusiva de MasterShop
                    OR (
                        EXISTS (
                            SELECT 1 FROM account_move_line aml 
                            LEFT JOIN product_product pp ON pp.id = aml.product_id 
                            LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id 
                            LEFT JOIN product_category pc ON pc.id = pt.categ_id 
                            WHERE aml.move_id = m.id AND aml.display_type = 'product' 
                              AND (
                                  pc.name ILIKE '%Servicios MOD%' 
                                  OR pt.default_code ILIKE 'MOD%' 
                                  OR aml.name ILIKE '%[MOD%'
                              )
                        )
                        AND NOT EXISTS (
                            SELECT 1 FROM account_move_line aml 
                            LEFT JOIN product_product pp ON pp.id = aml.product_id 
                            LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id 
                            LEFT JOIN product_category pc ON pc.id = pt.categ_id 
                            WHERE aml.move_id = m.id AND aml.display_type = 'product' 
                              AND (
                                  aml.name ILIKE '%MASTERSHOP%' 
                                  OR aml.name ILIKE '%Herramientas Master Shop%'
                                  OR pc.name ILIKE '%Herramienta%'
                              )
                        )
                    )
                );
            """)

        # 4. Sincronizar placas normalizadas en base de datos
        self.env.cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'account_move' AND column_name = 'clean_placa_vehiculo';
        """)
        if self.env.cr.fetchone():
            self.env.cr.execute("""
                UPDATE account_move
                SET clean_placa_vehiculo = UPPER(REGEXP_REPLACE(TRIM(x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g'))
                WHERE x_placa_vehiculo IS NOT NULL 
                  AND TRIM(x_placa_vehiculo) != ''
                  AND UPPER(REGEXP_REPLACE(TRIM(x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) NOT IN ('NT', 'NA', 'SINPLACA')
                  AND LENGTH(REGEXP_REPLACE(TRIM(x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) >= 2;
            """)

        # 5. Asegurar columnas de mano de obra
        self.env.cr.execute("""
            ALTER TABLE product_template ADD COLUMN IF NOT EXISTS es_mano_de_obra boolean DEFAULT false;
            ALTER TABLE product_product ADD COLUMN IF NOT EXISTS es_mano_de_obra boolean DEFAULT false;
            ALTER TABLE account_move_line ADD COLUMN IF NOT EXISTS es_mano_de_obra boolean DEFAULT false;
        """)

        # 6. Sincronizar catálogo de productos de mano de obra
        # NOTA: Solo servicios mecánicos reales (Servicios MOD o código MOD), excluyendo envíos externos y herramientas
        self.env.cr.execute("""
            UPDATE product_template pt
            SET es_mano_de_obra = false;

            UPDATE product_template pt
            SET es_mano_de_obra = true
            FROM product_category pc
            WHERE pt.categ_id = pc.id
              AND (
                  pc.name::text ILIKE '%Servicios MOD%'
                  OR pt.default_code ILIKE 'MOD%'
                  OR pt.default_code ILIKE 'SER%'
              )
              AND pc.name::text NOT ILIKE '%Externos%'
              AND pc.name::text NOT ILIKE '%Herramienta%'
              AND pt.name::text NOT ILIKE '%envio%'
              AND pt.name::text NOT ILIKE '%flete%';

            UPDATE product_template pt
            SET es_mano_de_obra = true
            WHERE pt.categ_id = 1
              AND (
                  pt.name::text ILIKE '%alinea%'
                  OR pt.name::text ILIKE '%balanceo%'
                  OR pt.name::text ILIKE '%rectific%'
                  OR pt.name::text ILIKE '%lavado%'
                  OR pt.name::text ILIKE '%calibrad%'
                  OR pt.name::text ILIKE '%mano de obra%'
                  OR pt.name::text ILIKE '%diagnostico%'
              )
              AND pt.name::text NOT ILIKE '%pesas%'
              AND pt.name::text NOT ILIKE '%filtro%'
              AND pt.name::text NOT ILIKE '%bomba%'
              AND pt.name::text NOT ILIKE '%herramienta%'
              AND pt.name::text NOT ILIKE '%mastershop%';

            UPDATE product_product pp
            SET es_mano_de_obra = pt.es_mano_de_obra
            FROM product_template pt
            WHERE pp.product_tmpl_id = pt.id;

            UPDATE account_move_line aml
            SET es_mano_de_obra = pt.es_mano_de_obra
            FROM product_product pp
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE aml.product_id = pp.id;

            -- 6.5 Sincronizar líneas bajo secciones de Mano de Obra en account_move_line
            WITH ranked_aml AS (
                SELECT 
                    aml.id,
                    MAX(CASE WHEN aml.display_type = 'line_section' THEN aml.name ELSE NULL END) OVER (
                        PARTITION BY aml.move_id 
                        ORDER BY aml.sequence, aml.id 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) as current_section
                FROM account_move_line aml
            )
            UPDATE account_move_line
            SET es_mano_de_obra = true
            WHERE id IN (
                SELECT id FROM ranked_aml
                WHERE (
                    current_section ILIKE '%mano%obra%' 
                    OR current_section ILIKE '%manos%obra%'
                    OR current_section ILIKE '%manon%obra%'
                    OR current_section ILIKE '%manoo%obra%'
                    OR current_section ILIKE '%m/o%'
                    OR current_section ILIKE '%m.o.%'
                    OR current_section ILIKE '%servicio%mantenimiento%'
                    OR current_section ILIKE '%trabajo%mecanico%'
                )
                AND current_section NOT ILIKE '%repuesto%'
            )
            AND es_mano_de_obra IS NOT TRUE;

            -- 7. Sincronizar montos de mano de obra y repuestos en account_move
            ALTER TABLE account_move ADD COLUMN IF NOT EXISTS taller_monto_mano_obra numeric DEFAULT 0.0;
            ALTER TABLE account_move ADD COLUMN IF NOT EXISTS taller_monto_repuestos numeric DEFAULT 0.0;

            UPDATE account_move am
            SET 
                taller_monto_mano_obra = COALESCE(sub.mo, 0.0) * (CASE WHEN am.move_type = 'out_refund' THEN -1 ELSE 1 END),
                taller_monto_repuestos = COALESCE(sub.rep, 0.0) * (CASE WHEN am.move_type = 'out_refund' THEN -1 ELSE 1 END)
            FROM (
                SELECT 
                    aml.move_id,
                    SUM(CASE WHEN aml.es_mano_de_obra = True THEN aml.price_subtotal ELSE 0 END) AS mo,
                    SUM(CASE WHEN aml.es_mano_de_obra IS NOT TRUE THEN aml.price_subtotal ELSE 0 END) AS rep
                FROM account_move_line aml
                WHERE aml.display_type = 'product'
                GROUP BY aml.move_id
            ) sub
            WHERE am.id = sub.move_id;
        """)



class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    es_mano_de_obra = fields.Boolean(
        string='Es Mano de Obra',
        compute='_compute_es_mano_de_obra',
        store=True,
        readonly=False,
        index=True,
        help='Indica si esta línea corresponde a mano de obra / servicio del taller automotriz. Puede marcarse o desmarcarse libremente.'
    )

    @api.depends('product_id', 'product_id.es_mano_de_obra', 'product_id.type', 'product_id.categ_id', 'product_id.default_code', 'name')
    def _compute_es_mano_de_obra(self):
        for line in self:
            if line.display_type and line.display_type != 'product':
                line.es_mano_de_obra = False
                continue

            line_name = (line.name or '').strip().lower()
            if 'mastershop' in line_name or 'herramienta' in line_name or 'envio' in line_name or 'flete' in line_name:
                line.es_mano_de_obra = False
                continue

            if line.product_id:
                if line.product_id.es_mano_de_obra:
                    line.es_mano_de_obra = True
                    continue
                categ = (line.product_id.categ_id.name or '').lower()
                if any(c in categ for c in ['externo', 'repuesto', 'filtro', 'freno', 'lubricante', 'aditivo', 'herramienta', 'accesorio', 'motor', 'carrocería', 'faja', 'herraje']):
                    line.es_mano_de_obra = False
                    continue
                code = (line.product_id.default_code or '').upper()
                if 'servicios mod' in categ or code.startswith('MOD') or (code.startswith('SER') and 'externo' not in categ) or line.product_id.type == 'service':
                    line.es_mano_de_obra = True
                    continue
                line.es_mano_de_obra = False
            else:
                if any(line_name.startswith(w) for w in [
                    'cambi', 'desmont', 'instal', 'repar', 'manten', 'servic',
                    'alinea', 'balanc', 'lavad', 'limpie', 'calibr', 'diagno',
                    'revis', 'rectif', 'purga', 'engras', 'mano de obra', 'soldadur', 'torno', 'bajad'
                ]) or '[mod' in line_name:
                    if any(w in line_name for w in ['kit de repuesto', 'filtro de', 'juego de empaque', 'bomba de', 'herramienta']):
                        line.es_mano_de_obra = False
                    else:
                        line.es_mano_de_obra = True
                else:
                    line.es_mano_de_obra = False

    @api.onchange('product_id')
    def _onchange_product_id_check_section_mano_de_obra(self):
        if self.display_type and self.display_type != 'product':
            return
        if self.move_id:
            cur_sec = False
            for line in self.move_id.invoice_line_ids:
                if line.display_type == 'line_section':
                    cur_sec = line.name or ''
                elif line == self or line.id == self.id or (self._origin.id and line._origin.id == self._origin.id):
                    break
            if cur_sec and is_mano_de_obra_section(cur_sec):
                self.es_mano_de_obra = True

    @api.onchange('name')
    def _onchange_name_check_section_mano_de_obra(self):
        if (self.display_type and self.display_type != 'product') or self.product_id or self._origin.id:
            return
        if self.move_id:
            cur_sec = False
            for line in self.move_id.invoice_line_ids:
                if line.display_type == 'line_section':
                    cur_sec = line.name or ''
                elif line == self or line.id == self.id:
                    break
            if cur_sec and is_mano_de_obra_section(cur_sec):
                self.es_mano_de_obra = True



