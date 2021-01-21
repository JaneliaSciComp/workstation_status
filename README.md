# workstation_status
Workstation status visualizations

# Workstation Status [![Picture](https://raw.github.com/JaneliaSciComp/JaneliaSciComp.github.com/master/images/HHMI_Janelia_Color_Alternate_180x40.png)](http://www.janelia.org)

[![Build Status](https://travis-ci.org/JaneliaSciComp/workstation_status.svg?branch=master)](https://travis-ci.org/JaneliaSciComp/workstation_status)
[![GitHub last commit](https://img.shields.io/github/last-commit/JaneliaSciComp/workstation_status.svg)](https://github.com/JaneliaSciComp/workstation_status)
[![GitHub commit merge status](https://img.shields.io/github/commit-status/badges/shields/master/5d4ab86b1b5ddfb3c4a70a70bd19932c52603b8c.svg)](https://github.com/JaneliaSciComp/workstation_status)
[![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-360/)
[![Requirements Status](https://requires.io/github/JaneliaSciComp/workstation_status/requirements.svg?branch=master)](https://requires.io/github/JaneliaSciComp/workstation_status/requirements/?branch=master)

## Summary
This repository contains the Workstation Status web application. 

## Configuration

This system depends on the [Centralized Config](https://github.com/JaneliaSciComp/Centralized_Config) system, and
will use the following configurations:
- rest_services
- servers

The location of the configuration system is in the config.cfg file as CONFIG.

To rebuild the docker container:
```
docker build --tag registry.int.janelia.org/jacs/workstation-status .
docker push registry.int.janelia.org/jacs/workstation-status
```

## Deployment

Take the following steps to start the system:
```
cd /opt/flask/workstation_status
docker-compose -f docker-compose-prod.yml up -d
```

## Author Information
Written by Rob Svirskas (<svirskasr@janelia.hhmi.org>)

[Scientific Computing](http://www.janelia.org/research-resources/computing-resources)  
