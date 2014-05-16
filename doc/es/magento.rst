#:before:magento/magento:section:exportacion_de_precios_de_productos#

.. inheritref:: magento/magento:section:exportacion_de_stock_de_productos

Exportación de stock de productos
=================================

A la tienda dispone de las opciones para la exportación de stock a Magento. Mediante
el botón "Exportar stocks" exportará todos los productos a partir de la fecha de creación
que contenga un movimiento del albarán de salida o entrada. Esta acción obtendrá todos los productos
con la condición:

* Disponible en eSale
* El producto esté disponible en la tienda
* La fecha de creación del movimiento sea mayor que la que especificamos

También en los productos dispone de un asistente para seleccionar productos y exportar
sólo estos productos a la tienda que seleccione en el asistente (pasarán a posterior
una verificación que estén disponibles al eSale y a la tienda que hemos seleccionado).

Los stocks a exportar consiste en enviar a Magento la cantidad disponible que tenemos en el almacén
en cualquier ubicación interna que tengamos dado de alta a las Ubicaciones de logística.

Si disponemos marcada la opción en el producto "Gestiona stock", a parte d'enviar la cantidad
que disponemos (stock), también publicaremos a Magento que este producto se debe gestionar el stock a Magento.
