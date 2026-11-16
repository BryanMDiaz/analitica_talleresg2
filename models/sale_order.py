import re
import unicodedata
from odoo import models, fields, api


def is_mano_de_obra_section(text):
    """
    Detecta si el título de una sección corresponde a Mano de Obra.
    Tolera variaciones y faltas tipográficas comunes:
    - 'MANO DE OBRA', 'MANOS DE OBRA', 'MANO DE OBRAS', 'MANOS DE OBRAS'
    - 'MANON DE OBRA', 'Manoo de Obra', 'MANO OBRA', 'MANOS OBRAS'
    - 'M/O', 'M.O.', 'Mano de Obra Preventivo / Correctivo', etc.
    """
    if not text:
        return False
    t = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8').lower()
    t = re.sub(r'[^a-z0-9\s/.]', ' ', t).strip()
    
    # Si la sección es de repuestos, lubricantes, etc. y no menciona obra, no es mano de obra
    if any(k in t for k in ['repuesto', 'consumible', 'insumo', 'material', 'herramienta', 'filtro', 'lubricante', 'accesorio']):
        if not ('obra' in t or 'mano' in t):
            return False
            
    # Variaciones de mano de obra
    if re.search(r'\bmano[ons]?\b.*?\bobras?\b', t):
        return True
    if re.search(r'\bobras?\b.*?\bmano[ons]?\b', t):
        return True
    if 'mano de obra' in t or 'manos de obra' in t or 'mano obra' in t or 'manos obras' in t:
        return True
        
    # Abreviaturas comunes
    if re.search(r'(^|\s)(m/o|m\.o\.)(\s|$)', t):
        return True
        
    # Servicios técnicos
    if any(s in t for s in ['servicio de mantenimiento', 'servicios de mantenimiento', 'trabajos de taller', 'servicios de taller', 'trabajos mecanicos', 'mantenimiento preventivo y correctivo']):
        return True

    return False


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mecanico_id = fields.Many2one(
        'hr.employee',
        string='Mecánico',
        tracking=True,
        help='Mecánico asignado desde la lista de empleados'
    )
    clean_placa_vehiculo = fields.Char(
        string='Placa Normalizada',
        compute='_compute_clean_placa_vehiculo',
        store=True,
        index=True,
        help='Placa unificada en mayúsculas y sin caracteres especiales para consolidar historial analítico.'
    )
    es_taller = fields.Boolean(
        string='Es Orden de Taller',
        compute='_compute_es_taller',
        store=True,
        index=True,
        help='Indica si la orden o cotización corresponde al Taller Automotriz.'
    )

    @api.depends('x_placa_vehiculo')
    def _compute_clean_placa_vehiculo(self):
        for rec in self:
            if rec.x_placa_vehiculo:
                clean = re.sub(r'[^A-Za-z0-9]', '', rec.x_placa_vehiculo).upper()
                rec.clean_placa_vehiculo = clean if clean not in ('NT', 'NA', 'SINPLACA') and len(clean) >= 2 else False
            else:
                rec.clean_placa_vehiculo = False

    @api.depends('x_placa_vehiculo', 'partner_id', 'partner_id.category_id', 'order_line', 'order_line.product_id')
    def _compute_es_taller(self):
        for order in self:
            if order.x_placa_vehiculo and order.x_placa_vehiculo.strip():
                order.es_taller = True
                continue
            partner_tags = order.partner_id.category_id.mapped('name') if order.partner_id else []
            if any('talleres' in (tag or '').lower() for tag in partner_tags):
                order.es_taller = True
                continue
            is_workshop = False
            for line in order.order_line:
                if line.display_type:
                    continue
                categ_name = (line.product_id.categ_id.name or '').lower()
                prod_code = (line.product_id.default_code or '').upper()
                line_name = (line.name or '').lower()
                if (
                    'servicio' in categ_name or
                    prod_code.startswith('MOD') or
                    any(k in categ_name for k in ['repuesto', 'freno', 'motor', 'llanta', 'direccion', 'embrague', 'filtro', 'lubricante', 'amortiguador']) or
                    any(line_name.startswith(k) for k in ['cambi', 'desmont', 'instal', 'repar', 'manten', 'servic', 'alinea', 'balanc', 'lavad', 'limpie', 'calibr', 'diagno', 'revis', 'rectif', 'mano de obra'])
                ):
                    is_workshop = True
                    break
            order.es_taller = is_workshop

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            # Ocultamos la pestaña original de Studio dinámicamente sin tocar la base de datos
            for node in arch.xpath("//page[@name='studio_page_1h5_1j48b5qul']"):
                node.set('invisible', 'True')
            for node in arch.xpath("//page[@string='Informacion Vehiculo' and @name!='page_informacion_vehiculo_analitica']"):
                node.set('invisible', 'True')
        return arch, view

    @api.onchange('mecanico_id')
    def _onchange_mecanico_id(self):
        if self.mecanico_id and 'x_detalle_mecanico' in self._fields:
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
                # Kilómetros y Millas siempre quedan vacíos para la nueva orden
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
            'order_id': self.id,
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('mecanico_id') and 'x_detalle_mecanico' in self.fields_get():
                employee = self.env['hr.employee'].browse(vals['mecanico_id'])
                if employee.exists():
                    vals['x_detalle_mecanico'] = employee.name
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('mecanico_id') and 'x_detalle_mecanico' in self.fields_get():
            employee = self.env['hr.employee'].browse(vals['mecanico_id'])
            if employee.exists():
                vals['x_detalle_mecanico'] = employee.name
        elif 'mecanico_id' in vals and not vals['mecanico_id'] and 'x_detalle_mecanico' in self.fields_get():
            vals['x_detalle_mecanico'] = False
        return super().write(vals)

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        fields_to_copy = [
            'mecanico_id', 'x_detalle_mecanico', 'x_marca_vehiculo',
            'x_modelo_vehiculo', 'x_ano_vehiculo', 'x_tipo_vehiculo',
            'x_placa_vehiculo', 'clean_placa_vehiculo', 'x_chasis_vehiculo', 'x_motor_vehiculo',
            'x_vin', 'x_nota_vehiculo', 'x_klms_vehiculo', 'x_millas_vehiculo'
        ]
        for field in fields_to_copy:
            if field in self._fields:
                val = getattr(self, field)
                if field == 'mecanico_id':
                    invoice_vals[field] = val.id if val else False
                else:
                    invoice_vals[field] = val
        return invoice_vals

    def init(self):
        """
        Sincroniza automáticamente los registros existentes que tengan
        texto en x_detalle_mecanico con su correspondiente empleado en hr.employee.
        """
        super().init()
        self.env.cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sale_order' AND column_name = 'x_detalle_mecanico';
        """)
        if self.env.cr.fetchone():
            self.env.cr.execute("""
                UPDATE sale_order s
                SET mecanico_id = e.id
                FROM hr_employee e
                WHERE s.mecanico_id IS NULL
                  AND s.x_detalle_mecanico IS NOT NULL
                  AND TRIM(s.x_detalle_mecanico) != ''
                  AND LOWER(TRIM(s.x_detalle_mecanico)) = LOWER(TRIM(e.name));
            """)

        self.env.cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sale_order' AND column_name = 'es_taller';
        """)
        if self.env.cr.fetchone():
            self.env.cr.execute("""
                UPDATE sale_order s
                SET es_taller = (
                    (s.x_placa_vehiculo IS NOT NULL AND TRIM(s.x_placa_vehiculo) != '')
                    OR EXISTS (
                        SELECT 1 FROM res_partner_res_partner_category_rel rel
                        JOIN res_partner_category cat ON cat.id = rel.category_id
                        WHERE rel.partner_id = s.partner_id AND cat.name::text ILIKE '%Talleres / Cliente%'
                    )
                    OR EXISTS (
                        SELECT 1 FROM sale_order_line sol 
                        LEFT JOIN product_product pp ON pp.id = sol.product_id 
                        LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id 
                        LEFT JOIN product_category pc ON pc.id = pt.categ_id 
                        WHERE sol.order_id = s.id AND (sol.display_type IS NULL OR sol.display_type = '') 
                          AND (
                              pc.name ILIKE '%Servicio%' 
                              OR pt.default_code ILIKE '%MOD%' 
                              OR sol.name ~* '^(cambi|desmont|instal|repar|manten|servic|alinea|balanc|lavad|limpie|calibr|diagno|revis|rectif|purga|engras|mano de obra|[0-9]+\.\s*(cambi|desmont|instal|repar|manten|servic|alinea|balanc|lavad|limpie|calibr|diagno|revis|rectif|purga|engras))'
                              OR pc.name ILIKE '%Repuesto%'
                              OR pc.name ILIKE '%Freno%'
                              OR pc.name ILIKE '%Motor%'
                              OR pc.name ILIKE '%Llantas%'
                              OR pc.name ILIKE '%Direccion%'
                              OR pc.name ILIKE '%Embrague%'
                              OR pc.name ILIKE '%Filtro%'
                              OR pc.name ILIKE '%Lubricante%'
                          )
                    )
                );
            """)

        # Sincronizar placas normalizadas en base de datos
        self.env.cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sale_order' AND column_name = 'clean_placa_vehiculo';
        """)
        if self.env.cr.fetchone():
            self.env.cr.execute("""
                UPDATE sale_order
                SET clean_placa_vehiculo = UPPER(REGEXP_REPLACE(TRIM(x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g'))
                WHERE x_placa_vehiculo IS NOT NULL 
                  AND TRIM(x_placa_vehiculo) != ''
                  AND UPPER(REGEXP_REPLACE(TRIM(x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) NOT IN ('NT', 'NA', 'SINPLACA')
                  AND LENGTH(REGEXP_REPLACE(TRIM(x_placa_vehiculo), '[^A-Za-z0-9]', '', 'g')) >= 2;
            """)

        # Asegurar columna en sale_order_line
        self.env.cr.execute("""
            ALTER TABLE sale_order_line ADD COLUMN IF NOT EXISTS es_mano_de_obra boolean DEFAULT false;
        """)
        # Sincronizar sale_order_line existentes con productos marcados
        self.env.cr.execute("""
            UPDATE sale_order_line sol
            SET es_mano_de_obra = true
            FROM product_product pp
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE sol.product_id = pp.id AND pt.es_mano_de_obra = true;
        """)
        # Sincronizar líneas bajo secciones de Mano de Obra en sale_order_line
        self.env.cr.execute("""
            WITH ranked_sol AS (
                SELECT 
                    sol.id,
                    MAX(CASE WHEN sol.display_type = 'line_section' THEN sol.name ELSE NULL END) OVER (
                        PARTITION BY sol.order_id 
                        ORDER BY sol.sequence, sol.id 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) as current_section
                FROM sale_order_line sol
            )
            UPDATE sale_order_line
            SET es_mano_de_obra = true
            WHERE id IN (
                SELECT id FROM ranked_sol
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
        """)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

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
            if line.display_type:
                line.es_mano_de_obra = False
                continue
            if line.product_id:
                if line.product_id.es_mano_de_obra:
                    line.es_mano_de_obra = True
                    continue
                categ = (line.product_id.categ_id.name or '').lower()
                if any(c in categ for c in ['repuesto', 'filtro', 'freno', 'lubricante', 'aditivo', 'herramienta', 'accesorio', 'motor', 'carrocería', 'faja', 'herraje']):
                    line.es_mano_de_obra = False
                    continue
                code = (line.product_id.default_code or '').upper()
                if 'servicio' in categ or code.startswith('MOD') or code.startswith('SER') or line.product_id.type == 'service':
                    line.es_mano_de_obra = True
                    continue
                line.es_mano_de_obra = False
            else:
                text = (line.name or '').strip().lower()
                if any(text.startswith(w) for w in [
                    'cambi', 'desmont', 'instal', 'repar', 'manten', 'servic',
                    'alinea', 'balanc', 'lavad', 'limpie', 'calibr', 'diagno',
                    'revis', 'rectif', 'purga', 'engras', 'mano de obra', 'soldadur', 'torno', 'bajad'
                ]) or '[mod' in text:
                    if any(w in text for w in ['kit de repuesto', 'filtro de', 'juego de empaque', 'bomba de']):
                        line.es_mano_de_obra = False
                    else:
                        line.es_mano_de_obra = True
                else:
                    line.es_mano_de_obra = False

    @api.onchange('product_id', 'product_template_id')
    def _onchange_product_id_check_section_mano_de_obra(self):
        if self.display_type:
            return
        if self.order_id:
            cur_sec = False
            for line in self.order_id.order_line:
                if line.display_type == 'line_section':
                    cur_sec = line.name or ''
                elif line == self or line.id == self.id or (self._origin.id and line._origin.id == self._origin.id):
                    break
            if cur_sec and is_mano_de_obra_section(cur_sec):
                self.es_mano_de_obra = True

    @api.onchange('name')
    def _onchange_name_check_section_mano_de_obra(self):
        if self.display_type or self.product_id or self._origin.id:
            return
        if self.order_id:
            cur_sec = False
            for line in self.order_id.order_line:
                if line.display_type == 'line_section':
                    cur_sec = line.name or ''
                elif line == self or line.id == self.id:
                    break
            if cur_sec and is_mano_de_obra_section(cur_sec):
                self.es_mano_de_obra = True

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res['es_mano_de_obra'] = self.es_mano_de_obra
        return res


