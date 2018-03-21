# This file is part magento_stock module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from io import BytesIO
from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.tools import grouped_slice
from trytond.config import config as config_
from magento import *
import datetime
import unicodecsv
import logging

__all__ = ['SaleShop']

MAX_CONNECTIONS = config_.getint('magento', 'max_connections', default=50)
logger = logging.getLogger(__name__)


class SaleShop:
    __metaclass__ = PoolMeta
    __name__ = 'sale.shop'
    magento_use_config_manage_stock = fields.Boolean(
        'Magento Use Config Manage Stock',
        help=('If check this value, when export product stock add '
            'use_config_manage_stock option'))

    def _get_magento_inventory(self, product, qty):
        '''Get Magento Inventory data'''
        is_in_stock = '0'
        if qty > 0:
            is_in_stock = '1'

        manage_stock = '0'
        if product.esale_manage_stock:
            manage_stock = '1'

        data = {}
        data['qty'] = qty
        data['is_in_stock'] = is_in_stock
        data['manage_stock'] = manage_stock
        if self.magento_use_config_manage_stock:
            data['use_config_manage_stock'] = ('1'
                if product.magento_use_config_manage_stock else '0')
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
        return data

    def magento_inventory(self, products, sync='api'):
        'Magento Inventory'
        User = Pool().get('res.user')

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

        inventories = []
        for product in products:
            if not product.code:
                message = ('Magento. '
                    'Not found code in product ID %s.' % (product.id))
                logger.error(message)
                continue

            # force a space when sync to Mgn Api - sku int/str
            code = ('%s ' % product.code) if sync == 'api' else product.code
            qty = quantities[product.id]
            data = self._get_magento_inventory(product, qty)
            if app.debug:
                message = 'Magento %s. Product: %s. Data: %s' % (
                        self.name, code, data)
                logger.info(message)
            inventories.append([code, data]) # save in inventories list

        return inventories

    def sync_stock_magento(self, products):
        'Sync Stock Magento'
        app = self.magento_website.magento_app
        inventories = self.magento_inventory(products, sync='api')

        for inventory_group in grouped_slice(inventories, MAX_CONNECTIONS):
            inventory_data = [i for i in inventory_group]
            with Inventory(app.uri, app.username, app.password) as inventory_api:
                try:
                    inventory_api.update_multi(inventory_data)
                    message = '%s. Export group stock %s' % (
                        self.name, len(inventory_data)
                        )
                    logger.info(message)
                except Exception as e:
                    message = '%s. Error export group stock %s' % (
                        self.name, len(inventory_data)
                        )
                    logger.error(message)
                    logger.error(e)

    def export_stocks_magento(self, tpls=[]):
        'Export Stocks to Magento'
        pool = Pool()
        Prod = pool.get('product.product')
        User = pool.get('res.user')

        product_domain = Prod.magento_product_domain([self.id])
        product_domain += [('esale_active', '=', True)]

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
                if self.esale_product_move_stocks:
                    product_domain += [['OR',
                                ('create_date', '>=', last_stocks),
                                ('write_date', '>=', last_stocks),
                                ('template.create_date', '>=', last_stocks),
                                ('template.write_date', '>=', last_stocks),
                                ('id', 'in', [p.id for p in products]),
                            ]]
                else:
                    product_domain = [('id', 'in', [p.id for p in products])]

                # Update date last import
                self.write([self], {'esale_last_stocks': now})
                Transaction().commit()

        products = Prod.search(product_domain)

        if not products:
            logger.info(
                'Magento. Not products to export stock.')
            return

        logger.info(
            'Magento %s. Start export stock %s products.' % (
                self.name, len(products)))

        self.sync_stock_magento(products)
        Transaction().commit()

        logger.info(
            'Magento %s. End export stocks %s products.' % (
                self.name, len(products)))

    def export_stocks_kit_magento(self, prods=[]):
        'Export Stocks Product Kit to Magento (All Product Kits)'
        Product = Pool().get('product.product')

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
        Transaction().commit()

        logger.info(
            'Magento %s. End export stocks kit %s products.' % (
                self.name, len(products)))

    def esale_export_stock_csv_magento(self, products):
        'eSale Export Stock CSV Magento'
        inventories = self.magento_inventory(products, sync='csv')

        values, keys = [], set()
        for inventory in inventories:
            # inventory is a tuple (code, vals)
            vals = inventory[1]
            vals['sku'] = inventory[0]
            for k in vals.keys():
                keys.add(k)
            values.append(vals)

        output = BytesIO()
        wr = unicodecsv.DictWriter(output, sorted(list(keys)),
            quoting=unicodecsv.QUOTE_ALL, encoding='utf-8')
        wr.writeheader()
        wr.writerows(values)
        return output
