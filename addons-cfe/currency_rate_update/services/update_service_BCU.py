# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (c) 2017 Datamatic. All rights reserved.
#    @author Roberto Garcés
#
#    Abstract class to fetch rates from Banco Central del Uruguay
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from suds.client import Client
import ssl

from .currency_getter_interface import CurrencyGetterInterface
from odoo.exceptions import UserError, ValidationError

from datetime import datetime
from lxml import etree

import logging
_logger = logging.getLogger(__name__)

# para que funcione con python 2.7.9+
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

_logger = logging.getLogger(__name__)
import ipdb

codigo_ISO_BCU = {
    'AUD': 105,
    'ARS': 501,
    'BRL': 1001,
    'EUR': 1111,
    'CLF': 1300, 'NZD': 1490, 'ZAR': 1620, 'DKK': 1800,
    'USD': 2225,     # se toma de la tabla de cotizaciones interbancarias, en UYU
    'CAD': 2309, 'GBP': 2700, 'JPY': 3600, 'PEN': 4000,
    'CNY': 4150, 'MNX': 4200, 'HUF': 4300, 'TRY': 4400,
    'NOK': 4600, 'PYG': 4800, 'ISK': 4900, 'HKD': 5100,
    'KRW': 5300, 'RUB': 5400, 'COP': 5500, 'MYR': 5600,
    'INR': 5700, 'SEK': 5800, 'CHF': 5900, 'VEF': 6200,
    'UYI': 9800, 'UYR': 9900,
    'CLP': 1300,
}

codigo_BCU_ISO = {
    105: 'AUD',
    501: 'ARS',     # se toma de la tabla de cotizaciones interbancarias, en UYU
    1001: 'BRL',     # se toma de la tabla de cotizaciones interbancarias, en UYU
    1111: 'EUR',
    1300: 'CLP', 1490: 'NZD', 1620: 'ZAR', 1800: 'DKK',
    2225: 'USD',     # se toma de la tabla de cotizaciones interbancarias, en UYU
    2309: 'CAD', 2700: 'GBP', 3600: 'JPY', 4000: 'PEN',
    4150: 'CNY', 4200: 'MXN', 4300: 'HUF', 4400: 'TRY',
    4600: 'NOK', 4800: 'PYG', 4900: 'ISK', 5100: 'HKD',
    5300: 'KRW', 5400: 'RUB', 5500: 'COP', 5600: 'MYR',
    5700: 'INR', 5800: 'SEK', 5900: 'CHF', 6200: 'VEF',
    9800: 'UYI', 9900: 'UYR',
}


class BCU_getter(CurrencyGetterInterface):
    code = 'BCU'
    name = 'Uruguayan Central Bank'

    """Implementation of Currency_getter_factory interface
    for BCU service
    """
    def _get_rate_date (self):
        """Obtención de la fecha de cierre (la válida) para la cotización
        :return: fecha en formato aaaa-mm-dd
        """
        url = 'https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsultimocierre?WSDL'
        client = Client(url)
        try:
            result = client.service.Execute()
            fecha = result['Fecha']
        except:
            _logger.error(client)
        return fecha

    def _get_currency_list(self, currency_array):
        """A partir de la la lista de códigos ISO de las monedas crea una lista de códigos de monedas en el formato
        esperado por el servicio awsbcucotizaciones
        """
        lista = []
        for currency in currency_array:
            if currency in codigo_ISO_BCU:
                lista.append(codigo_ISO_BCU.get(currency))
            else:
                print('no esta %s' % currency)
                raise ValidationError('orror')
        return lista

    def _get_rates_from_result(self, result):
        dict = {}
        for item in result['datoscotizaciones']['datoscotizaciones.dato']:
            iso = codigo_BCU_ISO.get(item['Moneda'])
            dict[iso] = 1.0/item['TCC']
        return dict

    def get_updated_currency(self, currency_array, main_currency_name, max_delta_days):
        """implementation of abstract method of curreny_getter_interface"""
        self.validate_cur(main_currency_name)

        fecha = self._get_rate_date()
        try:
            url = 'https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcucotizaciones?WSDL'
            client = Client(url)
            request = client.factory.create('wsbcucotizacionesin')
            array = client.factory.create('ArrayOfint')
            array.item = self._get_currency_list(currency_array)
            request.Moneda = array
            request.FechaDesde = fecha
            request.FechaHasta = fecha
            request.Grupo = 0
            result = client.service.Execute(request)
            rates = self._get_rates_from_result(result)

            if main_currency_name in currency_array:
                currency_array.remove(main_currency_name)

            for curr in currency_array:
                self.validate_cur(curr)
                self.updated_currency[curr] = rates.get(curr)
        except:
            _logger.error(result)
        return self.updated_currency, self.log_info
