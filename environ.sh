#!/bin/bash

# 3-fingered-claw 
function yell () 
{ 
  echo "$0: $*" >&2
}

function die () 
{ 
  yell "$*"; exit 1
}

function try () 
{ 
  "$@" || die "cannot $*" 
}

# Default to foss toolchain
if [[ "$1" == "foss" || -z $1 ]];
then
    toolchain=foss
elif [[ "$1" == "intel" ]];
then
    toolchain=intel
fi
echo "Toolchain: $toolchain"
# Clean slate
try module purge

# Testing/Coverage requirements
case $toolchain in
  "foss")
      try module load IMAS-AL-Python/5.3.0-foss-2023b-DD-3.42.0
      try module load coverage/7.4.4-GCCcore-13.2.0
    ;;
  "intel")
      try module load IMAS-AL-Python/5.3.0-intel-2023b-DD-3.42.0
      # only in foss, but it works anyway:
      try module load coverage/7.4.4-GCCcore-13.2.0
    ;;
   *)
    echo "Unknown toolchain $toolchain"
    ;;
esac
try module -t list 2>&1 | sort

export HOME=$PWD
echo "HOME was set to $HOME"
