# -*- coding: utf-8 -*-
from odoo import _, api, fields, models, tools
import logging
from odoo.exceptions import AccessError, ValidationError, UserError, Warning
import time
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import ipdb
import re
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
import base64
import psycopg2
import smtplib
from odoo.tools.safe_eval import safe_eval

# mapping invoice type to journal type
TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale_refund',
    'in_refund': 'purchase_refund',
    'out_debit': 'sale_debit',
    'in_debit': 'purchase_debit',
}

# mapping invoice type to refund type
TYPE2DEBIT = {
    'out_invoice': 'out_debit',        # Customer Invoice
    'in_invoice': 'in_debit',          # Supplier Invoice
    'out_debit': 'out_invoice',        # Customer Debit
    'in_debit': 'in_invoice',          # Supplier Debit
}
_logger = logging.getLogger(__name__)
_errores = {'AS': 'Firmado',
            'BS': 'No se firmo',
            'AE': 'Aceptado por DGI Pendiente de Receptor Electronico',
            'BE': 'Rechazado por DGI Pendiente de Receptor Electronico',
            'AA': 'Aceptado por DGI y por Receptor Electronico',
            'PA': 'Pendiente de DGI y Aceptado por Receptor',
            'PR': 'Pendiente de DGI y  Rechazado por Receptor',
            'RR': 'Rechazado por DGI y por Receptor',
            'RA': 'Rechazado por DGI',
            'AR': 'Rechazado por Receptor'}

# formas de pago
CONTADO, CREDITO = (1, 2)

# monedas
CODIGO_MONEDA_UY = 'UYU'
MONEDA_UI = 'UYI'



