#This file is part magento_stock module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

import datetime
import logging
import threading

from magento import *

__all__ = ['SaleShop']
__metaclass__ = PoolMeta


class SaleShop:
    __name__ = 'sale.shop'

    def export_stocks_magento(self, tpls=[]):
        """Export Stocks to Magento
        :param shop: object
        :param tpls: list
        """
        pool = Pool()
        Template = pool.get('product.template')

        if tpls:
            templates = []
            for t in Template.browse(tpls):
                shops = [s.id for s in t.esale_saleshops]
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
        else:
            logging.getLogger('magento').info(
                'Magento. Start export stock %s products.' % (len(templates)))

            user = self.get_shop_user(self)

            db_name = Transaction().cursor.dbname
            thread1 = threading.Thread(target=self.export_stock_magento_thread, 
                args=(db_name, user.id, self.id, templates,))
            thread1.start()

    def export_stock_magento_thread(self, db_name, user, sale_shop, templates):
        """Export product stock to Magento APP
        :param db_name: str
        :param user: int
        :param sale_shop: int
        :param templates: list
        """

        with Transaction().start(db_name, user):
            pool = Pool()
            SaleShop = pool.get('sale.shop')
            Template = pool.get('product.template')

            shop, = SaleShop.browse([sale_shop])
            app = shop.magento_website.magento_app

            with Inventory(app.uri, app.username, app.password) as inventory_api:
                for template in Template.browse(templates):
                    products = [product for product in template.products if product.code]
                    quantities = self.get_esale_product_quantity(products)
                    
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

                        if hasattr(template, 'sale_min_qty'):
                            if template.sale_min_qty:
                                data['min_sale_qty'] = template.sale_min_qty
                                data['use_config_min_sale_qty'] = '0'
                            else:
                                data['min_sale_qty'] = 1
                                data['use_config_min_sale_qty'] = '1'
                        if hasattr(template, 'max_sale_qty'):
                            if template.max_sale_qty:
                                data['max_sale_qty'] = template.max_sale_qty
                                data['use_config_min_sale_qty'] = '0'
                            else:
                                data['max_sale_qty'] = 1
                                data['use_config_min_sale_qty'] = '1'

                        if app.debug:
                            message = 'Magento %s. Product: %s. Data: %s' % (
                                    shop.name, code, data)
                            logging.getLogger('magento').info(message)
                        try:
                            inventory_api.update(product.code, data)
                            message = '%s. Export stock %s - %s' % (
                                shop.name, code, data.get('qty')
                                )
                            logging.getLogger('esale stock').info(message)
                        except:
                            message = '%s. Error export stock %s - %s' % (
                                shop.name, code, data
                                )
                            logging.getLogger('esale stock').error(message)

            Transaction().cursor.commit()
            logging.getLogger('magento').info(
                'Magento %s. End export stocks %s products.' % (
                    shop.name, len(templates)))
