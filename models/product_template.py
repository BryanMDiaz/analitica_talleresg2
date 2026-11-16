# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    es_mano_de_obra = fields.Boolean(
        string='Es Mano de Obra / Servicio',
        default=False,
        index=True,
        help='Marcar si este producto corresponde a mano de obra, trabajos técnicos o servicios de taller.'
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    es_mano_de_obra = fields.Boolean(
        related='product_tmpl_id.es_mano_de_obra',
        string='Es Mano de Obra / Servicio',
        store=True,
        readonly=False,
        index=True,
        help='Marcar si este producto corresponde a mano de obra, trabajos técnicos o servicios de taller.'
    )
