# -*- coding: utf-8 -*-
from odoo import models, fields, api
import ipdb

def uy_ci_verif(ci):
    verif, *ci_num = map(int, filter(lambda x: 47 < ord(x) < 58, reversed(ci)))
    # XXX maybe we should support other lenghts
    if 6 > len(ci_num) or len(ci_num) > 7:
        raise ValueError("wrong lenght")
    # TODO replace magic by function
    magic = (4, 3, 6, 7, 8, 9, 2)
    return verif == -sum((x * y for x, y in zip(magic, ci_num))) % 10

def uy_rut_verif(rut):
    verif, _, _, _, *rut_num = map(int, filter(lambda x: 47 < ord(x) < 58, reversed(rut)))
    if len(rut_num) != 8:
        raise ValueError("wrong lenght")
    def magic():
        while True:
            for i in range(2, 10):
                yield i
    return verif == -sum((x * y for x, y in zip(magic(), rut_num))) % 11

class res_partner(models.Model):
    _inherit = 'res.partner'



    def _upper_vat(self):
        for partner in self:
            if partner.vat and partner.vat_type != '2':
                return True
            else:
                vat_country = partner.vat[:2]
                if not vat_country.isupper():
                    return False
        return True


    def valid_ci_uy(self, ci):
        '''
        Valid Uruguayan CI number.
        '''
        # Only digits
        try:
            int(ci)
        except:
            return False

        ci = str(ci)
        ci = ci.rjust(8,"0")

        if ( len(ci) > 8 ):
            return False

        check_digit = 0
        base = "2987634"
        for i in range(0,7):
            check_digit += int(ci[i]) * int(base[i])

        check_digit %= 10
        check_digit  = 10 - check_digit
        if ( check_digit == 10 ):
            check_digit = 0

        if ( check_digit == int(ci[7]) ):
            return True
        else:
            return False


    def valid_vat_uy(self, vat):
        '''
        Valid Uruguayan VAT number (RUT).
        '''
        # Only digits
        try:
            int(vat)
        except:
            return False

        # Long enough
        if ( len(vat) != 12 ):
            return False

        # VAT[] * Base[]
        check_digit = 0
        base = "43298765432"
        for i in range(0,11):
            check_digit += int(vat[i]) * int(base[i])

        # Module 11
        check_digit %= 11
        check_digit  = 11 - check_digit

        # Mistakes ?
        if ( check_digit == 10 ):
            return False
        else:
            if ( check_digit == 11 ): check_digit = 0
            if ( check_digit != int(vat[11]) ):
                return False

        # We are here, so ...
        return True


    def check_vat_uy(self, vat):
        # ipdb.set_trace()
        '''
        Check Uruguayan VAT number (RUT).
        '''
        # Si es un contacto no validamos
        if self.is_company and self.parent_id:
            return True
        # One or another ...
        #Si tiene codigo 2 es rut y debe ser Uruguay
        if self.vat_type and self.vat_type == '2' and self.country_id.code != 'UY':
            raise Warning('Para tipo de documento RUT el Cliente debe tener como pais Uruguay')
        #Si tiene codigo 3 es CI Y debe ser Uruguay
        if self.vat_type and self.vat_type == '3' and self.country_id.code != 'UY':
            raise Warning('Para tipo de documento Cedula de Identidad el Cliente debe tener como pais Uruguay')
        #Si es otros no puede ser uguauya
        if self.vat_type and self.vat_type == '4' and self.country_id.code == 'UY':
            raise Warning('Para tipo de documento Otros el cliente no puede tener como pais Uruguay')

        #Checkeamos la cedula
        if self.vat_type and self.vat_type == '3' and self.country_id.code == 'UY':
            if not self.valid_ci_uy(vat):
                raise Warning('Número de cedula incorrecto')
            return self.valid_ci_uy(vat)

        #Checkeamos el RUT
        if self.vat_type and self.vat_type == '2' and self.country_id.code == 'UY':
            return self.valid_vat_uy(vat)





    # _constraints = [(_upper_vat, "VAT country must be uppercase", ["vat"])]