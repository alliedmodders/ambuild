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
objcopy --only-keep-debug $LD_FILE $LD_FILE.dbg
if [ $? -ne 0 ]; then
	exit $?
fi
objcopy --strip-debug $LD_FILE
if [ $? -ne 0 ]; then
	exit $?
fi
objcopy --add-gnu-debuglink=$LD_FILE.dbg $LD_FILE
if [ $? -ne 0 ]; then
	exit $?
fi
