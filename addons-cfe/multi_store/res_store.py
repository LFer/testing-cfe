# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import models, fields, SUPERUSER_ID, api


class ResStore(models.Model):
    _name = "res.store"
    _description = 'Stores'
    _order = 'parent_id desc, name'

    name = fields.Char('Name', size=128, required=True,)
    parent_id = fields.Many2one('res.store', 'Parent Store', select=True)
    child_ids = fields.One2many('res.store', 'parent_id', 'Child Stores')
    journal_ids = fields.Many2many('account.journal', 'res_store_journal_rel', 'store_id', 'journal_id', 'Journals')
    company_id = fields.Many2one('res.company', 'Company', required=True,
                                  default=lambda self: self.env['res.company']._company_default_get('res.store'))
    user_ids = fields.Many2many(
        'res.users', 'res_store_users_rel', 'cid', 'user_id', 'Accepted Users')

    _sql_constraints = [('name_uniq', 'unique (name)', 'The company name must be unique !')]

    _constraints = [(models.BaseModel._check_recursion, 'Error! You can not create recursive stores.', ['parent_id'])]

    # @api.model
    # def name_search(self, name='', args=None, operator='ilike', limit=100):
    #     context = self._context.copy() or {}
    #     if context.pop('user_preference', None):
    #         # We browse as superuser. Otherwise, the user would be able to
    #         # select only the currently visible stores (according to rules,
    #         # which are probably to allow to see the child stores) even if
    #         # she belongs to some other stores.
    #         user = self.env['res.users'].browse(SUPERUSER_ID)
    #         store_ids = list(set([user.store_id.id] + [cmp.id for cmp in user.store_ids]))
    #         uid = SUPERUSER_ID
    #         args = (args or []) + [('id', 'in', store_ids)]
    #     return super(ResStore, self).name_search(name=name, args=args, operator=operator, limit=limit)