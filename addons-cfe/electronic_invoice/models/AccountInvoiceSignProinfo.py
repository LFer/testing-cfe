# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from odoo.exceptions import AccessError, except_orm, ValidationError, UserError, Warning
import time
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from xml.sax.saxutils import escape
import ipdb
_logger = logging.getLogger(__name__)
from suds import WebFault
from suds.client import Client
# from qrcode import *
import qrcode
from io import StringIO, BytesIO
import tempfile
import base64
import lxml.etree as et

KEY_URL_PRODUCCION = "electronic_invoice.url_produccion"
KEY_URL_TESTING = "electronic_invoice.url_testing"


class account_invoice(models.Model):
    """
    Extiende account.involice para facturación electrónica.
    Redefine las funciones que generar el xml a enviar al proveedor.
    """
    _inherit = "account.invoice"

    def genera_cabezal(self, tipo_cfe):
        """
        Genera el cabezal de una e-factura
        :param tipo_cfe: tipo de documento DGI
        :return: string de cabezal de la e-factura
        """
        CODIGO_MONEDA_UY = 'UYU'
        CODIGO_PAIS_UY = 'UY'
        #TODO: mejorar la forma de obtener los datos de la codiguera
        self.env.cr.execute("select code,value from dgi_codes order by code")
        res = self.env.cr.fetchone()
        CODIGO_EXENTO = res[0]
        EXENTO = res[1]
        res = self.env.cr.fetchone()
        CODIGO_MINIMO = res[0]
        IVA_MINIMO = res[1]
        res = self.env.cr.fetchone()
        CODIGO_BASICO = res[0]
        IVA_BASICO = res[1]

        cliente_tipo_doc = 0
        cliente_doc = 0
        tipo_doc = 0
        tipo_cambio = 0
        sys_cfg = self.env['ir.config_parameter']

        # ---------- IDENTIFICACION COMPROBANTE -------------
        # nro de serie
        # nro de comprobante
        if self.fe_Contingencia:
            tipo_doc = tipo_cfe + 100   # ejemplo: eFactura = 111, eFactura Contingencia = 211
            serie = self.fe_SerieContingencia
            numero = self.fe_DocNroContingencia
        else:
            tipo_doc = tipo_cfe
            serie, numero = self.get_serie_nro(self.number)

        # fecha de emisión
        fch = time.strptime(self.date_invoice.strftime(DEFAULT_SERVER_DATE_FORMAT), DEFAULT_SERVER_DATE_FORMAT)
        fecha = "%4d-%02d-%02d" % (fch.tm_year, fch.tm_mon, fch.tm_mday)

        # forma de pago
        pago = self.get_payment_term()

        # ---------- EMISOR ---------------------------------
        RUT = self.company_id.vat[2:]
        nombre = escape(self.company_id.name)
        usuario = self.env['res.users'].browse(self._uid)
        sucursal = usuario.store_id.nro_suc_dgi
        domicilio = escape(self.company_id.street[:70])
        ciudad = escape(self.company_id.city)
        departamento = escape(self.company_id.state_id.name)
        # ---------- RECEPTOR -------------------------------
        cliente_tipo_doc = self.partner_id.vat_type

        cliente_doc = ''

        if self.partner_id.vat:

            cliente_doc = self.partner_id.vat[2:]

        # if tipo_cfe in (self.EFACTURA, self.NC_EFACTURA, self.ND_EFACTURA):
        #     # tipo documento
        #     cliente_tipo_doc = 2
        #     cliente_doc = self.partner_id.vat[2:]
        # if tipo_cfe in (self.EFACTURA_EXP, self.NC_EFACTURA_EXP, self.ND_EFACTURA_EXP):
        #     # tipo documento
        #     cliente_tipo_doc = 4
        #     cliente_doc = self.partner_id.vat[2:]
        # if tipo_cfe in (self.ETICKET, self.NC_ETICKET, self.ND_ETICKET):
        #     # tipo documento
        #     cliente_tipo_doc = 3
        #     cliente_doc = self.partner_id.doc_identidad

        # if not cliente_doc:
        #     cliente_doc = 0
        #     cliente_tipo_doc = 0

        cliente_nombre = escape(self.filter_special_chars(self.partner_id.name))
        cliente_domicilio = escape(self.partner_id.street[:70])
        cliente_ciudad = escape(self.partner_id.city)
        cliente_departamento = escape(self.partner_id.state_id.name)
        cliente_pais_cod = self.partner_id.country_id.code
        cliente_pais_nombre = self.partner_id.country_id.name

        # if cliente_pais_cod != CODIGO_PAIS_UY:
        #     cliente_tipo_doc = 4

        # ---------- TOTALES --------------------------------

        moneda = self.currency_id.name
        if moneda != CODIGO_MONEDA_UY:
            if 'check_rate' in self._fields:
                if self.check_rate:
                    tipo_cambio = self.rate_exchange
                else:
                    currency_id = self.env['res.currency'].search([('name', '=', moneda)])
                    currency_rate = self.env['res.currency.rate'].search(
                        [('currency_id', '=', currency_id.id), ('write_date', '<=', fecha), ('name', '<=', fecha)],
                        limit=1)
                    if currency_rate:
                        tipo_cambio = currency_rate.rate
                    # Si no encuentro el tipo de cambio que hago?
                    elif not currency_rate:
                        sql_tipo_cambio = """SELECT rate FROM res_currency_rate rcr INNER JOIN res_currency rc ON rc.id = rcr.currency_id AND rc.name = '%s' WHERE rcr.write_date < '%s' ORDER BY rcr.id DESC LIMIT 1""" % (
                        moneda, fecha)
                        self._cr.execute(sql_tipo_cambio)
                        result = self._cr.dictfetchall()
                        if result:
                            tipo_cambio = result[0]['rate']
            else:
                currency_id = self.env['res.currency'].search([('name','=',moneda)])
                currency_rate = self.env['res.currency.rate'].search([('currency_id', '=', currency_id.id), ('write_date', '<=', fecha), ('name', '<=', fecha)], limit=1)
                if currency_rate:
                    tipo_cambio = currency_rate.rate
                #Si no encuentro el tipo de cambio que hago?
                elif not currency_rate:
                    sql_tipo_cambio = """SELECT rate FROM res_currency_rate rcr INNER JOIN res_currency rc ON rc.id = rcr.currency_id AND rc.name = '%s' WHERE rcr.write_date < '%s' ORDER BY rcr.id DESC LIMIT 1""" % (moneda, fecha)
                    self._cr.execute(sql_tipo_cambio)
                    result = self._cr.dictfetchall()
                    if result:
                        tipo_cambio = result[0]['rate']

        # monto total (+ IVA)
        monto_total = "%.2f" % self.amount_total
        monto_total_neto = self.amount_untaxed
        if 'discount' in self.env['account.invoice.line']._fields:
            try:
                total_descuento = 0 #FIXME self.amount_discount no existe mas, ver como hacerse con el monto
            except AttributeError:
                total_descuento = 0
        total_lineas = len(self.invoice_line_ids)
        decimal_precision = self.env['decimal.precision'].precision_get('Account')

        # recorro las líneas para obtener los totales por tipo de IVA
        total_monto_IVA_basico = 0
        total_monto_IVA_minimo = 0
        total_monto_exento = 0
        total_IVA_basico = 0
        total_IVA_minimo = 0
        total_desc_IVA_basico = 0
        total_desc_IVA_minimo = 0
        total_desc_exento = 0
        total_monto_retenido = 0
        for linea in self.invoice_line_ids:

            tipo_IVA = linea.invoice_line_tax_ids.dgi_code_ids.dgi_code_id.amount #TODO ¿Que pasa si tiene mas de un impuesto?
            codigo_IVA = linea.invoice_line_tax_ids.dgi_code_ids.dgi_code_id.code

            if not codigo_IVA:
                raise UserError(u'Hay artículos que no tienen el impuesto cargado' '\n'  u'La factura no se creará.')

            monto_linea = round(linea.price_subtotal, decimal_precision)
            monto_IVA = round((monto_linea*tipo_IVA), decimal_precision)
            try:
                monto_descuento = round((monto_linea/monto_total_neto)*total_descuento, decimal_precision)
            except:
                monto_descuento = 0
            if codigo_IVA == CODIGO_BASICO:
                total_monto_IVA_basico += monto_linea - monto_descuento
                total_IVA_basico += monto_IVA - monto_descuento
                total_desc_IVA_basico += monto_descuento
            elif codigo_IVA == CODIGO_MINIMO:
                total_monto_IVA_minimo += monto_linea - monto_descuento
                total_IVA_minimo += monto_IVA - monto_descuento
                total_desc_IVA_minimo += monto_descuento
            else:
                total_monto_exento += monto_linea - monto_descuento
                total_desc_exento += monto_descuento

        total_monto_IVAs = total_monto_IVA_basico + total_monto_IVA_minimo + total_monto_exento + total_IVA_basico + total_IVA_minimo
        if self.amount_total != total_monto_IVAs:
            if total_IVA_basico > 0:
                total_IVA_basico += (self.amount_total - total_monto_IVAs)
            else:
                total_monto_IVA_minimo += (self.amount_total - total_monto_IVAs)

        salida = '<CFEEntrada xmlns="esignit">\n'
        salida += '    <XMLEntradaNodoCFE>\n'
        salida += '        <FEIDDocTipoCFE>%d</FEIDDocTipoCFE>\n' % tipo_doc
        salida += '        <FEIDDocSerie>%s</FEIDDocSerie>\n' % serie
        salida += '        <FEIDDocNro>%d</FEIDDocNro>\n' % numero
        salida += '        <FEIDDocFchEmis>%s</FEIDDocFchEmis>\n' % fecha
        salida += '        <FEIDDocFmaPago>%d</FEIDDocFmaPago>\n' % pago
        salida += '        <FEIDDocFchVenc>%s</FEIDDocFchVenc>\n' % fecha
        if cliente_tipo_doc == 4:
            salida += '        <FEIDDocClauVenta>FOB</FEIDDocClauVenta>\n'
            salida += '        <FEIDDocModVenta>1</FEIDDocModVenta>\n'
            salida += '        <FEIDDocViaTransp>8</FEIDDocViaTransp>\n'
        salida += '        <FEEMIRUCEmisor>%s</FEEMIRUCEmisor>\n' % RUT
        salida += '        <FEEMIRznSoc>%s</FEEMIRznSoc>\n' % nombre
        salida += '        <FEEMINomComercial>%s</FEEMINomComercial>\n' % nombre
        salida += '        <FEEMICdgDGISucur>%s</FEEMICdgDGISucur>\n' % sucursal
        salida += '        <FEEMIDomFiscal>%s</FEEMIDomFiscal>\n' % domicilio
        salida += '        <FEEMICiudad>%s</FEEMICiudad>\n' % ciudad
        salida += '        <FEEMIDepartamento>%s</FEEMIDepartamento>\n' % departamento
        if tipo_cfe == self.ETICKET or tipo_cfe == self.NC_ETICKET or tipo_cfe == self.ND_ETICKET:
            #Pongo mayor a cero asi entra siempre, deberia entrar siempre tendria que sacar ese control o mejorarlo
            if self.monto_en_UI() > 0:
                salida += '        <FERECTipoDocRecep>%s</FERECTipoDocRecep>\n' % cliente_tipo_doc
                salida += '        <FERECCodPaisRecep>%s</FERECCodPaisRecep>\n' % cliente_pais_cod
                if cliente_pais_cod == CODIGO_PAIS_UY:
                    salida += '        <FERECDocRecep>%s</FERECDocRecep>\n' % cliente_doc
                else:
                    salida += '        <FERECDocRecepExt>%s</FERECDocRecepExt>\n' % cliente_doc

                salida += '        <FERECRznSocRecep>%s</FERECRznSocRecep>\n' % cliente_nombre

                if cliente_domicilio:
                    salida += '        <FERECDirRecep>%s</FERECDirRecep>\n' % cliente_domicilio

                salida += '        <FERECCiudadRecep>%s</FERECCiudadRecep>\n' % cliente_ciudad
                salida += '        <FERECDeptoRecep>%s</FERECDeptoRecep>\n' % cliente_departamento
        else:
            salida += '        <FERECTipoDocRecep>%s</FERECTipoDocRecep>\n' % cliente_tipo_doc
            salida += '        <FERECCodPaisRecep>%s</FERECCodPaisRecep>\n' % cliente_pais_cod
            salida += '        <FERECPaisRecep>%s</FERECPaisRecep>\n' % cliente_pais_nombre
            if cliente_pais_cod == CODIGO_PAIS_UY:
                salida += '        <FERECDocRecep>%s</FERECDocRecep>\n' % cliente_doc
            else:
                salida += '        <FERECDocRecepExt>%s</FERECDocRecepExt>\n' % cliente_doc

            salida += '        <FERECRznSocRecep>%s</FERECRznSocRecep>\n' % cliente_nombre

            if cliente_domicilio:
                salida += '        <FERECDirRecep>%s</FERECDirRecep>\n' % cliente_domicilio

            salida += '        <FERECCiudadRecep>%s</FERECCiudadRecep>\n' % cliente_ciudad
            salida += '        <FERECDeptoRecep>%s</FERECDeptoRecep>\n' % cliente_departamento

        if tipo_cfe == self.ETICKET or tipo_cfe == self.NC_ETICKET:
            salida += '        <FERECCP>0</FERECCP>\n'
            salida += '        <FERECCompraID></FERECCompraID>\n'

        salida += '        <FETOTTpoMoneda>%s</FETOTTpoMoneda>\n' % moneda

        if moneda != CODIGO_MONEDA_UY:
            salida += '        <FETOTTpoCambio>%s</FETOTTpoCambio>\n' % tipo_cambio

        # Si alguna de las lineas de la factura tiene el impuesto IVA Excento Exportacion
        # debe ir el tag ExpoyAsim
        codigo_10 = False
        for linea in self.invoice_line_ids:
            if linea.invoice_line_tax_ids.dgi_code_ids.dgi_code_id.code == 10:
                codigo_10 = True

        if cliente_tipo_doc == 4 or codigo_10:
            salida += '        <FETOTMntExpoyAsim>%s</FETOTMntExpoyAsim>\n' % monto_total
            salida += '        <FETOTMntTotal>%s</FETOTMntTotal>\n' % monto_total
        else:
            if tipo_cfe != self.ERESGUARDO:
                if total_monto_exento > 0:
                    salida += '        <FETOTMntNoGrv>%s</FETOTMntNoGrv>\n' % total_monto_exento
                if total_monto_IVA_minimo > 0:
                    salida += '        <FETOTMntNetoIvaTasaMin>%s</FETOTMntNetoIvaTasaMin>\n' % total_monto_IVA_minimo
                if total_monto_IVA_basico > 0:
                    salida += '        <FETOTMntNetoIVATasaBasica>%s</FETOTMntNetoIVATasaBasica>\n' % total_monto_IVA_basico
                if total_monto_IVA_minimo > 0:
                    salida += '        <FETOTIVATasaMin>%s</FETOTIVATasaMin>\n' % IVA_MINIMO
                if total_monto_IVA_basico > 0:
                    salida += '        <FETOTIVATasaBasica>%s</FETOTIVATasaBasica>\n' % IVA_BASICO
                if total_monto_IVA_minimo > 0:
                    salida += '        <FETOTMntIVATasaMin>%s</FETOTMntIVATasaMin>\n' % total_IVA_minimo
                if total_monto_IVA_basico > 0:
                    salida += '        <FETOTMntIVATasaBasica>%s</FETOTMntIVATasaBasica>\n' % total_IVA_basico
                salida += '        <FETOTMntTotal>%s</FETOTMntTotal>\n' % monto_total
            else:
                salida += '        <FETOTMntTotRetenido>%s</FETOTMntTotRetenido>\n' % total_monto_retenido

        salida += '        <FETOTCantLinDet>%s</FETOTCantLinDet>\n' % total_lineas

        if tipo_cfe != self.ERESGUARDO:
            salida += '        <FETOTMntPagar>%s</FETOTMntPagar>\n' % monto_total
        # else:
        #     salida += genera_resguardo
        _logger.error("%s", salida)
        return salida

    @property
    def genera_lineas(self):


        """
        Genera las líneas de una e-factura
        :return: string de líneas de la e-factura
        """
        salida = '        <FEDetalles>\n'
        unidad_medida = 'CANT'
        INDICADOR_EXPO = 10
        INDICADOR_GRATUITO = 5
        nro_linea = 1
        decimal_precision = self.env['decimal.precision'].precision_get('Account')
        for linea in self.invoice_line_ids:
            con_impuesto = linea.invoice_line_tax_ids.price_include
            if self.for_export:
                indicador_facturacion = INDICADOR_EXPO
            else:
                indicador_facturacion = linea.invoice_line_tax_ids.dgi_code_ids.dgi_code_id.code
            nombre_item = escape(self.filter_special_chars(linea.name))[0:79]
            cantidad = linea.quantity
            precio_unitario = linea.price_unit
            if precio_unitario == 0:
                indicador_facturacion = INDICADOR_GRATUITO
            descuento = precio_unitario * cantidad * (linea.discount / 100)

            if con_impuesto:
                impuesto = linea.invoice_line_tax_id.amount
                precio_unitario = round(precio_unitario / (1 + impuesto), decimal_precision)
                descuento = round(descuento / (1 + impuesto), decimal_precision)

            precio_total = linea.price_subtotal
            # desc_global = round((precio_total - (precio_unitario*cantidad)), decimal_precision)
            # descuento = descuento + desc_global
            # precio_total = precio_total - desc_global
            # precio_unitario = precio_unitario + round((desc_global / cantidad), decimal_precision)
            salida += '            <FEDetalle>\n'
            salida += '                <FEDETNroLinDet>%s</FEDETNroLinDet>\n' % nro_linea
            salida += '                <FEDETIndFact>%s</FEDETIndFact>\n' % indicador_facturacion
            salida += '                <FEDETNomItem>%s</FEDETNomItem>\n' % nombre_item
            salida += '                <FEDETCantidad>%s</FEDETCantidad>\n' % cantidad
            salida += '                <FEDETUniMed>%s</FEDETUniMed>\n' % unidad_medida
            salida += '                <FEDETPrecioUnitario>%s</FEDETPrecioUnitario>\n' % precio_unitario
            if descuento:
                salida += '                <FEDETDescuentoMonto>%s</FEDETDescuentoMonto>\n' % descuento
            salida += '                <FEDETMontoItem>%s</FEDETMontoItem>\n' % precio_total
            salida += '            </FEDetalle>\n'
            nro_linea += 1

        salida += '        </FEDetalles>\n'

        return salida

    @property
    def genera_descuentos_globales(self):
        """
        Genera el bloque de descuentos globales del documento electrónico
        :return: string del bloque de descuentos globales del documento electrónico
        """
        EXENTO_IVA = 1
        TASA_MINIMA = 2
        TASA_BASICA = 3
        contador = 0
        salida = ''
        if hasattr(self, 'amount_discount'):
            if self.amount_discount > 0:
                salida = '          <FEDscRcgGlobals>\n'
                if self.discount_tax_basica > 0:
                    contador += 1
                    salida += self.bloque_descuento(contador, TASA_BASICA, self.discount_tax_basica)
                if self.discount_tax_minima > 0:
                    contador += 1
                    salida += self.bloque_descuento(contador, TASA_MINIMA, self.discount_tax_minima)
                if self.discount_tax_exento > 0:
                    contador += 1
                    salida += self.bloque_descuento(contador, EXENTO_IVA, self.discount_tax_exento)
                salida += '          </FEDscRcgGlobals>\n'
        return salida

    def bloque_descuento(self, contador, tasa, monto):
        TIPO_MONTO = 2
        decimal_precision = self.env['decimal.precision'].precision_get('Account')
        descuento_basica = round(self.discount_tax_basica, decimal_precision)
        salida = '             <FEDscRcgGlobal>\n'
        salida += '                 <FEDRGNroLinDR>%s</FEDRGNroLinDR>\n' % contador
        salida += '                 <FEDRGTpoMovDR>D</FEDRGTpoMovDR>\n'
        salida += '                 <FEDRGTpoDR>%s</FEDRGTpoDR>\n' % TIPO_MONTO
        salida += '                 <FEDRGGlosaDR>d%s</FEDRGGlosaDR>\n' % tasa
        salida += '                 <FEDRGValorDR>%s</FEDRGValorDR>\n' % descuento_basica
        salida += '                 <FEDRGIndFactDR>%s</FEDRGIndFactDR>\n' % tasa
        salida += '             </FEDscRcgGlobal>\n'
        return salida

    def genera_resguardo(self):
        salida = """<CFEEntrada xmlns="esignit">
                        <XMLEntradaNodoCFE>
                            <FEIDDocTipoCFE>182</FEIDDocTipoCFE>
                            <FEIDDocSerie>A</FEIDDocSerie>
                            <FEIDDocNro>2</FEIDDocNro>
                            <FEIDDocFchEmis>2016-04-28</FEIDDocFchEmis>
                            <FEEMIRUCEmisor>212093440010</FEEMIRUCEmisor>
                            <FEEMIRznSoc>PRUEBA S.A.</FEEMIRznSoc>
                            <FEEMINomComercial>PRUEBA</FEEMINomComercial>
                            <FEEMICorreoEmisor>PRUEBA@PRUEBA.com.uy</FEEMICorreoEmisor>
                            <FEEMICdgDGISucur>1</FEEMICdgDGISucur>
                            <FEEMIDomFiscal>PRUEBA 1339 esq. PRUEBA</FEEMIDomFiscal>
                            <FEEMICiudad>Montevideo</FEEMICiudad>
                            <FEEMIDepartamento>Montevideo</FEEMIDepartamento>
                            <FERECTipoDocRecep>3</FERECTipoDocRecep>
                            <FERECCodPaisRecep>UY</FERECCodPaisRecep>
                            <FERECDocRecep>35378149</FERECDocRecep>
                            <FERECRznSocRecep>JUAN HERNAN PEREZ</FERECRznSocRecep>
                            <FERECDirRecep>PRUEBA 1339</FERECDirRecep>
                            <FERECCiudadRecep>Montevideo</FERECCiudadRecep>
                            <FERECDeptoRecep>Montevideo</FERECDeptoRecep>
                            <FERECPaisRecep>Uruguay</FERECPaisRecep>
                            <FETOTTpoMoneda>UYU</FETOTTpoMoneda>
                            <FETOTTpoCambio>1.000</FETOTTpoCambio>
                            <FETOTMntTotRetenido>7084.58</FETOTMntTotRetenido>
                            <FETOTCantLinDet>3</FETOTCantLinDet>
                            <FETOTRetenPerceps>
                                <FETOTRetenPercep>
                                    <FETOTCodRet>1146-171</FETOTCodRet>
                                    <FETOTValRetPerc>7084.58</FETOTValRetPerc>
                                    </FETOTRetenPercep>
                            </FETOTRetenPerceps>
                            <FEDetalles>
                                <FEDetalle>
                                    <FEDETNroLinDet>1</FEDETNroLinDet>
                                    <FEDETRetencPerceps>
                                        <FEDETRetencPercep>
                                            <FEDETCodRet>1146-171</FEDETCodRet>
                                            <FEDETTasa>10.500</FEDETTasa>
                                            <FEDETMntSujetoaRet>39750.00</FEDETMntSujetoaRet>
                                            <FEDETValRetPerc>4173.75</FEDETValRetPerc>
                                        </FEDETRetencPercep>
                                    </FEDETRetencPerceps>
                                </FEDetalle>
                                <FEDetalle>
                                    <FEDETNroLinDet>2</FEDETNroLinDet>
                                    <FEDETRetencPerceps>
                                        <FEDETRetencPercep>
                                            <FEDETCodRet>1146-171</FEDETCodRet>
                                            <FEDETTasa>10.500</FEDETTasa>
                                            <FEDETMntSujetoaRet>15500.00</FEDETMntSujetoaRet>
                                            <FEDETValRetPerc>1627.50</FEDETValRetPerc>
                                        </FEDETRetencPercep>
                                    </FEDETRetencPerceps>
                                </FEDetalle>
                                <FEDetalle>
                                    <FEDETNroLinDet>3</FEDETNroLinDet>
                                    <FEDETRetencPerceps>
                                        <FEDETRetencPercep>
                                            <FEDETCodRet>1146-171</FEDETCodRet>
                                            <FEDETTasa>10.500</FEDETTasa>
                                            <FEDETMntSujetoaRet>12222.23</FEDETMntSujetoaRet>
                                            <FEDETValRetPerc>1283.33</FEDETValRetPerc>
                                        </FEDETRetencPercep>
                                    </FEDETRetencPerceps>
                                </FEDetalle>
                            </FEDetalles>
                        </XMLEntradaNodoCFE>
                        <XMLEntradaNodoAdicional>
                            <TipoDocumentoId>182</TipoDocumentoId>
                            <DocComCodigo>6</DocComCodigo>
                            <DocComSerie>A</DocComSerie>
                            <SucursalId>1</SucursalId>
                            <Adenda>#1 padron 1122
                                    #2 padron 2211
                                    #3 padron 3311
                            </Adenda>
                            <LoteId>0</LoteId>
                            <EsReceptor>false</EsReceptor>
                        </XMLEntradaNodoAdicional>
                    </CFEEntrada>"""
        return salida


    def genera_nodo_referencia(self, tipo_cfe):
        #pdb.set_trace()
        serie = False
        if self.is_debit_note:
            doc_origen = self.invoice_id
        else:
            if self.origin:
                doc_origen = self.env['account.invoice'].search([('number', '=', self.origin)], limit=1)
            else:
                doc_origen = ''
        if doc_origen:
            serie = doc_origen.fe_Serie
            doc_nro = doc_origen.fe_DocNro
            doc_referencia = doc_origen.fe_TipoCFE
            nro_interno = doc_origen.number
        else:
            serie = ''
            doc_nro = ''
            doc_referencia = ''
            nro_interno = self.origin or ''

        salida = '        <FEReferencias>\n'
        salida += '            <FEReferencia>\n'
        salida += '                <FEREFNroLinRef>1</FEREFNroLinRef>\n'

        if serie:
            # el documento referencia es electrónico
            salida += '                <FEREFTpoDocRef>%s</FEREFTpoDocRef>\n' % doc_referencia
            salida += '                <FEREFSerie>%s</FEREFSerie>\n' % serie
            salida += '                <FEREFNroCFERef>%s</FEREFNroCFERef>\n' % doc_nro
        else:
            salida += '                <FEREFIndGlobal>1</FEREFIndGlobal>\n'
            salida += '                <FEREFRazonRef>Referencia a documento fuera de regimen electronico %s</FEREFRazonRef>\n' % nro_interno.encode('utf-8')

        salida += '            </FEReferencia>\n'
        salida += '        </FEReferencias>\n'

        return salida



    def genera_nodo_adicional(self, tipo_cfe):
        es_contingencia = "false"
        sys_cfg = self.env['ir.config_parameter']

        # nro de serie
        # nro de comprobante
        if self.fe_Contingencia:
            tipo_doc = tipo_cfe + 100   # ejemplo: eFactura = 111, eFactura Contingencia = 211
            serie = self.fe_SerieContingencia
            numero = self.fe_DocNroContingencia
            es_contingencia = "true"
            cae_desde = sys_cfg.get_param("dtm_fe_CAEDNro")
            cae_hasta = sys_cfg.get_param("dtm_fe_CAEHNro")
            cae_nro_aut = sys_cfg.get_param("dtm_fe_CAENA")
            cae_fecha_aut = sys_cfg.get_param("dtm_fe_CAEFA")
            cae_fecha_venc = sys_cfg.get_param("dtm_fe_CAEFVD")
        else:
            tipo_doc = tipo_cfe
            serie, numero = self.get_serie_nro(self.number)
        usuario = self.env['res.users'].browse(self._uid)
        #sucursal = usuario.store_id.nro_suc_dgi
        sucursal = 1
        adenda = ""
        if self.comment:
            adenda = self.filter_special_chars(self.comment)

        es_receptor = "false"

        salida = '    </XMLEntradaNodoCFE>\n'
        salida += '    <XMLEntradaNodoAdicional>\n'
        salida += '        <TipoDocumentoId>%s</TipoDocumentoId>\n' % tipo_doc
        salida += '        <DocComCodigo>%s</DocComCodigo>\n' % numero
        salida += '        <DocComSerie>%s</DocComSerie>\n' % serie
        salida += '        <SucursalId>%s</SucursalId>\n' % sucursal
        salida += '        <Adenda>%s</Adenda>\n' % adenda
        salida += '        <Contingencia>%s</Contingencia>\n' % es_contingencia

        if self.fe_Contingencia:
            salida += '        <CAEDnro>%s</CAEDnro>\n' % cae_desde
            salida += '        <CAEHnro>%s</CAEHnro>\n' % cae_hasta
            salida += '        <CAENA>%s</CAENA>\n' % cae_nro_aut
            salida += '        <CAEFA>%s</CAEFA>\n' % cae_fecha_aut
            salida += '        <CAEFVD>%s</CAEFVD>\n' % cae_fecha_venc

        salida += '        <EsReceptor>%s</EsReceptor>\n' % es_receptor
        salida += '    </XMLEntradaNodoAdicional>\n'
        salida += '</CFEEntrada>\n'

        return salida

    def firmar_documento(self, xml_firma, tipo_cfe):
        # URL del WS y su clave en parámetros del sistema
        key_firmar = KEY_URL_TESTING
        if self.es_produccion():
            key_firmar = KEY_URL_PRODUCCION
        sys_cfg = self.env['ir.config_parameter']
        url_firmar = sys_cfg.get_param(key_firmar)
        try:
            client = Client(url_firmar)
        except:
            raise UserError(u'¡ No se pudo conectar !''\n' u'Intente más tarde.')

        try:
            sign_result = client.service.Execute(xml_firma, tipo_cfe, self.number)
            #self.sign_result = client.service.Execute(xml_firma, tipo_cfe, self.number)
            if not self.hay_error(sign_result):
                # Firmado con éxito
                self.carga_datos_firma(tipo_cfe,sign_result)
                # Generacion de QR
                if self.fe_URLParaVerificarQR:
                    # QR tamaño 1

                    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=20,border=4, )
                    qr.add_data(self.fe_URLParaVerificarQR)  # you can put here any attribute SKU in my case
                    qr.make(fit=True)
                    img = qr.make_image()
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    img_str = base64.b64encode(buffer.getvalue())
                    self.qr_img = img_str

            else:
                mensaje = self.get_error(sign_result)
                return (False, mensaje)

            _logger.error("%s", "===========================================================")
            _logger.error("%s", xml_firma)
            _logger.error("%s", "===========================================================")
            _logger.error("%s", sign_result)
            _logger.error("%s", "===========================================================")
        except WebFault:
            print("===================================================")
            print("ERROR: No se pudo consumir el WS de firmar")
            print("===================================================")
            raise UserError(u'¡ Error al intentar firmar !''\n' u'La firma electrónica no se realizó.')
            # except WebFault, detalle:



        if self.hay_error(sign_result):
            mensaje = self.get_error(sign_result)
            return (False, mensaje)
        else:
            # Firmado con éxito
            return (True, '')

    def hay_error(self, sign_result):
        xml_out = sign_result['Outxmlsalida']
        xml_root = et.fromstring(xml_out)
        xml_ns = '{com.esignit.fe}'
        return (sign_result['Errornum'] != 0 or xml_root.findtext(xml_ns + 'MensajeError') != '')

    def get_error(self, sign_result):
        xml_out = sign_result['Outxmlsalida']
        xml_root = et.fromstring(xml_out)
        xml_ns = '{com.esignit.fe}'
        return xml_root.findtext(xml_ns + 'MensajeError')

    def carga_datos_firma(self, tipo_doc, sign_result):
        xml_out = sign_result['Outxmlsalida']
        xml_root = et.fromstring(xml_out)
        xml_ns = '{com.esignit.fe}'
        self.fe_TipoCFE = tipo_doc
        self.fe_Serie = xml_root.findtext(xml_ns + 'Serie')
        self.fe_DocNro = int(xml_root.findtext(xml_ns + 'DocNro'))
        self.fe_FechaHoraFirma = xml_root.findtext(xml_ns + 'FechaHoraFirma')
        self.fe_Hash = xml_root.findtext(xml_ns + 'Hash')
        self.fe_Estado = xml_root.findtext(xml_ns + 'Estado')
        self.fe_URLParaVerificarQR = xml_root.findtext(xml_ns + 'URLParaVerificarQR')
        self.fe_URLParaVerificarTexto = xml_root.findtext(xml_ns + 'URLParaVerificarTexto')
        self.fe_CAEDNro = int(xml_root.findtext(xml_ns + 'CAEDNro'))
        self.fe_CAEHNro = int(xml_root.findtext(xml_ns + 'CAEHNro'))
        self.fe_CAENA = xml_root.findtext(xml_ns + 'CAENA')
        self.fe_CAEFA = xml_root.findtext(xml_ns + 'CAEFA')
        self.fe_CAEFVD = xml_root.findtext(xml_ns + 'CAEFVD')


account_invoice()
