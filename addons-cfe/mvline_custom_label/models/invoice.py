# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def invoice_validate(self):
        res = super(AccountInvoice, self).invoice_validate()
        for invoice in self:
            if invoice.x_Serie and invoice.x_DocNro:
                invoice.number = str(invoice.x_Serie) + '-' + str(invoice.x_DocNro)
                invoice.reference = invoice._get_computed_reference()
                invoice.move_name = invoice.number
                invoice.move_id.name = invoice.number
                invoice.move_id.ref = invoice.reference
        return res
    

