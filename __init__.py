from trytond.pool import Pool

from .padron_afip import *

def register():
    Pool.register(
        PadronAfip,
        PadronAfipStart,
        module='padron_afip_ar', type_='model')
    Pool.register(
        PadronAfipImport,
        module='padron_afip_ar', type_='wizard')
