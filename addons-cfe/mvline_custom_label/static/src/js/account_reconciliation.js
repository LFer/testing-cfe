odoo.define('mvline_custom_label.account_reconciliation', function (require) {
'use strict';

    var core = require('web.core');
    var ajax = require('web.ajax');
    var qweb = core.qweb;
    ajax.loadXML('/mvline_custom_label/static/src/xml/account_reconciliation.xml', qweb);

});