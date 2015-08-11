# This file is part magento_stock module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from magento import *
import datetime
import logging

__all__ = ['SaleShop']
__metaclass__ = PoolMeta

logger = logging.getLogger(__name__)


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
            if not user:
                logger.info(
                    'Magento %s. Add a user in shop configuration.' % (self.name))
                return
            context = User._get_preferences(user, context_only=True)
        context['shop'] = self.id # force current shop

        with Transaction().set_context(context):
            quantities = self.get_esale_product_quantity(products)

        with Inventory(app.uri, app.username, app.password) as inventory_api:
            for product in products:
                if not product.code:
                    message = 'Magento. Error export product ID %s. ' \
                            'Add a code' % (product.id)
                    logger.error(message)
                    continue
                code = '%s ' % product.code # force a space - sku int/str
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
                    logger.info(message)
                try:
                    inventory_api.update(code, data)
                    message = '%s. Export stock %s - %s' % (
                        self.name, code, data.get('qty')
                        )
                    logger.info(message)
                except:
                    message = '%s. Error export stock %s - %s' % (
                        self.name, code, data
                        )
                    logger.error(message)

    def export_stocks_magento(self, tpls=[]):
        """Export Stocks to Magento
        :param tpls: list of product.template ids
        """
        pool = Pool()
        Prod = pool.get('product.product')
        User = pool.get('res.user')

        product_domain = Prod.magento_product_domain([self.id])

        context = Transaction().context
        if not context.get('shop'): # reload context when run cron user
            user = self.get_shop_user()
            if not user:
                logger.info(
                    'Magento %s. Add a user in shop configuration.' % (self.name))
                return
            context = User._get_preferences(user, context_only=True)
        context['shop'] = self.id # force current shop

        with Transaction().set_context(context):
            if tpls:
                product_domain += [('template.id', 'in', tpls)]
            else:
                now = datetime.datetime.now()
                last_stocks = self.esale_last_stocks

                products = self.get_product_from_move_and_date(last_stocks)

                product_domain += [['OR',
                            ('create_date', '>=', last_stocks),
                            ('write_date', '>=', last_stocks),
                            ('template.create_date', '>=', last_stocks),
                            ('template.write_date', '>=', last_stocks),
                            ('id', 'in', [p.id for p in products]),
                        ]]

                # Update date last import
                self.write([self], {'esale_last_stocks': now})
                Transaction().cursor.commit()

        products = Prod.search(product_domain)

        if not products:
            logger.info(
                'Magento. Not products to export stock.')
            return

        logger.info(
            'Magento %s. Start export stock %s products.' % (
                self.name, len(products)))

        self.sync_stock_magento(products)
        Transaction().cursor.commit()

        logger.info(
            'Magento %s. End export stocks %s products.' % (
                self.name, len(products)))

    def export_stocks_kit_magento(self, prods=[]):
        '''
        Export Stocks Product Kit to Magento (All Product Kits)
        :param prods: list
        '''
        pool = Pool()
        Product = pool.get('product.product')

        product_domain = Product.magento_product_domain([self.id])
        product_domain.append(('kit', '=', True))

        if prods:
            products = Product.browse(prods)
        else:
            products = Product.search(product_domain)

        if not products:
            return

        logger.info(
            'Magento %s. Start export stocks kit %s products.' % (
                self.name, len(products)))

        self.sync_stock_magento(products)
        Transaction().cursor.commit()

        logger.info(
            'Magento %s. End export stocks kit %s products.' % (
                self.name, len(products)))
