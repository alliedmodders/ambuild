#!/bin/bash

if [ $# -lt 3 ]; then
	echo "Usage: <file> <linker> <...linker args>";
	exit 1;
fi

LD_FILE=$1
LD_EXEC=$2

shift;
shift;

$LD_EXEC $@
if [ $? -ne 0 ]; then
	exit $?
fi
dsymutil $LD_FILE
if [ $? -ne 0 ]; then
	exit $?
fi
strip -S $LD_FILE
if [ $? -ne 0 ]; then
	exit $?
fi

