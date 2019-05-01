#!/usr/bin/env bash
docker build . -t remarker:$(git describe --tag)