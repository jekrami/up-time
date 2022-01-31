#!/bin/bash
#------------> By J.Ekrami @ 98-06-02
cd /home/ekrami/logs
alan=`date '+%Y-%m-%d'`;
filename="logs.$alan.tar.gz"
tar -cvzf $filename . --remove-files
cd ..
mv logs/$filename logs.bkup/.
