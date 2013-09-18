#This file is part magento_stock module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.pool import Pool
from .shop import *

def register():
    Pool.register(
        SaleShop,
        module='magento_stock', type_='model')
