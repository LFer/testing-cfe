# -*- coding: utf-8 -*-
from odoo import models, fields, api
import ipdb

class ResPartner(models.Model):
    _inherit = "res.partner"

    vat_type = fields.Selection([('2', 'RUT'),
                                 ('3', 'Cédula de identidad'),
                                 ('4', 'Otros'),
                                 ('5', 'Pasaporte'),
                                 ('6', 'DNI'),
                                 ('7', 'NIFE')],
                                string='Tipo de documento',
                                default='2')



    country_id = fields.Many2one(comodel_name='res.country', required=True)
    street = fields.Char(required=True)
    city = fields.Char(required=True)
    state_id = fields.Many2one(comodel_name='res.country.state', required=True)