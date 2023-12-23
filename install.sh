#!/usr/bin/env bash

createdb argot -U postgres
psql argot -f up.sql -U postgres
