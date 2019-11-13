# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResStore(models.Model):
    _inherit = 'res.store'

    nro_suc_dgi = fields.Char('Nro. Sucursal DGI', required=True)
    social_reason = fields.Char(string='Nombre Fantasía', store=True, related='company_id.partner_id.social_reason')
    phone = fields.Char(string='Teléfono')
    rut = fields.Char(string='RUT', store=True, related='company_id.vat')
    country_id = fields.Many2one(comodel_name='res.country', string='Pais')
    state_id = fields.Many2one(comodel_name='res.country.state', string='Departamento')
    city = fields.Char(string='Ciudad')
    street = fields.Char(string='Calle')


ResStore()

