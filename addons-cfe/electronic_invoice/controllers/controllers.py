# -*- coding: utf-8 -*-
from odoo import http

# class ElectronicInvoice(http.Controller):
#     @http.route('/electronic_invoice/electronic_invoice/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/electronic_invoice/electronic_invoice/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('electronic_invoice.listing', {
#             'root': '/electronic_invoice/electronic_invoice',
#             'objects': http.request.env['electronic_invoice.electronic_invoice'].search([]),
#         })

#     @http.route('/electronic_invoice/electronic_invoice/objects/<model("electronic_invoice.electronic_invoice"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('electronic_invoice.object', {
#             'object': obj
#         })