from setuptools import setup

setup(
    name="chai-persistence",
    packages=["chai_persistence"],
    version="0.1.0",
    description="Implement polling to store values from downstream (Netatmo API) retrieval.",
    author="Kim Bauters",
    author_email="kim.bauters@bristol.ac.uk",
    license="Protected",
    install_requires=["pendulum",  # handle datetime instances with ease
                      "pause",  # convenient sleeping based on target times
                      "click",  # easy decorator style command line interface
                      "pg8000",  # pure Python PostgreSQL database adapter
                      "sqlalchemy",  # SQL database ORM solution
                      "tomli",  # TOML configuration file parser
                      # "chai_data_sources",
                      ],
)
