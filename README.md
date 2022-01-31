# up-time
 How to get Network devices up-time charts with MRTG?


As a test and an educational issue for our young colleagues I did this simple two lines code and worked very well.

I did this in a multi vlan network as well as flat network and code works there too.

- First I needed to “SEE” my devices and I used ping to get values but it took too much time to ping a range (in multi vlan 10’s of ranges) I tested and found fping more practical , so I wrote this simple commands :


#!bin/bash

for i in 100 {121..129} 131 140 151

do

alan=`date '+%Y-%m-%d_%H-%M-%S'`;

filename="$alan[$i].log"

<<<<<<< HEAD
// fping -agsq 192.168.$i.0/24 -r 0 > logs/$filename ;

fping -agsq 192.168.$i.0/24 > logs/$filename ;
=======
fping -agsq 192.168.$i.0/24 -r 0 > logs/$filename ;
>>>>>>> 7986aa3273e29dc6cca8c021afe39cc55965dc7d

cp logs/$filename last[$i].log

done


The -r 0 option in slow devices causes me to not get a response in time , but make commands very fast. I removed it for having all pingable devices, losing some seconds.

Then I forwarded results to a text file ( for each vlan) keeping originals with time tags on them.

Then I put the code in a scheduled task for every 15 minutes.

- I noticed that MRTG needs four values to draw a chart:

- first value to draw first line ( for example download value)

- second value to draw second line (in another color) for example Upload value

- 3’rd is first value legend

- 4’th is second value legend


-getlast.sh counts the ping-able devices and return results :


#!/bin/bash


echo `cat last[$1].log | wc -l`

echo "0"

echo "$1"

echo "$2"


- and run these code with another scheduled command but not in shell , in MRTG cfg file:


In my example p100.cfg is for 100 vlan, that is used as an example for Servers:


Title[p100]: Servers

PageTop[p100]: <H1>Servers</H1>

Target[p100]: `/path/to/file/getlast.sh 100 Servers`

MaxBytes[p100]: 200

LegendI[p100]: Range 100

LegendO[p100]: *

YLegend[p100]: Count

Legend1[p100]: Range 100

Legend2[p100]: **


-as you know mrtg can runs in a scheduled command like this:


*/5 * * * * env LANG=C /usr/bin/mrtg /etc/mrtg/p100.cfg


-I did this for all vlans and put them in this way:

each vlan in a single cfg file and run mrtg with a single mrtg.cfg file as follows:


WorkDir: /var/www/html/mrtg

Options[_]: growright, pngdate, gauge, nopercent

XSize[_]: 500

YSize[_]: 200

EnableIPv6: no

RunAsDaemon: no

PageFoot[^]: Page managed by J.Ekrami

Include: /etc/mrtg/p100.cfg

Include: /etc/mrtg/p121.cfg

Include: /etc/mrtg/p122.cfg

.

.

.


Include: /etc/mrtg/p180.cfg



-The results are very simple but also very useful. Who can leave the pc “ON” after work hours!!:)



