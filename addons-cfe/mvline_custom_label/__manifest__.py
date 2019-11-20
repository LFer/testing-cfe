# -*- coding: utf-8 -*-
{
    'name': "Custom Move Line Label",
    'summary': """
        Custom Move Line Label in Reconciliation View""",
    'description': """
        This Module:
        - Put Serie-Numero as move line label in Reconciliation View instead of default label from invoice. 
    """,
    'author': "MuranMed",
    'website': "https://www.fiverr.com/muranmed",
    'category': 'Accounting',
    'version': '1.0',
    'depends': ['base', 'account'],
    'qweb': [
        'static/src/xml/account_reconciliation.xml',
        'views/assets.xml',
    ],
    'data': [
        'views/assets.xml',
    ],
}