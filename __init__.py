from trytond.pool import Pool

from .padron_afip import *

def register():
    Pool.register(
        PadronAfip,
        PadronAfipStart,
        module='padron-afip-ar', type_='model')
    Pool.register(
        PadronAfipImport,
        module='padron-afip-ar', type_='wizard')
