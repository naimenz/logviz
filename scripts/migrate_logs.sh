#!/bin/bash
# Script to migrate jsonl log files into the database

# two command-line args: one for the directory of log files, another for the port
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <log_directory> <port>"
    exit 1
fi

dir=$1
port=$2

if [ ! -d "$dir" ]; then
    echo "Error: $dir is not a directory"
    exit 1
fi

for file in $dir/*.log; do
    echo "Uploading $file"
    curl -X POST -F "port=$port" -F "files[]=@$file" http://localhost:$port/api/upload
done
for file in $dir/*.jsonl; do
    echo "Uploading $file"
    curl -X POST -F "port=$port" -F "files[]=@$file" http://localhost:$port/api/upload
done
