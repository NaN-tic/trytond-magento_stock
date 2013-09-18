#This file is part magento_stock module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

import logging
import threading
from magento import *

__all__ = ['SaleShop']
__metaclass__ = PoolMeta


class SaleShop:
    __name__ = 'sale.shop'

    def export_stock_magento(self, shop, products):
        """Export Stock to Magento APP
        :param shop: Obj
        :param products: Obj list
        """
        prods = [product.id for product in products
                if product.code and product.template.esale_active ]

        logging.getLogger('magento stock').info(
            '%s. Export stock %s product(s).' % (
            shop.name, len(prods)
            ))

        db_name = Transaction().cursor.dbname
        thread1 = threading.Thread(target=self.export_stock_magento_thread, 
            args=(db_name, Transaction().user, shop.id, prods,))
        thread1.start()

    def export_stock_magento_thread(self, db_name, user, shop, products):
        """Export Stock to Magento APP - Thread
        :param db_name: str
        :param user: int
        :param shop: Obj
        :param products: list
        """
        with Transaction().start(db_name, user) as transaction:
            pool = Pool()
            SaleShop = pool.get('sale.shop')
            Product = pool.get('product.product')

            sale_shop = SaleShop.browse([shop])[0]
            mgnapp = sale_shop.magento_website.magento_app

            prods = Product.search([('id', 'in', products)])
            quantities = self.get_esale_product_quantity(prods)

            with Inventory(mgnapp.uri, mgnapp.username, mgnapp.password) as inventory_api:
                for product in Product.browse(products):
                    qty = quantities[product.id]
                    is_in_stock = int(qty > 0) or False
                    manage_stock = product.esale_manage_stock
                    data = { 
                        'qty': qty,
                        'is_in_stock': is_in_stock,
                        'manage_stock': manage_stock
                    }
                    try:
                        inventory_api.update(product.code, data)
                        logging.getLogger('esale stock').info(
                            '%s. Export stock %s - %s' % (
                            sale_shop.name, product.code, data
                            ))
                    except:
                        logging.getLogger('esale stock').error(
                            '%s. Export stock %s - %s' % (
                            sale_shop.name, product.code, data
                            ))

            logging.getLogger('esale stock').info(
                    '%s. End export stock' % (sale_shop.name))
