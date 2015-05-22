# This file is part magento_stock module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
import datetime
import logging

from magento import *

__all__ = ['SaleShop']
__metaclass__ = PoolMeta


class SaleShop:
    __name__ = 'sale.shop'

    def sync_stock_magento(self, products):
        '''Sync Stock Magento'''
        pool = Pool()
        User = pool.get('res.user')

        app = self.magento_website.magento_app

        context = Transaction().context
        if not context.get('shop'): # reload context when run cron user
            user = self.get_shop_user()
            context = User._get_preferences(user, context_only=True)
        context['shop'] = self.id # force current shop

        with Transaction().set_context(context):
            quantities = self.get_esale_product_quantity(products)

        with Inventory(app.uri, app.username, app.password) as inventory_api:
            for product in products:
                code = product.code
                qty = quantities[product.id]

                is_in_stock = '0'
                if qty > 0:
                    is_in_stock = '1'

                manage_stock = '0'
                if product.esale_manage_stock:
                    manage_stock = '1'

                data = { 
                    'qty': qty,
                    'is_in_stock': is_in_stock,
                    'manage_stock': manage_stock
                    }
                if hasattr(product, 'sale_min_qty'):
                    if product.sale_min_qty:
                        data['min_sale_qty'] = product.sale_min_qty
                        data['use_config_min_sale_qty'] = '0'
                    else:
                        data['min_sale_qty'] = 1
                        data['use_config_min_sale_qty'] = '1'
                if hasattr(product, 'max_sale_qty'):
                    if product.max_sale_qty:
                        data['max_sale_qty'] = product.max_sale_qty
                        data['use_config_min_sale_qty'] = '0'
                    else:
                        data['max_sale_qty'] = 1
                        data['use_config_min_sale_qty'] = '1'

                if app.debug:
                    message = 'Magento %s. Product: %s. Data: %s' % (
                            self.name, code, data)
                    logging.getLogger('magento').info(message)
                try:
                    inventory_api.update(product.code, data)
                    message = '%s. Export stock %s - %s' % (
                        self.name, code, data.get('qty')
                        )
                    logging.getLogger('magento').info(message)
                except:
                    message = '%s. Error export stock %s - %s' % (
                        self.name, code, data
                        )
                    logging.getLogger('magento').error(message)

    def export_stocks_magento(self, tpls=[]):
        """Export Stocks to Magento
        :param tpls: list of product.template ids
        """
        pool = Pool()
        Template = pool.get('product.template')

        if tpls:
            templates = []
            for t in Template.browse(tpls):
                shops = [s.id for s in t.shops]
                if t.esale_available and self.id in shops:
                    templates.append(t)
        else:
            now = datetime.datetime.now()
            last_stocks = self.esale_last_stocks

            products = self.get_product_from_move_and_date(last_stocks)
            tpls = [product.template for product in products]
            templates = list(set(tpls))

            # Update date last import
            self.write([self], {'esale_last_stocks': now})

        if not templates:
            logging.getLogger('magento').info(
                'Magento. Not products to export stock.')
            return

        products = [product for template in templates for product in template.products]

        logging.getLogger('magento').info(
            'Magento %s. Start export stock %s products.' % (
                self.name, len(products)))

        self.sync_stock_magento(products)
        Transaction().cursor.commit()

        logging.getLogger('magento').info(
            'Magento %s. End export stocks %s products.' % (
                self.name, len(products)))
