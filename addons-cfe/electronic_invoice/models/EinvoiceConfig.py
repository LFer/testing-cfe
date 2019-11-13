
# -*- coding: utf-8 -*-
from odoo import models, fields, api
# formas de pago
CONTADO, CREDITO = (1, 2)

class DgiCodes(models.Model):
    _name = 'dgi.codes'
    _description = 'DGI Codes'
    code = fields.Integer('Code', required=True)
    name = fields.Char('Name', size=100, required=True)
    amount = fields.Float('Amount', required=True)
    value = fields.Float('Value', required=True)


class AccountTaxDgiCodes(models.Model):
    _name = 'account.tax.dgi.codes'
    _description = 'Map Account Tax to DGI Codes'

    tax_id = fields.Many2one('account.tax', "Tax", required=True, store=True, help='Account Tax')
    dgi_code_id = fields.Many2one('dgi.codes', 'DGI Tax Code', store=True, required=True, help='DGI Tax Code')

    _sql_constraints = [
        ('account_tax_uniq', 'unique(tax_id,dgi_code_id)', 'Impuesto ya relacionado'),
    ]


class AccountTax(models.Model):
    _name = 'account.tax'
    _inherit = 'account.tax'

    dgi_code_ids = fields.One2many('account.tax.dgi.codes', 'tax_id', 'DGI codes for this tax')


class AccountPaymentTermDgiCodes(models.Model):
    _name = 'account.payment.term.dgi.codes'
    _description = 'Map Account Payment Term to DGI Codes'

    payment_id = fields.Many2one('account.payment.term', "Payment Term", required=True, store=True, help='Account Payment Term')
    dgi_payment_id = fields.Selection([(CONTADO, 'Contado'), (CREDITO, 'Crédito')], store=True, required=True, help='DGI Payment Code')


class AccountPaymentTerm(models.Model):
    _name = 'account.payment.term'
    _inherit = 'account.payment.term'

    dgi_payment_ids = fields.One2many('account.payment.term.dgi.codes', 'payment_id', 'DGI payment codes for this account')