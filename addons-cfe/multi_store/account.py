# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    store_id = fields.Many2one(
        'res.store', 'Store',
        help='The store this user is currently working for.')
    store_ids = fields.Many2many(
        'res.store', 'res_store_journal_rel', 'journal_id', 'store_id',
        'Store', help="""Users that are not of this store, can see this\
        journals records but can not post or modify any entry on them.""")

