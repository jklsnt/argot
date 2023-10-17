#!/usr/bin/env bash

createdb argot
psql argot -f up.sql
