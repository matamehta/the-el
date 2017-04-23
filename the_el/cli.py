import json
import csv
import sys
import os

import click
from sqlalchemy import create_engine
from jsontableschema_sql import Storage
from smart_open import smart_open

from .postgres import copy_from

@click.group()
def main():
    pass

def get_connection_string(connection_string):
    connection_string = os.getenv('CONNECTION_STRING', connection_string)
    if connection_string == None:
        raise Exception('`CONNECTION_STRING` environment variable or `--connection-string` option required')
    return connection_string

def create_storage_adaptor(connection_string, db_schema, geometry_support):
    engine = create_engine(connection_string)
    storage = Storage(engine, dbschema=db_schema, geometry_support=geometry_support, views=True)
    return engine, storage

def fopen(file, mode='r'):
    if file == None:
        if mode == 'r':
            return sys.stdin
        elif mode == 'w':
            return sys.stdout
    else:
        return smart_open(file, mode=mode)

def get_table_schema(table_schema_path):
    with fopen(table_schema_path) as file:
        return json.load(file)

@main.command()
@click.argument('table_name')
@click.option('--connection-string')
@click.option('-o','--output-file')
@click.option('--db-schema')
@click.option('--geometry-support')
def describe_table(table_name, connection_string, output_file, db_schema, geometry_support):
    connection_string = get_connection_string(connection_string)

    engine, storage = create_storage_adaptor(connection_string, db_schema, geometry_support)
    descriptor = storage.describe(table_name)

    with fopen(output_file, 'w') as file:
        json.dump(descriptor, file)

@main.command()
@click.argument('table_name')
@click.argument('table_schema_path')
@click.option('--connection-string')
@click.option('--db-schema')
@click.option('--indexes-fields')
@click.option('--geometry-support')
def create_table(table_name, table_schema_path, connection_string, db_schema, indexes_fields, geometry_support):
    connection_string = get_connection_string(connection_string)

    engine, storage = create_storage_adaptor(connection_string, db_schema, geometry_support)

    table_schema = get_table_schema(table_schema_path)

    if indexes_fields != None:
        indexes_fields = indexes_fields.split(',')

    storage.create(table_name, table_schema, indexes_fields=indexes_fields)

@main.command()
@click.argument('table_name')
@click.option('--table-schema-path')
@click.option('--connection-string')
@click.option('-f','--input-file')
@click.option('--db-schema')
@click.option('--geometry-support')
@click.option('--skip-headers', is_flag=True)
def write(table_name,
          table_schema_path,
          connection_string,
          input_file,
          db_schema,
          geometry_support,
          skip_headers):
    connection_string = get_connection_string(connection_string)

    table_schema = get_table_schema(table_schema_path)

    engine, storage = create_storage_adaptor(connection_string, db_schema, geometry_support)

    if table_schema_path != None:
        table_schema = get_table_schema(table_schema_path)
        storage.describe(table_name, descriptor=table_schema)

    ## TODO: csv settings? use Frictionless Data csv standard?
    ## TODO: support line delimted json?
    with fopen(input_file) as file:
        rows = csv.reader(file)
        if skip_headers:
            next(rows)

        if engine.dialect.driver == 'psycopg2':
            copy_from(engine, table_name, table_schema, rows)
        else:
            storage.write(table_name, rows)

@main.command()
@click.argument('table_name')
@click.option('--connection-string')
@click.option('-o','--output-file')
@click.option('--db-schema')
@click.option('--geometry-support')
def read(table_name, connection_string, output_file, db_schema, geometry_support):
    connection_string = get_connection_string(connection_string)

    engine, storage = create_storage_adaptor(connection_string, db_schema, geometry_support)

    ## TODO: csv settings? use Frictionless Data csv standard?
    ## TODO: support line delimted json?
    with fopen(output_file, mode='w') as file:
        writer = csv.writer(file)

        descriptor = storage.describe(table_name)
        fields = map(lambda x: x['name'], descriptor['fields'])
        writer.writerow(fields)

        for row in storage.iter(table_name):
            writer.writerow(row)
