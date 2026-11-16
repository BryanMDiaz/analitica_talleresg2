# -*- coding: utf-8 -*-

import re
from odoo import models, fields, api


class TallerSeleccionarVehiculoWizard(models.TransientModel):
    _name = 'taller.seleccionar.vehiculo.wizard'
    _description = 'Asistente para Seleccionar Vehículo de Cliente'

    order_id = fields.Many2one('sale.order', string='Cotización / Pedido')
    move_id = fields.Many2one('account.move', string='Factura')
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    filtro_placa = fields.Char(string='Buscar por Placa', help='Filtre los vehículos por número de placa, marca o modelo')
    total_vehiculos = fields.Integer(string='Total de Vehículos', compute='_compute_total_vehiculos')
    line_ids = fields.One2many(
        'taller.seleccionar.vehiculo.wizard.line',
        'wizard_id',
        string='Vehículos Registrados'
    )

    @api.depends('line_ids')
    def _compute_total_vehiculos(self):
        for w in self:
            w.total_vehiculos = len(w.line_ids)

    def _filter_vehicles(self, vehicles, term):
        if not term:
            return vehicles
        search_term = term.strip().upper()
        clean_search = re.sub(r'[^A-Za-z0-9]', '', search_term)
        filtered = []
        for v in vehicles:
            p_raw = str(v.get('placa') or '').upper()
            p_clean = re.sub(r'[^A-Za-z0-9]', '', p_raw)
            m = str(v.get('marca') or '').upper()
            mod = str(v.get('modelo') or '').upper()
            vin = str(v.get('vin') or '').upper()
            chasis = str(v.get('chasis') or '').upper()
            if (
                clean_search in p_clean or
                search_term in p_raw or
                search_term in m or
                search_term in mod or
                clean_search in vin or
                clean_search in chasis
            ):
                filtered.append(v)
        return filtered

    def action_search_vehicles(self):
        """Filtra los vehículos del cliente según el término de búsqueda ingresado."""
        self.ensure_one()
        all_vehicles = self.partner_id.get_registered_vehicles() if self.partner_id else []
        filtered = self._filter_vehicles(all_vehicles, self.filtro_placa)
        self.line_ids.unlink()
        self.write({
            'line_ids': [(0, 0, v) for v in filtered]
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'taller.seleccionar.vehiculo.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_clear_filter(self):
        """Restaura la lista completa de vehículos del cliente."""
        self.ensure_one()
        self.filtro_placa = False
        all_vehicles = self.partner_id.get_registered_vehicles() if self.partner_id else []
        self.line_ids.unlink()
        self.write({
            'line_ids': [(0, 0, v) for v in all_vehicles]
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'taller.seleccionar.vehiculo.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.onchange('filtro_placa')
    def _onchange_filtro_placa(self):
        """Filtra en vivo las líneas cuando el usuario escribe en el campo de búsqueda."""
        if not self.partner_id:
            return
        all_vehicles = self.partner_id.get_registered_vehicles()
        filtered = self._filter_vehicles(all_vehicles, self.filtro_placa)
        self.line_ids = [(5, 0, 0)] + [(0, 0, v) for v in filtered]


class TallerSeleccionarVehiculoWizardLine(models.TransientModel):
    _name = 'taller.seleccionar.vehiculo.wizard.line'
    _description = 'Línea de Vehículo de Cliente'
    _order = 'placa asc'

    wizard_id = fields.Many2one(
        'taller.seleccionar.vehiculo.wizard',
        string='Asistente',
        ondelete='cascade',
        required=True
    )
    placa = fields.Char(string='Placa', required=True)
    marca = fields.Char(string='Marca')
    modelo = fields.Char(string='Modelo')
    ano = fields.Char(string='Año')
    tipo_vehiculo = fields.Char(string='Tipo')
    chasis = fields.Char(string='Chasis')
    motor = fields.Char(string='Motor')
    vin = fields.Char(string='VIN')
    nota = fields.Char(string='Nota')

    def action_select_vehicle(self):
        self.ensure_one()
        wizard = self.wizard_id
        vals = {
            'x_placa_vehiculo': self.placa,
            'x_marca_vehiculo': self.marca or False,
            'x_modelo_vehiculo': self.modelo or False,
            'x_ano_vehiculo': self.ano or False,
            'x_tipo_vehiculo': self.tipo_vehiculo or False,
            'x_chasis_vehiculo': self.chasis or False,
            'x_motor_vehiculo': self.motor or False,
            'x_vin': self.vin or False,
            'x_nota_vehiculo': self.nota or False,
            'x_klms_vehiculo': False,
            'x_millas_vehiculo': False,
        }
        if wizard.order_id:
            wizard.order_id.write(vals)
        elif wizard.move_id:
            wizard.move_id.write(vals)
        return {'type': 'ir.actions.act_window_close'}
