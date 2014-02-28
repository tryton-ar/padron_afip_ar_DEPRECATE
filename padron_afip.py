#! -*- coding: utf8 -*-
"Herramienta para procesar y consultar el Padrón Unico de Contribuyentes AFIP"

# Documentación e información adicional:
#    http://www.sistemasagiles.com.ar/trac/wiki/PadronContribuyentesAFIP
# Basado en pyafipws padron.py de Mariano Reingart

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, Button, StateTransition
import urllib2
import os
#import shelve
#import sqlite3
import zipfile
from email.utils import formatdate

# Tipos de datos (código RG1361)

N = 'Numerico'      # 2
A = 'Alfanumerico'  # 3
I = 'Importe'       # 4
C = A               # 1 (caracter alfabetico)
B = A               # 9 (blanco)

# formato y ubicación archivo completo de la condición tributaria según RG 1817
FORMATO = [
    ("cuit", 11, N, ""),
    ("denominacion", 30, A, ""),
    ("imp_ganancias", 2, A,	"'NI', 'AC','EX', 'NC'"),
    ("imp_iva", 2, A, "'NI' , 'AC','EX','NA','XN','AN'"),
    ("monotributo", 2, A, "'NI', 'Codigo categoria tributaria'"),
    ("integrante_soc", 1, A, "'N' , 'S'"),
    ("empleador", 1, A, "'N', 'S'"),
    ("actividad_monotributo", 2, A, ""),
    ]


__all__ = ['PadronAfip', 'PadronAfipStart', 'PadronAfipImport']

class PadronAfip(ModelSQL, ModelView):
    "padron.afip"
    __name__ = "padron.afip"

    denominacion = fields.Char('denominacion')
    imp_ganancias = fields.Char('imp_ganancias')
    imp_iva = fields.Char('imp_iva')
    monotributo = fields.Char('monotributo')
    integrante_soc = fields.Char('integrante_soc')
    empleador = fields.Char('empleador')
    actividad_monotributo = fields.Char('actividad_monotributo')
    cuit = fields.Char('CUIT')

class PadronAfipStart(ModelView):
    "padron afip start"
    __name__ = "padron.afip.import.start"

class PadronAfipImport(Wizard):
    "padron afip wizard import"
    __name__ = "padron.afip.import"

    start = StateView('padron.afip.import.start', 'padron_afip_ar.padron_afip_import_form', [
        Button('Cancel','end', 'tryton-cancel'),
        Button('Import', 'download_import', 'tryton-ok', default=True)
        ])
    download_import = StateTransition()

    def transition_download_import(self):
        url = "http://www.afip.gob.ar/genericos/cInscripcion/archivos/apellidoNombreDenominacion.zip"
        self._descargar(url)
        self._procesar()
        return 'end'

    def _descargar(self, url, filename="padron.txt", proxy=None):
        #import sys
        #from utils import leer, escribir, N, A, I, get_install_dir
        "Descarga el archivo de AFIP, devuelve 200 o 304 si no fue modificado"
        proxies = {}
        if proxy:
            proxies['http'] = proxy
            proxies['https'] = proxy
        print "Abriendo URL %s ..." % url
        req = urllib2.Request(url)
        if os.path.exists(filename):
            http_date = formatdate(timeval=os.path.getmtime(filename),
                                   localtime=False, usegmt=True)
            req.add_header('If-Modified-Since', http_date)
        try:
            web = urllib2.urlopen(req)
        except urllib2.HTTPError, e:
            if e.code == 304:
                print "No modificado desde", http_date
                return 304
            else:
                raise
        # leer info del request:
        meta = web.info()
        lenght = float(meta['Content-Length'])
        tmp = open(filename + ".zip", "wb")
        print "Guardando"
        size = 0
        p0 = None
        while True:
            p = int(size / lenght * 100)
            if p0 is None or p>p0:
                print "Descargando ... %0d %%" % p
                p0 = p
            data = web.read(1024*100)
            size = size + len(data)
            if not data:
                print "Descarga Terminada!"
                break
            tmp.write(data)
        print "Abriendo ZIP..."
        tmp.close()
        web.close()
        uf = open(filename + ".zip", "rb")
        zf = zipfile.ZipFile(uf)
        for fn in zf.namelist():
            print "descomprimiendo", fn
            tf = open(filename, "wb")
            tf.write(zf.read(fn))
            tf.close()
        return 200

    def _procesar(self, filename="padron.txt"):
        "Analiza y crea la base de datos interna sqlite para consultas"
        PadronAfip = Pool().get('padron.afip')

        f = open(filename, "r")
        keys = [k for k, l, t, d in FORMATO]
        # conversion a planilla csv (no usado)
        if False and not os.path.exists("padron.csv"):
            csvfile = open('padron.csv', 'wb')
            import csv
            wr = csv.writer(csvfile, delimiter=',',
                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for i, l in enumerate(f):
                if i % 100000 == 0:
                    print "Progreso: %d registros" % i
                r = self._leer(l, FORMATO)
                row = [r[k] for k in keys]
                wr.writerow(row)
            csvfile.close()
        f.seek(0)
        for i, l in enumerate(f):
            if i % 10000 == 0: print i
            registro = self._leer(l, FORMATO)
            registro['cuit'] = str(registro['cuit'])
            PadronAfip.create([registro])

    def _leer(self, linea, formato, expandir_fechas=False):
        "Analiza una linea de texto dado un formato, devuelve un diccionario"
        dic = {}
        comienzo = 1
        for fmt in formato:
            clave, longitud, tipo = fmt[0:3]
            dec = (len(fmt)>3 and isinstance(fmt[3], int)) and fmt[3] or 2
            valor = linea[comienzo-1:comienzo-1+longitud].strip()
            try:
                if chr(8) in valor or chr(127) in valor or chr(255) in valor:
                    valor = None        # nulo
                elif tipo == N:
                    if valor:
                        valor = long(valor)
                    else:
                        valor = 0
                elif tipo == I:
                    if valor:
                        try:
                            if '.' in valor:
                                    valor = float(valor)
                            else:
                                valor = valor.strip(" ")
                                valor = float(("%%s.%%0%sd" % dec) % (long(valor[:-dec] or '0'), int(valor[-dec:] or '0')))
                        except ValueError:
                            raise ValueError("Campo invalido: %s = '%s'" % (clave, valor))
                    else:
                        valor = 0.00
                elif expandir_fechas and clave.lower().startswith("fec") and longitud <= 8:
                    if valor:
                        valor = "%s-%s-%s" % (valor[0:4], valor[4:6], valor[6:8])
                    else:
                        valor = None
                else:
                    valor = valor.decode("ascii","ignore")
                dic[clave] = valor
                comienzo += longitud
            except Exception, e:
                raise ValueError("Error al leer campo %s pos %s val '%s': %s" % (
                    clave, comienzo, valor, str(e)))
        return dic
