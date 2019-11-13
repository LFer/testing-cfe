# -*- coding: utf-8 -*-
{
    'name': "Factura Electrónica",

    'summary': """
        Los comprobantes fiscales electrónicos emitidos por nuestro software presentan idéntica validez ante todos los organismos legales y tributarios que las tradicionales facturas impresas.
""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Proyecta",
    'website': "https://proyecta.odoo.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'web', 'multi_store','l10n_uy_base_vat'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/DgiCodes.xml',
        'views/ResPartnerView.xml',
        'views/AccountInvoiceView.xml',
        'views/ResConfigSettingsViews.xml',
        'views/ElectronicInvoiceMenu.xml',
        'views/ResStoreView.xml',
        'data/DgiCodes.xml',
        'data/ResCurrency.xml',

        # 'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}