class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    fe_TipoCFE = fields.Integer(string='Tipo de CFE', readonly=True)
    fe_Serie = fields.Char(string='Serie', readonly=True, copy=False)
    fe_DocNro = fields.Integer(string=u'Número', readonly=True, copy=False)
    fe_FechaHoraFirma = fields.Char(string='Fecha/Hora de firma', readonly=True)
    fe_Hash = fields.Char(string='Firma', readonly=True)
    fe_Estado = fields.Char(string='Estado', readonly=True)
    fe_URLParaVerificarQR = fields.Char(string=u'Código QR', readonly=True)
    fe_URLParaVerificarTexto = fields.Char(string=u'Verificación', readonly=True)
    fe_CAEDNro = fields.Integer(string='CAE Desde', readonly=True)
    fe_CAEHNro = fields.Integer(string='CAE Hasta', readonly=True)
    fe_CAENA = fields.Char(string=u'CAE Autorización', readonly=True)
    fe_CAEFA = fields.Char(string=u'CAE Fecha de autorización', readonly=True)
    fe_CAEFVD = fields.Char(string='CAE vencimiento', readonly=True)
    fe_Contingencia = fields.Boolean('Es Contingencia', default=False)
    fe_SerieContingencia = fields.Char(string='Serie', size=3)
    fe_DocNroContingencia = fields.Integer(string=u'Número')
    qr_img = fields.Binary('Imagen QR', copy=False)
    qr_imgx2 = fields.Binary('Imagen QR al doble de tamaño', copy=False)
    is_debit_note = fields.Boolean(string='Debit Note', default=False)
    nro_compra = fields.Char(string=u'Nro. de compra')
    for_export = fields.Boolean(string='For export', default=False)
    fe_activa = fields.Boolean(compute='get_cfe_status', help='Le muestra el status de la conexión de facturación electrónica')

    # tipos documentos de facturación electrónica
    EFACTURA, NC_EFACTURA, ND_EFACTURA, EFACTURA_EXP, NC_EFACTURA_EXP, ND_EFACTURA_EXP, ETICKET, NC_ETICKET, ND_ETICKET = (111, 112, 113, 121, 122, 123, 101, 102, 103)
    ERESGUARDO = 182

    DOC_RUT, DOC_CI, DOC_OTROS, DOC_PASAPORTE, DOC_DNI, DOC_NIFE = ('2', '3', '4', '5', '6', '7')

    @api.multi
    def action_invoice_draft(self):
        if self.filtered(lambda inv: inv.state != 'cancel'):
            raise UserError(_("Invoice must be cancelled in order to reset it to draft."))
        # go from canceled state to draft state
        self.write({'state': 'draft', 'date': False})
        # Delete former printed invoice
        try:
            report_invoice = self.env['ir.actions.report']._get_report_from_name('account.report_invoice')
        except IndexError:
            report_invoice = False
        return True

    @api.multi
    def _get_report_base_filename(self):
        self.ensure_one()
        return self.type == 'out_invoice' and self.state == 'draft' and _('Draft Invoice') or \
               self.type == 'out_invoice' and self.state in ('open','in_payment','paid') and _('Invoice - %s - %s') % (self.fe_Serie, self.fe_DocNro) or \
               self.type == 'out_refund' and self.state == 'draft' and _('Credit Note') or \
               self.type == 'out_refund'  and _('Credit Note - %s - %s') % (self.fe_Serie, self.fe_DocNro) or \
               self.type == 'in_invoice' and self.state == 'draft' and _('Vendor Bill') or \
               self.type == 'in_invoice' and self.state in ('open','in_payment','paid') and _('Vendor Bill - %s') % (self.number) or \
               self.type == 'in_refund' and self.state == 'draft' and _('Vendor Credit Note') or \
               self.type == 'in_refund' and _('Vendor Credit Note - %s') % (self.number)


    def filter_special_chars(self, text):
        # stripped = lambda s: "".join(i for i in s if 31 < ord(i) < 127)
        # text = unicodedata.normalize("NFKD", text)  # D is for d-ecomposed
        # clean_text = text.encode("ascii", "ignore")
        # clean_text = u"".join([ch for ch in text if not unicodedata.combining(ch)])
        # return stripped(clean_text)
        valid_chars = u' 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%()=?¿¡\'()*+/-+:;=@[\]^_`{|}ÇçüáéíóúÁÉÍÓÚñÑàèìùò'
        return ''.join(c for c in text if c in valid_chars)

    @staticmethod
    def get_serie_nro(invoice_number):
        """
        Obtiene Serie y número de la secuencia interna. En caso de
        cambiar la secuencia interna, heredar y sobreescribir.

        La secuencia por defecto es VEN/%(year)s/####, de allí tomamos
        como serie VE y el número del final.
        :param invoice_number:
        """
        return invoice_number[0:1], int(invoice_number.split('-')[1])

    @api.multi
    def action_number_cfe(self):
        """
        Escribimos el numero de factura y asiento segun lo que nos devuelva el webservice
        Si la cfe es
        :return:
        """
        self.write({})
        for inv in self:
            if inv.fe_Serie and inv.fe_DocNro:
                number = str(self.fe_Serie + ' ' + str(self.fe_DocNro))
            else:
                number = inv.number
            self.write({'internal_number': number})

            if inv.type in ('in_invoice', 'in_refund'):
                if not inv.reference:
                    ref = number
                else:
                    ref = inv.reference
            else:
                ref = number
            self._cr.execute(""" UPDATE account_move SET ref=%s WHERE id=%s AND (ref IS NULL OR ref = '')""", (ref, inv.move_id.id))
            self._cr.execute (""" UPDATE account_move SET name=%s WHERE id=%s """, (ref, inv.move_id.id))
            self._cr.execute(""" UPDATE account_move_line SET ref=%s WHERE move_id=%s AND (ref IS NULL OR ref = '')""",(ref, inv.move_id.id))
            self._cr.execute(""" UPDATE account_analytic_line SET ref=%s FROM account_move_line WHERE account_move_line.move_id = %s AND account_analytic_line.move_id = account_move_line.id""", (ref, inv.move_id.id))
            self._cr.execute ("""UPDATE account_invoice SET number=%s WHERE id=%s """,(number, inv.id))
            self.invalidate_cache()
        return True

    @api.multi
    def get_cfe_status(self):
        _logger.error(self.es_produccion ())
        SysParam = self.env['ir.config_parameter']
        self.fe_activa = False
        for recs in self:
            if recs.es_produccion():
                recs.fe_activa = True
                return {
                    'type': 'ir.actions.client',
                    'tag': 'action_warn',
                    'name': 'Notificación',
                    'params': {
                        'title': 'CFE',
                        'text': '¡La facturación Electrónica está activa!',
                        'sticky': True
                    }
                }
            elif SysParam.get_param('fe_inactiva'):
                recs.fe_activa = False
                return {
                    'type': 'ir.actions.client',
                    'tag': 'action_warn',
                    'name': 'Notificación',
                    'params': {
                        'title': 'CFE',
                        'text': '¡La facturación Electrónica está desactivada '
                                'Verifique que no exista la clave fe_inactiva en parametros del sistema o contactese con el servicio tecnico!',
                        'sticky': True
                    }
                }
            else:
                recs.fe_activa = False
                return {
                    'type': 'ir.actions.client',
                    'tag': 'action_warn',
                    'name': 'Notificación',
                    'params': {
                        'title': 'CFE',
                        'text': '¡La facturación Electrónica está desactivada '
                                'Verifique que no exista la clave fe_inactiva en parametros del sistema o contactese con el servicio tecnico!',
                        'sticky': True
                    }
                }

    def genera_cabezal(self, tipo_cfe):
        """
        Genera el cabezal de una e-factura
        :param tipo_cfe: tipo de documento DGI
        :return: string de cabezal de la e-factura
        """
        pass

    def genera_lineas(self):
        """
        Genera las líneas de una e-factura
        :return: string de líneas de la e-factura
        """
        pass

    def genera_descuentos_globales(self):
        """
        Genera el bloque de descuentos globales del documento electrónico
        :return: string del bloque de descuentos globales del documento electrónico
        """
        pass

    def genera_nodo_referencia(self, tipo_cfe):
        pass

    def genera_nodo_adicional(self, tipo_cfe):
        pass

    def genera_resguardo(self):
        pass

    def hay_error(self):
        """Retorna True si ocurrió algún error en la firma del documento,
        False si esta todo ok
        """
        pass

    def get_error(self):
        """Retorna el mensaje de error retornado en la firma del documento
        """
        pass

    def carga_datos_firma(self):
        """Carga los datos del documento firmado"""
        pass

    def cotizacion_UI(self, invertida = False):
        tipo_cambio = 1
        # fecha de emisión
        fch = time.strptime(self.date_invoice.strftime(DEFAULT_SERVER_DATE_FORMAT), DEFAULT_SERVER_DATE_FORMAT)
        fecha = "%4d-%02d-%02d" % (fch.tm_year, fch.tm_mon, fch.tm_mday)
        sql_id_ui = """SELECT id from res_currency where name = '%s'""" % MONEDA_UI
        self._cr.execute(sql_id_ui)
        resultado = self._cr.dictfetchall()
        if not resultado:
            raise Warning('No se econtro cotizacion para la Unidad Indexada')
        id_ui = resultado[0]['id']
        sql_tipo_cambio = """SELECT rate FROM res_currency_rate rcr WHERE rcr.name < '%s' AND rcr.currency_id = '%s' ORDER BY rcr.id DESC LIMIT 1""" % (fecha, id_ui)
        self._cr.execute(sql_tipo_cambio)
        result = self._cr.dictfetchall()
        if result:
            tipo_cambio = result[0]['rate']
        return tipo_cambio

    def monto_en_pesos(self):
        resultado = self.amount_untaxed
        # fecha de emisión
        fch = time.strptime(self.date_invoice.strftime(DEFAULT_SERVER_DATE_FORMAT), DEFAULT_SERVER_DATE_FORMAT)
        fecha = "%4d-%02d-%02d" % (fch.tm_year, fch.tm_mon, fch.tm_mday)
        moneda = self.currency_id.name
        if moneda != CODIGO_MONEDA_UY:
            sql_tipo_cambio = """SELECT rate
                                      FROM res_currency_rate rcr
                                      INNER JOIN res_currency rc ON rc.id = rcr.currency_id AND rc.name = '%s'
                                      WHERE rcr.write_date < '%s'
                                      ORDER BY rcr.id DESC
                                      LIMIT 1""" % (moneda, fecha)
            self._cr.execute(sql_tipo_cambio)
            result = self._cr.dictfetchall()
            if result:
                tipo_cambio = result[0]['rate']
                tipo_cambio = round(1/tipo_cambio,3)
                resultado = resultado * tipo_cambio

        return resultado

    def monto_en_UI(self):
        if self.cotizacion_UI() > 0:
            tipo_cambio = round(1/self.cotizacion_UI(),4)
            monto_pesos = self.monto_en_pesos()
            resultado = monto_pesos / tipo_cambio
        else:
            tipo_cambio = round(1/0.258839,4)
            monto_pesos = self.monto_en_pesos()
            resultado = monto_pesos / tipo_cambio
        return resultado

    def valida_empresa(self):
        """
        Valida los datos obligatorios de la empresa.
        """
        if not self.company_id.vat:
            raise Warning(u'Falta el RUT de la empresa. \nLa factura no se creará.')

        if not self.company_id.name:
            raise Warning(u'Falta el nombre de la empresa. \nLa factura no se creará.')

        if not self.company_id.street:
            raise Warning(u'Falta el domicilio de la empresa. \nLa factura no se creará.')

        if not self.company_id.city:
            raise Warning(u'Falta la ciudad de la empresa. \nLa factura no se creará.')

        if not self.company_id.state_id.name:
            raise Warning(u'Falta el departamento de la empresa. \n La factura no se creará.')

        if not self.env['res.store'].search([]).ids:
            raise Warning('No existen sucursales, debe al menos crear una. \nLa factura no se creará.')

        usuario = self.env['res.users'].browse(self._uid)
        if not usuario.store_id:

            raise Warning('El usuario no tiene una sucursal asociada. \nLa factura no se creará.')

    def valida_cliente(self):
        """
        Valida los datos obligatorios del cliente.
        if not (self.partner_id.doc_identidad or self.partner_id.vat):
            raise except_orm(u'El cliente debe tener RUT o Documento de Identidad', u'La factura no se creará.')
        """

        if self.partner_id.is_company and not self.partner_id.vat:
            raise Warning(u'Un Cliente de tipo Empresa debe tener RUT', u'La factura no se creará.')

        if not self.partner_id.name:
            raise Warning(u'Falta el nombre del cliente', u'La factura no se creará.')

        if not self.partner_id.country_id.code:
            raise Warning(u'Falta el país del cliente', u'La factura no se creará.')

        if not self.partner_id.street:
            raise Warning(u'Falta el domicilio del cliente', u'La factura no se creará.')

        if not self.partner_id.city:
            raise Warning(u'Falta la ciudad del cliente', u'La factura no se creará.')

        if not self.partner_id.state_id.name:
            raise Warning(u'Falta el departamento del cliente', u'La factura no se creará.')

        #Para los codigos de paises diferente a UY (uruguay) no validamos el tope
        if self.partner_id.country_id.code == 'UY':
            if self.monto_en_UI() > 10000:
                if not self.partner_id.vat:
                    raise Warning(u'Como el eTicket supera las 10.000 UI debe ingresar el documento del cliente.', u'La factura no se creará.')
            else:
                pass
        if self.for_export and not self.partner_id.vat:
            raise Warning(u'Para una factura de exportación es necesario el RUT del cliente', u'La factura no se creará.')

    def get_payment_term(self):
        try:
            if self.payment_term_id:
                retorno = self.payment_term_id.dgi_payment_ids.dgi_payment_id
                if not retorno:
                    raise Warning(u'La forma de pago no tiene definida si corresponde a Contado o Crédito en DGI', u'Debe configurarlo en los parámetros de facturación electrónica')
            else:
                # si no hay plazos de pago asumimos CONTADO
                retorno = CONTADO
        except:
            raise Warning(u'La forma de pago no tiene definida si corresponde a Contado o Crédito en DGI', u'Debe configurarlo en los parámetros de facturación electrónica')
        return retorno

    def genera_documento(self, tipo_cfe):
        self.valida_empresa()
        self.valida_cliente()

        salida = self.genera_cabezal(tipo_cfe)
        salida += self.genera_lineas
        salida += self.genera_descuentos_globales

        if tipo_cfe == self.NC_EFACTURA or tipo_cfe == self.ND_EFACTURA \
                or tipo_cfe == self.NC_ETICKET or tipo_cfe == self.ND_ETICKET:
            salida += self.genera_nodo_referencia(tipo_cfe)

        salida += self.genera_nodo_adicional(tipo_cfe)
        return salida

    def firma_factura(self):
        """
       Genera el XML para consumir el WS de pro-info para firmar
       la factura y consume el mismo.
       En caso de fallar la firma, retirna False de modo de mantener
       la factura en borrador para obligar el reintento.
       """
        # determino si se genera e-factura o e-ticket a partir de que el cliente tenga o no RUT
        # o si es nota de crédito correspondiente
        if self.partner_id.vat_type == self.DOC_RUT:
            if not self.partner_id.vat:
                raise Warning('¡Debe Ingresar el RUT del Cliente o cambiar el tipo de documento!')
            # eFacturas
            if self.for_export:
                if self.is_debit_note:
                    xml_firma = self.genera_documento(self.ND_EFACTURA_EXP)
                    tipo_cfe = self.ND_EFACTURA_EXP
                else:
                    if self.type == 'out_invoice':
                        xml_firma = self.genera_documento(self.EFACTURA_EXP)
                        tipo_cfe = self.EFACTURA_EXP
                    else:
                        xml_firma = self.genera_documento(self.NC_EFACTURA_EXP)
                        tipo_cfe = self.NC_EFACTURA_EXP
            else:
                if self.is_debit_note:
                    xml_firma = self.genera_documento(self.ND_EFACTURA)
                    tipo_cfe = self.ND_EFACTURA
                else:
                    if self.type == 'out_invoice':
                        xml_firma = self.genera_documento(self.EFACTURA)
                        tipo_cfe = self.EFACTURA
                    else:
                        xml_firma = self.genera_documento(self.NC_EFACTURA)
                        tipo_cfe = self.NC_EFACTURA
        else:
            # eTickets
            if self.is_debit_note:
                xml_firma = self.genera_documento(self.ND_ETICKET)
                tipo_cfe = self.ND_ETICKET
            else:
                if self.type == 'out_invoice':
                    xml_firma = self.genera_documento(self.ETICKET)
                    tipo_cfe = self.ETICKET
                else:
                    xml_firma = self.genera_documento(self.NC_ETICKET)
                    tipo_cfe = self.NC_ETICKET
        if self.fe_Contingencia:
            tipo_cfe += 100     # ejemplo: eFactura = 111, eFactura Contingencia = 211

        # Consumo del servicio
        firmo_ok, mensaje = self.firmar_documento(xml_firma, tipo_cfe)
        _logger.error("%s", xml_firma)
        return firmo_ok, mensaje

    def firma_resguardo(self):
        """
       Genera el XML para consumir el WS para firmar
       el resguardo y consume el mismo.
       En caso de fallar la firma, retirna False de modo de mantener
       la factura en borrador para obligar el reintento.
       """
        xml_firma = self.genera_resguardo()

        # Consumo del servicio
        firmo_ok, mensaje = self.firmar_documento(xml_firma, self.ERESGUARDO)
        return firmo_ok, mensaje

    @api.multi
    def es_produccion(self):
        """
        La función comprueba si el ambiente en que está corriendo eel servicio
        es Producción.

        Para ello realiza tres comprobaciones independientes que deben ser
        verdaderas para determinar que se encuentra efectivamente en dicho
        ambiente. La razón para realizar las tres comprobaciones es simple
        redundacia controlada para reducir en umbral de errores.

        Las comprobaciones realizadas son:
            1. El nombre de la base de datos debe ser produccion
            2. La MAC reportada por uuid.getnode() debe coincidir con la
               almacenada en el parámetro del sistema local_mac.
               En caso de encontrarnos en un ambiente virtual con interfaces sin
               MAC (Las venet de OpenVZ y Virtuozzo) se verificará que la IP
               sea la almacenada en local_ip. Para ello se ejecuta el comando
               de shell "hostname -I" que retorna la lista de direcciones del host.
            3. Debe existir y ser legible por el usuario dueño del servicio, el
               archivo /etc/produccion
        """

        # El nombre de la base de datos
        es_la_base = (self.env.cr.dbname == 'produccion')
        _logger.info("\n\tLlave 01: %s \t La base de datos: %s", es_la_base, self.env.cr.dbname)

        # MAC local
        import uuid
        es_el_hardware = False
        local_mac = self.env['ir.config_parameter'].get_param('local_mac')
        if local_mac:
            es_el_hardware = (local_mac == str(uuid.getnode()))
            _logger.info("\n\tLlave 02: %s \t La MAC local: %s", es_el_hardware, local_mac)

        # IP local
        import subprocess
        es_la_ip = False
        local_ip = self.env['ir.config_parameter'].get_param('local_ip')
        if local_ip:
            es_la_ip = (local_ip in subprocess.getoutput("hostname -I").split())
            _logger.info("\n\tLlave 02: %s \t La IP: %s", es_la_ip, local_ip)

        # Existe /etc/produccion
        from os.path import isfile
        existe_etc_produccion = isfile('/etc/produccion')
        _logger.info("\n\tLlave 03: %s \t El archivo en /etc: %s", existe_etc_produccion, '/etc/produccion')

        return (es_la_base and (es_el_hardware or es_la_ip) and existe_etc_produccion)
        # return existe_etc_produccion

    def hacer_servicio_readonly(self, servicio=None):
        if servicio:
            servicio.solo_lectura = True
            servicio.rt_carga_id.solo_lectura = True
            return True

    @api.one
    def action_invoice_open(self):
        for line in self.invoice_line_ids:
            if line.rt_service_product_id:
                self.hacer_servicio_readonly(servicio=line.rt_service_product_id)
        if self.type == 'out_refund':
            if self.refund_invoice_id:
                if self.amount_total > self.refund_invoice_id.amount_total:
                    raise Warning('No puede validar una Nota de Crédito que supere el monto de la Factura Asociada')

        sys_cfg = self.env['ir.config_parameter']
        #Pregutamos si esta cfe activa o no
        cfe_activa = sys_cfg.get_param('electronic_invoice.fe_activa')
        if not cfe_activa:
            return super(AccountInvoice, self).action_invoice_open()

        if not self.date_invoice:
            self.date_invoice = fields.Date.context_today(self)
        self.cotizacion_UI()
        self.monto_en_pesos()
        self.action_move_create()
        self.einvoice_sign_it()
        return super(AccountInvoice, self).action_invoice_open()



    def einvoice_sign_it(self):
        """Accion que firma electrónicamente la factura"""
        sys_cfg = self.env['ir.config_parameter']
        if sys_cfg.get_param('fe_inactiva'):
            return True
        PROVEEDOR = "purchase"
        NCREPROVEEDOR = "purchase_refund"
        if self.journal_id.type not in (PROVEEDOR, NCREPROVEEDOR):  #no firmamos los documentos de proveedores
            firmo_ok, mensaje = self.firma_factura()
            if not firmo_ok:
                raise Warning(u'¡ No se pudo firmar ! \n %s' % mensaje)

        return True

