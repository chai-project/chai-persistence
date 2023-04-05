# pylint: disable=line-too-long, missing-module-docstring
# pylint: disable=loop-invariant-statement, loop-global-usage, singleton-comparison

import logging
import os
import sys
from threading import Thread
from typing import Dict

import click
import tomli
from pause import sleep
from sqlalchemy import and_
from sqlalchemy.orm import aliased, Session, sessionmaker, scoped_session

from chai_persistence.db_definitions import db_session, db_engine, Home, Configuration as DBConfiguration
from chai_persistence.home_interface import HomeInterface

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

# get all the current homes (and periodically check for changes)
# store home instances so that they can be used for automated logging

# for every participant:
#   log the temperature for both valve and thermostat
#   log the valve open status as a percentage


class Configuration:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """ Configuration used by the API server. """
    client_id: str = ""
    client_secret: str = ""
    db_server: str = "127.0.0.1"
    db_name: str = "chai"
    db_username: str = ""
    db_password: str = ""
    debug: bool = False

    def __str__(self):
        return (f"Configuration(client_id={self.client_id}, client_secret={self.client_secret}, "
                f"db_server={self.db_server}, db_name={self.db_name}, "
                f"db_username={self.db_username}, db_password={self.db_password}, "
                f"db_debug={self.debug})")


@click.command()
@click.option("--config", default=None, help="The TOML configuration file.")
@click.option("--client_id", default=None, help="The client ID for accessing the Netatmo API.")
@click.option("--client_secret", default=None, help="The file containing the (single line) secret of the client ID.")
@click.option("--dbserver", default=None, help="The server location of the PostgreSQL database, defaults to 127.0.0.1.")
@click.option("--db", default=None, help="The name of the database to access, defaults to chai.")
@click.option("--username", default=None, help="The username to access the database.")
@click.option("--dbpass_file", default=None, help="The file containing the (single line) password for database access.")
@click.option('--debug', is_flag=True, help="Provides debug output for the database when present.")
def cli(config, client_id, client_secret, dbserver, db, username, dbpass_file, debug):  # pylint: disable=invalid-name
    settings = Configuration()

    if config and not os.path.isfile(config):
        click.echo("The configuration file is not found. Please provide a valid file path.")
        sys.exit(0)

    if config:
        with open(config, "rb") as file:
            try:
                toml = tomli.load(file)

                if toml_netatmo := toml["netatmo"]:
                    settings.client_id = str(toml_netatmo.get("id", settings.client_id))
                    settings.client_secret = str(toml_netatmo.get("secret", settings.client_secret))

                if toml_db := toml["database"]:
                    settings.db_server = str(toml_db.get("server", settings.db_server))
                    settings.db_name = str(toml_db.get("name", settings.db_name))
                    settings.db_username = str(toml_db.get("user", settings.db_username))
                    settings.db_password = str(toml_db.get("pass", settings.db_password))
                    settings.debug = bool(toml_db.get("debug", settings.debug))
            except tomli.TOMLDecodeError:
                click.echo("The configuration file is not valid and cannot be parsed.")
                sys.exit(0)

    # some entries may not be present in the TOML file, or they may be overridden by explicit CLI arguments

    # [overriden/supplemental Netatmo settings]
    if client_id is not None:
        settings.client_id = client_id

    # verify that the client secret file exists
    if client_secret and not os.path.isfile(client_secret):
        click.echo("Client secret file not found. Please provide a valid file path.")
        sys.exit(0)

    if client_secret:
        # use the contents of the file as the client secret
        with open(client_secret, encoding="utf-8") as file:
            secret = file.read().strip()
            settings.client_secret = secret

    # [overridden/supplemental database settings]
    if dbserver is not None:
        settings.db_server = dbserver

    if db is not None:
        settings.db_name = db

    if username is not None:
        settings.db_username = username

    # verify that the password file exists
    if dbpass_file and not os.path.isfile(dbpass_file):
        click.echo("Password file not found. Please provide a valid file path.")
        sys.exit(0)

    if dbpass_file:
        # use the contents of the file as the bearer token
        with open(dbpass_file, encoding="utf-8") as file:
            password = file.read().strip()
            settings.db_password = password

    if debug is True:
        settings.debug = True

    main(settings)


def main(settings: Configuration):
    # start the thread that will repeatedly check for changes to the homes in the database
    #  and is responsible for spawning the required child threads to handle the polling of each Netatmo device
    thread = Thread(target=run, args=(settings, 1 * 60 * 60), daemon=False, name="homes refresh")
    print("starting main thread")
    thread.start()


def run(settings: Configuration, sleep_duration: int):
    db_config = DBConfiguration(username=settings.db_username, password=settings.db_password,
                                server=settings.db_server, database=settings.db_name,
                                enable_debugging=settings.debug)

    engine = db_engine(db_config)
    session_factory = sessionmaker(bind=engine)
    st_session: scoped_session = scoped_session(session_factory)
    home_interfaces: Dict[HomeInterface] = {}

    while True:
        print("  checking homes for any changes")

        # retrieve all homes, and only the most recent revision of each home
        session: Session
        with db_session(st_session) as session:
            home_alias = aliased(Home)
            homes = session.query(
                Home
            ).outerjoin(
                home_alias, and_(Home.label == home_alias.label, Home.revision < home_alias.revision)
            ).filter(
                home_alias.revision == None  # noqa: E711
            ).all()

            for home in homes:
                if home.label in home_interfaces:
                    db_id, h_i = home_interfaces[home.label]  # get the home interface we currently have
                    if home.id != db_id:  # if the id changed for the home with this label we need ...
                        h_i.stop()  # ... stop it's background threads and ...
                        del home_interfaces[home.label]  # ... remove its reference
                if home.label not in home_interfaces:
                    print(f"   -starting polling of the home with the label '{home.label}'")
                    h_i = HomeInterface(home_db_id=home.id, st_session=st_session,
                                        netatmo_refresh_token=home.relay.refreshToken,
                                        client_id=settings.client_id, client_secret=settings.client_secret)
                    home_interfaces[home.label] = (home.id, h_i)
            print(f"  started/refreshed all home polling threads")
            print()

        sleep(sleep_duration)


if __name__ == "__main__":
    cli()
