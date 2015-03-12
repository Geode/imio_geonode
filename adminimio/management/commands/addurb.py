# -*- coding: utf8 -*-
from django.core.management.base import BaseCommand, CommandError

from optparse import OptionParser
from optparse import make_option
from geoserver.catalog import Catalog
from uuid import uuid4
from decimal import *
from django.core.management import call_command
import time

from geonode.layers.models import Layer

class Command(BaseCommand):

    args = 'params'
    help = 'Collect layer from Database'
    geoserver_rest_url = 'http://localhost:8080/geoserver/rest'
    urb = {
            "capa":"Parcelles",
            "toli":"cadastre_ln_toponymiques",
            "canu":"cadastre_pt_num",
            "cabu":"Batiments",
            "gept":"cadastre_points_generaux",
            "gepn":"cadastre_pol_gen",
            "inpt":"point",
            "geli":"cadastre_ln_generales",
            "inli":"cadastre_ln_informations",
            "topt":"point",
            }

    option_list = BaseCommand.option_list + (
    make_option("-p", "--gpw",
        action='store',
        type="string",
        dest='gpw',
        default="",
        help="Geoserver admin password [default: %default]"),
    )+ (
    make_option("-u", "--urbanUrl",
        action='store',
        type="string",
        dest='urbanUrl',
        default="",
        help="Urban URL [default: %default]"),
    )+ (
    make_option("-r", "--ropw",
        action='store',
        type="string",
        dest='ropw',
        default="",
        help="Remote postGIS ro_user password [default: %default]"),
    )+ (
    make_option("-d", "--database",
        action='store',
        type="string",
        dest='database',
        default="urb_xxx",
        help="remote urban database name [default: %default]"),
    )+ (
    make_option("-a", "--alias",
        action='store',
        type="string",
        dest='alias',
        default="",
        help="prefix alias [default: %default]"),
    )+ (
    make_option("-z", "--uri",
        action='store',
        type="string",
        dest='uri',
        default="imio.be",
        help="uri= [default: %default]"),
    )+ (
    make_option("-g", "--postuser",
        action='store',
        type="string",
        dest='postuser',
        default="ro_user",
        help="db_use r= [default: %default]"),
    )+ (
    make_option("-c", "--geoserveradmin",
        action='store',
        type="string",
        dest='geoserveradmin',
        default="admin",
        help="Geoserver admin = [default: %default]"),
    )+ (
    make_option("-n", "--groupname",
        action='store',
        type="string",
        dest='groupname',
        default="",
        help="Group Name for permition = [default: %default]"),
    )

    def createDataStore(self, options):
        cat = Catalog(self.geoserver_rest_url, options['geoserveradmin'], options['gpw'])
        #create datastore for URB schema
        ws = cat.create_workspace(options['alias'],options['uri'])
        ds = cat.create_datastore(options['alias'], ws)
        ds.connection_parameters.update(
            host=options['urbanUrl'],
            port="5432",
            database=options['database'],
            user=options['postuser'],
            passwd=options['ropw'],
            dbtype="postgis")
        cat.save(ds)
        return ws.name , ds.name, ds.resource_type
    
    def addLayersToGeoserver(self, options):
        cat = Catalog(self.geoserver_rest_url, options['geoserveradmin'], options['gpw'])

        ds = cat.get_store(options['alias'])

        layers = []
        try:
            #connect to tables and create layers and correct urban styles
            print("premiere boucle")
            for table in self.urb:
                try:
                    style = self.urb[table]
                    ft = cat.publish_featuretype(table, ds, 'EPSG:31370', srs='EPSG:31370')
                    ft.default_style = style
                    cat.save(ft)
                    res_name = ft.dirty['name']
                    res_title = options['alias']+"_"+table
                    cat.save(ft)

                    layers.append({ 'res_name' : res_name, 'res_title' : res_title })
                except Exception as e:
                    print(str(e))

        except Exception as e:
            print(str(e))

        return layers

    def addLayersToGeonode(self, options, ws_name, ds_name, ds_resource_type, layers):
        for layer in layers:
            created = False

            layer, created = Layer.objects.get_or_create(name=layer['res_name'], defaults={
                "workspace": ws_name,
                "store":  ds_name,
                "storeType": ds_resource_type,
                "typename": "%s:%s" % (ws_name.encode('utf-8'), layer['res_name'].encode('utf-8')),
                "title": layer['res_title'] or 'No title provided',
                "abstract": 'No abstract provided',
                #"owner": owner,
                "uuid": str(uuid4())
                #"bbox_x0": Decimal(ft.latLonBoundingBox.miny),
                #"bbox_x1": Decimal(ft.latLonBoundingBox.maxy),
                #"bbox_y0": Decimal(ft.latLonBoundingBox.minx),
                #"bbox_y1": Decimal(ft.latLonBoundingBox.maxx)       
            })         
            if created:
                grName = unicode(options['groupname'])
                perm = {
                       u'users': {
                           u'AnonymousUser': [] },
                       u'groups': {
                           grName:[u'view_resourcebase'] }
                       }
                layer.set_permissions(perm)
                layer.save()
            else:
                print("   !!! le layer "+ layer['res_title'] +" n'as pas ete cree ... Verifier si il etait deja cree avant ?")

    def handle(self, *args, **options):
        if self.verifParams(options):
            ws_name , ds_name, ds_resource_type =  self.createDataStore(options)
            layers = self.addLayersToGeoserver(options)
            self.addLayersToGeonode(options,ws_name, ds_name,ds_resource_type, layers)

    def verifParams(self, options):
        if(options['gpw'] is None or options['gpw'] is '' or
           options['urbanUrl'] is None or options['urbanUrl'] is '' or
           options['ropw'] is None or options['ropw'] is '' or
           options['alias'] is None or options['alias'] is '' or
           options['groupname'] is None or options['groupname'] is ''):
            print('Some parameter was not define')
            return False
        else:
            return True