class MailTemplate(models.Model):
    _inherit = "mail.template"


    def get_mail_recipients(self, partner):
        type = 'Facturacion electronica'
        list_mails = []
        for mail in partner.email_ids:
            if mail.email_type_id.name == type:
                list_mails.append(mail.email)
        return list_mails



    @api.multi
    def generate_recipients(self, results, res_ids):
        """Generates the recipients of the template. Default values can ben generated
        instead of the template values if requested by template or context.
        Emails (email_to, email_cc) can be transformed into partners if requested
        in the context. """
        self.ensure_one()

        if self.use_default_to or self._context.get('tpl_force_default_to'):
            default_recipients = self.env['mail.thread'].message_get_default_recipients(res_model=self.model, res_ids=res_ids)
            for res_id, recipients in default_recipients.items():
                results[res_id].pop('partner_to', None)
                results[res_id].update(recipients)

        records_company = None
        if self._context.get('tpl_partners_only') and self.model and results and 'company_id' in self.env[self.model]._fields:
            records = self.env[self.model].browse(results.keys()).read(['company_id'])
            records_company = {rec['id']: (rec['company_id'][0] if rec['company_id'] else None) for rec in records}

        for res_id, values in results.items():
            partner_ids = values.get('partner_ids', list())
            if self._context.get('tpl_partners_only'):
                if self._context.get('active_model') == 'account.invoice':
                    invoice = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
                    partner_invoice = invoice.partner_id
                    mails = self.get_mail_recipients(partner_invoice)
                else:
                    mails = tools.email_split(values.pop('email_to', '')) + tools.email_split(values.pop('email_cc', ''))

                Partner = self.env['res.partner']
                if records_company:
                    Partner = Partner.with_context(default_company_id=records_company[res_id])
                for mail in mails:
                    partner_id = Partner.find_or_create(mail)
                    partner_ids.append(partner_id)
            partner_to = values.pop('partner_to', '')
            if partner_to:
                # placeholders could generate '', 3, 2 due to some empty field values
                tpl_partner_ids = [int(pid) for pid in partner_to.split(',') if pid]
                partner_ids += self.env['res.partner'].sudo().browse(tpl_partner_ids).exists().ids
            results[res_id]['partner_ids'] = partner_ids
        return results

