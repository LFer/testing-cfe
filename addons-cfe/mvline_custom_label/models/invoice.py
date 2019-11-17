# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def invoice_validate(self):
        res = super(AccountInvoice, self).invoice_validate()
        for invoice in self:
            if invoice.fe_Serie and invoice.fe_DocNro:
                invoice.number = str(invoice.fe_Serie) + '-' + str(invoice.fe_DocNro)
                invoice.reference = invoice._get_computed_reference()
                invoice.move_name = invoice.number
                invoice.move_id.name = invoice.number
                invoice.move_id.ref = invoice.reference
        return res
    

