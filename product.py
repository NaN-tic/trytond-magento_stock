# This file is part magento_stock module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['Template']


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    magento_use_config_manage_stock = fields.Boolean(
        'Magento Use Config Manage Stock',
        help=('If check this value, when export product stock add true in '
            'use_config_manage_stock option'))
