from setuptools import setup

setup(
    name="chai-persistence",
    packages=["chai-persistence"],
    version="0.1.0",
    description="Log and handle requests from upstream, and implement polling to store values from downstream.",
    author="Kim Bauters",
    author_email="kim.bauters@bristol.ac.uk",
    license="Protected",
    install_requires=["pendulum",  # handle datetime instances with ease
                      "sqlalchemy",  # SQL database ORM solution
                      "pause",  # convenient sleeping based on target times
                      # chai_data_sources
                      ],
)
