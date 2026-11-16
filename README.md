<div align="center">

<img src="static/description/icon.png" alt="Analítica Talleres G2" width="120" />

# 🔧 Analítica Talleres G2

### El pulso de tu taller, en un solo lugar.

**Ventas · Vehículos · Clientes · Costos · Rentabilidad**

![Odoo](https://img.shields.io/badge/Odoo-18.0-714B67?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OWL](https://img.shields.io/badge/Frontend-OWL-00A09D?style=for-the-badge)
![Licencia](https://img.shields.io/badge/Licencia-LGPL--3-blue?style=for-the-badge)

Módulo para **Odoo 18 Enterprise** que conecta la operación del taller con sus resultados: desde la cotización y el historial del vehículo hasta el seguimiento comercial y el análisis de ingresos y costos.

</div>

---

## ✨ Funcionalidades

| Área | Lo que aporta |
| --- | --- |
| 📊 **Tablero ejecutivo** | Selección de período, evolución mensual, comparación con el mes anterior y total anual. |
| 💵 **Ingresos** | Desglose de mano de obra, repuestos y servicios externos. |
| 🚗 **Bitácora por vehículo** | Historial por placa, datos del vehículo, último servicio, cotizaciones y facturas relacionadas. |
| 👥 **Clientes y mecánicos** | Consulta de clientes del taller y rankings en el tablero. |
| 🧾 **Ventas y facturación** | Datos del vehículo y del mecánico integrados en cotizaciones, pedidos y facturas. |
| 🔎 **Selección de vehículos** | Asistente para reutilizar vehículos del cliente y buscar por placa, marca, modelo, VIN o chasis. |
| 📈 **Rentabilidad** | Centros de costos vinculados a cuentas analíticas, importes estimados y reales, y margen operativo. |
| 🔐 **Accesos** | Grupos de usuario y administrador, con reglas por compañía para centros de costos y bitácora. |

### Semáforo de seguimiento

- 🟢 **Activos:** hasta 30 días desde el último servicio.
- 🟡 **En alerta:** más de 30 y hasta 90 días.
- 🔴 **En riesgo:** más de 90 días o sin fecha de último servicio.

Incluye una tarea programada diaria para actualizar las estadísticas de clientes.

## 🧩 Requisitos

- **Odoo 18 Enterprise**, con acceso a su directorio de addons personalizados.
- Módulos estándar: `base`, `mail`, `analytic`, `account`, `sale` y `hr`.
- Módulo personalizado **`contabilidad_velatek`**, disponible en el `addons_path`. Esta dependencia **no está incluida** en este repositorio.
- Permisos de administración para instalar el módulo y asignar grupos.

> **Configuración de Talleres G2:** parte de la lógica busca compañías cuyo nombre contiene `GRUPO 2`. Para usarlo en otra organización, revisa y adapta esos filtros en los modelos.

## 🚀 Instalación

### 1. Descargar el módulo

Desde tu directorio de addons personalizados:

```bash
 git clone https://github.com/BryanMDiaz/analitica_talleresg2.git analitica_talleresg2
```

Conserva el nombre de carpeta **`analitica_talleresg2`**, utilizado por las referencias de recursos. Incluye el directorio padre en el `addons_path` de Odoo y comprueba que `contabilidad_velatek` también esté disponible.

### 2. Instalar desde Odoo

1. Reinicia el servicio de Odoo para detectar el módulo.
2. Accede como administrador y activa el **modo desarrollador**.
3. En **Aplicaciones**, selecciona **Actualizar lista de aplicaciones**.
4. Busca **Analítica Talleres G2** y pulsa **Instalar**.
5. Asigna el grupo **Usuario** o **Administrador** del módulo a las personas correspondientes.

### Alternativa por terminal

Sustituye las rutas y la base de datos por las de tu instalación. Ejecuta el comando con el servicio habitual detenido y reinícialo al terminar:

```bash
odoo -c /ruta/odoo.conf -d nombre_base_datos -i analitica_talleresg2 --stop-after-init
```

Para actualizar una instalación existente:

```bash
odoo -c /ruta/odoo.conf -d nombre_base_datos -u analitica_talleresg2 --stop-after-init
```

## 🧭 Primeros pasos

1. Abre **Analítica Talleres G2** desde el menú de aplicaciones.
2. En **Cotizaciones y Ventas**, registra las operaciones con los datos del vehículo y el mecánico.
3. Utiliza el asistente para seleccionar vehículos ya registrados del cliente.
4. Consulta **Bitácora de Servicios** para revisar el historial por placa.
5. Explora **Clientes Talleres G2** y **Reportes de Ventas** para analizar la actividad.
6. En **Tablero de Control**, selecciona el período y revisa ingresos, rankings y seguimiento de vehículos.

El modelo `analitica.taller` permite asociar cuentas analíticas a centros de costos y recalcular ingresos, costos y margen mediante sus acciones. Sus estados son **Borrador → En Progreso → Finalizado**, con opción de cancelación.

## 🗂️ Estructura

```text
analitica_talleresg2/
├── __init__.py
├── __manifest__.py                  # Metadatos, dependencias y recursos
├── data/cron.xml                    # Actualización diaria de estadísticas
├── models/
│   ├── analitica_taller.py           # Centros de costos y márgenes
│   ├── taller_bitacora_vehiculo.py   # Historial e indicadores
│   ├── taller_seleccionar_vehiculo_wizard.py
│   ├── sale_order.py                # Ventas
│   ├── account_move.py              # Facturación
│   ├── res_partner.py               # Clientes y vehículos
│   └── product_template.py          # Clasificación de mano de obra
├── security/                        # Grupos, permisos y reglas
├── views/                           # Formularios, reportes, asistente y menús
└── static/
    ├── description/icon.png
    └── src/
        ├── dashboard/               # Componente OWL, XML y SCSS
        └── scss/                    # Estilos del módulo
```

## 🛠️ Tecnología y mantenimiento

Backend con **Python y el ORM de Odoo**, consultas y vistas SQL para la bitácora y los indicadores, y un tablero construido con **OWL**, XML y SCSS.

Para cambios de modelos, vistas o permisos, actualiza el módulo con `-u analitica_talleresg2`. Para cambios web, comprueba también la regeneración de assets y la caché del navegador.

La instalación y el funcionamiento deben comprobarse en una instancia de Odoo 18 con todas las dependencias. Este repositorio no incluye un entorno de Odoo ni una suite de pruebas automatizadas.

## 📄 Autoría y licencia

- **Autor declarado:** [Velatek](https://www.velatek.com).
- **Versión:** `18.0.1.0.0`.
- **Licencia declarada en el manifiesto:** `LGPL-3`.

---

<div align="center">

**🔧 Cada servicio cuenta. Cada dato ayuda a decidir.**

</div>
