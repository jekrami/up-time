#!/bin/bash

ls *.log > list.txt

for i in {21..200}

do
  ip="192.168.155.$i"
  ipline="$ip ->"
  while read f; do

	if grep -Fxq $ip $f
	then
	 ipline=$ipline"O"
	else
	 ipline=$ipline"."
	fi
  done <list.txt
echo $ipline 

done