class MailComposer(models.TransientModel):
    """ Generic message composition wizard. You may inherit from this wizard
        at model and view levels to provide specific features.

        The behavior of the wizard depends on the composition_mode field:
        - 'comment': post on a record. The wizard is pre-populated via ``get_record_data``
        - 'mass_mail': wizard in mass mailing mode where the mail details can
            contain template placeholders that will be merged with actual data
            before being sent to each recipient.
    """
    _inherit = 'mail.compose.message'

    @api.model
    def get_record_data(self, values):
        """ Returns a defaults-like dict with initial values for the composition
        wizard when sending an email related a previous email (parent_id) or
        a document (model, res_id). This is based on previously computed default
        values. """
        result, subject = {}, False
        if values.get('parent_id'):
            parent = self.env['mail.message'].browse(values.get('parent_id'))
            result['record_name'] = parent.record_name,
            subject = tools.ustr(parent.subject or parent.record_name or '')
            if not values.get('model'):
                result['model'] = parent.model
            if not values.get('res_id'):
                result['res_id'] = parent.res_id
            partner_ids = values.get('partner_ids', list()) + [(4, id) for id in parent.partner_ids.ids]
            if self._context.get('is_private') and parent.author_id:  # check message is private then add author also in partner list.
                partner_ids += [(4, parent.author_id.id)]
            result['partner_ids'] = partner_ids
        elif values.get('model') and values.get('res_id'):
            # doc_name_get = self.env[values.get('model')].browse(values.get('res_id')).name_get()
            doc = self.env[values.get('model')].browse(values.get('res_id'))
            if doc._name == 'account.invoice':
                if 'out_invoice' or 'in_invoice' or 'in_refund' not in doc._fields:
                    doc_name_get = self.env[values.get('model')].browse(values.get('res_id')).name_get()
                else:
                    if doc.type == 'out_invoice':
                        if doc.state in ['open', 'paid']:
                            doc_name_get = doc.fe_Serie + ' ' + str(doc.fe_DocNro) + ' - ' + str(doc.name)
                        elif doc.state == 'draft':
                            doc_name_get = 'Factura Borrador / ' + str(doc.name)
                    if doc.type == 'out_refund':
                        if doc.state in ['open', 'paid']:
                            doc_name_get = doc.fe_Serie + ' ' + str(doc.fe_DocNro) + ' - ' + str(doc.name)
                        elif doc.state == 'draft':
                            doc_name_get = 'Nota de Crédito Borrador / ' + str(doc.name)
                    if doc.type in ['in_invoice', 'in_refund']:
                        doc_name_get = doc.partner_id.name + ' ' + str(doc.reference)
                if doc.type in ['in_invoice', 'in_refund']:
                    doc_name_get = doc.partner_id.name + ' ' + str(doc.reference)
            else:
                doc_name_get = self.env[values.get('model')].browse(values.get('res_id')).name_get()




            result['record_name'] = doc_name_get
            subject = tools.ustr(result['record_name'])

        re_prefix = _('Re:')
        if subject and not (subject.startswith('Re:') or subject.startswith(re_prefix)):
            subject = "%s %s" % (re_prefix, subject)
        result['subject'] = subject
        #print(result)
        return result

