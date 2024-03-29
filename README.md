# Workstation Status [![Picture](https://raw.github.com/janelia-flyem/janelia-flyem.github.com/master/images/HHMI_Janelia_Color_Alternate_180x40.png)](http://www.janelia.org)

[![GitHub last commit](https://img.shields.io/github/last-commit/JaneliaSciComp/workstation_status.svg)](https://github.com/JaneliaSciComp/workstation_status)
[![GitHub commit merge status](https://img.shields.io/github/commit-status/badges/shields/master/5d4ab86b1b5ddfb3c4a70a70bd19932c52603b8c.svg)](https://github.com/JaneliaSciComp/workstation_status)

[![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![nginx](https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white)](https://www.nginx.com/)
[![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/en/2.2.x/)

## Summary
This repository contains the Workstation Status web application. 

This system uses MySQL, gunicorn and nginx, and depends on docker and docker-compose
to run.

To run on production:

    sh restart_prod.sh
   
## Dependencies

1. This code depends on the [configurator](https://github.com/JaneliaSciComp/configurator). It should be active at the URL set in REST_SERVICES in api/config.cfg.

## Installation

1. Update nginx.conf or nginx-dev.conf as appropriate to reflect the correct hostname.
2. Run the application using restart_prod.sh or restart_dev.sh as appropriate.
3. The API is now available at `http://your-hostname/`. Opening this url in your browser will bring up the API documentation.


Rob Svirskas (<svirskasr@janelia.hhmi.org>)

[Scientific Computing](http://www.janelia.org/research-resources/computing-resources)
