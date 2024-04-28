#! /usr/bin/bash

files=(
  'conf/twitter.cookies'
  'conf/users.json'
  'log/tweets.json'
  'log/twitter.log'
)

for file in "${files[@]}"; do
  touch "${file}"
  chmod 666 "${file}"
done
