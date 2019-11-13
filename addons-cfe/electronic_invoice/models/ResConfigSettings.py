# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
import ipdb

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    key_produccion = fields.Char(string="WS Producción")
    key_testing = fields.Char(string="WS Testing")
    fe_activa = fields.Boolean(string="Desactivar Facturacion Electronica")
    local_mac = fields.Char(string="MAC Local")


    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(key_produccion=self.env['ir.config_parameter'].sudo().get_param('electronic_invoice.url_produccion'))
        res.update(key_testing=self.env['ir.config_parameter'].sudo().get_param('electronic_invoice.url_testing'))
        res.update(local_mac=self.env['ir.config_parameter'].sudo().get_param('electronic_invoice.local_mac'))
        if self.env['ir.config_parameter'].sudo().get_param('electronic_invoice.fe_activa') == 'True':
            res.update(fe_activa=True)
        else:
            res.update(fe_activa=False)
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('electronic_invoice.url_produccion', self.key_produccion)
        self.env['ir.config_parameter'].sudo().set_param('electronic_invoice.url_testing', self.key_testing)
        self.env['ir.config_parameter'].sudo().set_param('electronic_invoice.local_mac', self.local_mac)
        self.env['ir.config_parameter'].sudo().set_param('electronic_invoice.fe_activa', self.fe_activa)