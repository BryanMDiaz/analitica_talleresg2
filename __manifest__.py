# -*- coding: utf-8 -*-
{
    'name': 'Analítica Talleres G2',
    'version': '18.0.1.0.0',
    'summary': 'Módulo de Analítica y Gestión de Costos para Talleres G2',
    'description': """
Módulo de Analítica para Talleres G2
====================================
Este módulo permite la gestión y el análisis detallado de operaciones, costos y rentabilidad en talleres:
- Registro y seguimiento de órdenes y centros de costos de talleres.
- Vinculación con cuentas analíticas de Odoo.
- Métricas de ingresos, egresos y cálculo automático de margen operativo.
- Información de vehículos y asignación de mecánicos (empleados) en presupuestos y ventas.
- Vistas modernas optimizadas para Odoo 18.
    """,
    'category': 'Operations',
    'author': 'Velatek',
    'website': 'https://www.velatek.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'analytic',
        'account',
        'sale',
        'hr',
        'contabilidad_velatek',
    ],
    'data': [
        'security/analitica_talleres_security.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/analitica_taller_views.xml',
        'views/sale_order_views.xml',
        'views/reportes_ventas_views.xml',
        'views/clientes_talleres_views.xml',
        'views/taller_bitacora_views.xml',
        'views/account_move_views.xml',
        'views/product_views.xml',
        'views/dashboard_views.xml',
        'views/taller_seleccionar_vehiculo_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'analitica_talleresg2/static/src/scss/analitica_taller.scss',
            'analitica_talleresg2/static/src/dashboard/dashboard.scss',
            'analitica_talleresg2/static/src/dashboard/dashboard.js',
            'analitica_talleresg2/static/src/dashboard/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