class MailMail(models.Model):
    """ Model holding RFC2822 email messages to send. This model also provides
        facilities to queue and send new email messages.  """
    _inherit = 'mail.mail'

    def compose_string(self, string=None, invoice=None):
        if string and invoice:
            if 'Your Factura' in string:
                if invoice.type == 'out_invoice':
                    string = string.replace('Your Factura', 'Su Factura')
                if invoice.type == 'out_refund':
                    string = string.replace('Your Factura', 'Su Nota de Crédito')
                string = string.replace(invoice.number, str(invoice.fe_Serie) + '-' + str(invoice.fe_DocNro))
        return string

    @api.model
    def create(self, values):
        context = self.env.context
        account_invoice = 'account.invoice'
        model = context.get('active_model')
        model_id = context.get('active_ids')
        if model == account_invoice:
            if model_id:
                invoice = self.env[model].browse(model_id)
                if invoice:
                    # Voy a iterar sobre el diccionario de valores a crear
                    for key, value in values.items():
                        if key == 'body_html':
                            values[key] = self.compose_string(string=value, invoice=invoice)
        # notification field: if not set, set if mail comes from an existing mail.message
        if 'notification' not in values and values.get('mail_message_id'):
            values['notification'] = True
        new_mail = super(MailMail, self).create(values)
        if values.get('attachment_ids'):
            new_mail.attachment_ids.check(mode='read')
        return new_mail

class AccountInvoiceRefund(models.TransientModel):
    """Credit Notes"""

    _inherit = "account.invoice.refund"

    def compose_message(self, invoice):
        message = ''
        EF = 'E- Facturas'
        ET = 'E- Tickets'
        if invoice:
            if invoice.journal_id.name == EF:
                message = 'Afecta a EF %s-%s' %(str(invoice.fe_Serie), invoice.fe_DocNro)
            if invoice.journal_id.name == ET:
                message = 'Afecta a ET %s-%s' % (str(invoice.fe_Serie), invoice.fe_DocNro)

            if (invoice.journal_id.name != EF and invoice.journal_id.name != ET):
                message = 'Afacta a %s-%s' %(str(invoice.fe_Serie), invoice.fe_DocNro)

        return message

    @api.model
    def _get_reason(self):
        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if active_id:
            inv = self.env['account.invoice'].browse(active_id)
            return self.compose_message(inv)
        return ''


    description = fields.Char(string='Reason', required=True, default=_get_reason)