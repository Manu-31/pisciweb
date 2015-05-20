#!/bin/bash
#
#--------------------------------------------------------------------------------
#   En cours d'integration dans pisciweb.py
#   Ce qui est note OBSOLETE est integre ...
#--------------------------------------------------------------------------------
# Usage
#   templog.sh create
#      creation de la base de donnees
#   templog.sh graph
#      generation d'un graphe
#   templog.sh read
#      consultation de la base de donnes
#   templog.sh periodique
#      enregistrement d'une mesure a chaque pas de temps
#   templog.sh log   (OBSOLETE)
#      enregistrement d'une mesure unique
#   templog.sh test
#      affichage d'une mesure prise directement (pas de log)
#   templog.sh archive
#      archivage de la base
#   templog.sh allumer_pompe   (OBSOLETE)
#      ...
#   templog.sh eteindre_pompe   (OBSOLETE)
#      ...
#
# Par defaut
#   templog.sh    (OBSOLETE)
#      log 
#
#--------------------------------------------------------------------------------
# Utilisation envisagée
#
# Les trois lignes suivantes dans la crontab permettent d'echantilloner toutes
# minutes (pour la premiere) de generer un graphique tous les huitiemes d'heure
# pour la seconde et de sauvegarder la base (4ko en l'etat) tous les jours.
#
# *   *    *    *    *     /home/pi/pisciweb/templog.sh  (OBSOLETE)
# 0-59/15  *    *    *    *     /home/pi/pisciweb/templog.sh graph
# 1   0    *    *    *     /home/pi/pisciweb/templog.sh archive
# 0   9    *    *    *     /home/pi/pisciweb/templog.sh allumer_pompe
# 0  19    *    *    *     /home/pi/pisciweb/templog.sh eteindre_pompe
#--------------------------------------------------------------------------------
# V-O.4 - Gestion de la pompe (via gpio)
# V-0.3 - Operationnelle
# V-0.2 - Premiere version experimentale
# V-0.1 - On se contente de faire des mesures. Pas encore teste !
#    pour le moment, les "rrdtool fetch aquarium.rdd AVERAGE --start -3600" ne donnent rien !
#--------------------------------------------------------------------------------
# A faire :
#   daemoniser ? ([ -z "$FORK" ] && { FORK=1 $0 "$@" & exit; })
#   mieux gerer les options !!
#--------------------------------------------------------------------------------

# Les identifiants et noms des deux sondes
SONDE1=28-0000037ae572
NOM1="Eau piscine"

SONDE2=28-0000037b14c5  #28-0000037ade5d2
NOM2="Local pompe"

# Identifiant de la pompe
PIN_POMPE=12

# Parametres generaux
# La période entre deux mesures. Attention, par defaut rrdtool prend
# des intervalles de 300 secondes. IL faut donc faire plus pour etre
# certain d'avoir un echantillon
REPERTOIRE=/home/pi/pisciweb
PERIODE_MESURE=60
PNGFILE=${REPERTOIRE}/static/tempiscine.png
LOGFILE=${REPERTOIRE}/raspiscine.log

# Temperatures extremes (attention, ces valeurs limitent aussi les
# enregistrements)
TEMP_MIN=-10.0
TEMP_MAX=45.0
DEBUG=FALSE

# Parametres du systeme 1-wire
FACT=1000.0
W1_BASEDIR=/sys/bus/w1/devices/

# La version fondee sur owfs
OWFSDIR=/mnt

# Parametres rrdtool
# Le fichier (sans extension rrd)
RRD_BASENAME=tempiscine
# La durée minimale entre deux mesures (unknown audelà)
RRD_HEARTBEAT=$(echo "scale=2; 2*$PERIODE_MESURE" | bc)

RRD_FILE=${REPERTOIRE}/${RRD_BASENAME}.rrd

# Paramtres gpio
GPIO=/usr/bin/gpio
GPIO_ARRET=0
GPIO_MARCHE=1

# Generation d'une entree dans le logfile
log () {
   d=`date`
   echo "[$d] $1" >> $LOGFILE
}

# Allumage de la pompe
allumer_pompe () {
   log "Allumage de la pompe"
   $GPIO -1 write $PIN_POMPE $GPIO_MARCHE
}

# Extinction de la pompe
eteindre_pompe () {
   log "Extinction de la pompe"
   $GPIO -1 write $PIN_POMPE $GPIO_ARRET
}

# La fonction de mesure de temperature
#    Parametre : l'identifiant de la sonde
#    result    : la temperature en deg C
grab_temp () {
   # Version 1wire
   if [ -f  $W1_BASEDIR/$1/w1_slave ] ; then
      RE=`cat $W1_BASEDIR/$1/w1_slave | grep "t="|cut -d= -f2`
      result=$(echo "scale=2; $RE/$FACT" | bc)
   else 
      result=U
   fi
   
   #version owfs
   #result=`cat ${OWFSDIR}/$1/temperature|sed -e "s/ //g"`
}


# La fonction de log d'une mesure unique (par capteur)
echantilloner () {
   # On enregistre les mesures actuelles
   grab_temp $SONDE1 ; T1=$result
   grab_temp $SONDE2 ; T2=$result

   # Etat de la pompe
   POMPE=`$GPIO -1 read $PIN_POMPE`

   N=`date +%s`
   if [ "$DEBUG" == "TRUE" ] ; then
      echo Sampling ${N}:${T1}:${T2}:${POMPE}
   fi
   rrdtool update ${RRD_FILE} ${N}:${T1}:${T2}:${POMPE}
}

# Generation d'un graph
tracer () {
  # log "Generation d'un graphe"
   rrdtool graph ${PNGFILE} --vertical-label "Temperature (deg C)" \
     --width 800 --height 200 \
     --end now \
     --start end-86400s \
     --lower-limit $TEMP_MIN --upper-limit $TEMP_MAX --rigid \
     --color BACK#FFFFFF   \
     --color CANVAS#ffe50b \
     DEF:Temp1=${RRD_FILE}:Temp1:AVERAGE \
     CDEF:huitieme=Temp1,8,/           \
     DEF:Temp2=${RRD_FILE}:Temp2:AVERAGE \
     DEF:Pompe=${RRD_FILE}:Pompe:AVERAGE \
     AREA:$TEMP_MIN#3398ff \
     AREA:0#3398ff \
     STACK:huitieme#49a2ff \
     STACK:huitieme#5fadff \
     STACK:huitieme#71b6ff \
     STACK:huitieme#83c0ff \
     STACK:huitieme#8dc5ff \
     STACK:huitieme#97caff \
     STACK:huitieme#b0d6ff \
     STACK:huitieme#c9e3ff \
     CDEF:lp=Pompe,0.5,LT,$TEMP_MAX,0.9,*,$TEMP_MIN,IF  \
     CDEF:ppline=Pompe,0.5,LT,0,55,IF \
     LINE0:lp#202020 \
     AREA:ppline#10901040:"Filtration active":STACK \
     LINE1:Temp1#0000FF:"$NOM1" \
     LINE2:Temp2#FF0000:"$NOM2" \
#     CDEF:froid=Temp1,14,LT,Temp1,0,IF \
#    AREA:froid#0000FF40:"Trop froid !" \

#     CDEF:lp=Pompe,0.5,LT,0,$TEMP_MAX,0.6,*,IF  \
#     CDEF:ppline=Pompe,0.5,LT,0,10.0,IF \
#     AREA:ppline#b2eb78:"Filtration active":STACK \
# Pour un fond gris quand la pompe tourne
#     CDEF:pmh=Pompe,0.5,LT,0,$TEMP_MAX,IF \
#     CDEF:pml=Pompe,0.5,LT,0,$TEMP_MIN,IF \
#     AREA:pml#E0E0E0 \
#     AREA:pmh#E0E0E0:"Filtration active" \
}

# Sauvegarde de la base
archiver () {
   log "Archivage de la base"
   N=`date +%F`
   cp ${RRD_FILE} ${REPERTOIRE}/${RRD_BASENAME}-${N}.rrd
}

# Creation de la base de donnees
if [ "$1" == "create" ] ; then
   log "Creation de la base"
   echo "Creation de la base (on sauvegarde la precedente)"
   mv ${RRD_FILE} ${RRD_FILE}.old
   rrdtool create ${RRD_FILE} \
      DS:Temp1:GAUGE:${RRD_HEARTBEAT}:${TEMP_MIN}:${TEMP_MAX} \
      DS:Temp2:GAUGE:${RRD_HEARTBEAT}:${TEMP_MIN}:${TEMP_MAX} \
      DS:Pompe:GAUGE:${RRD_HEARTBEAT}:0:1 \
      RRA:AVERAGE:0.5:1:288
   exit
fi

# Consultation de la base
if [ "$1" == "read" ] ; then
   echo Consultation hors nan
   rrdtool fetch ${RRD_FILE} AVERAGE| grep -v nan
   exit
fi

# Echantillonage
if [ "$1" == "log" ] ; then
   echo "Enregistrement d'une valeur"
   echantilloner
   exit
fi

if [ "$1" == "graph" ] ; then
   echo "Creation d'un graphe"
   tracer
   exit
fi

if [ "$1" == "allumer_pompe" ] ; then
   echo "Allumage de la pompe"
   allumer_pompe
   exit
fi

if [ "$1" == "eteindre_pompe" ] ; then
   echo "Extinction de la pompe"
   eteindre_pompe
   exit
fi

# Si on veut un script qui tourne en permanence (plutot qu'un cron)
if [ "$1" == "periodique" ] ; then
   while ( true) ; do 
      echantilloner

      # On attend pour la prochaine tournee
      sleep ${PERIODE_MESURE}
   done
fi

if [ "$1" == "test" ] ; then
   log "Test"
   grab_temp $SONDE1 ; T1=$result
   grab_temp $SONDE2 ; T2=$result
   echo $NOM1=$T1
   echo $NOM2=$T2
 exit   
fi

if [ "$1" == "archive" ] ; then
   archiver
   exit
fi

if [ $# != 0 ] ; then
   echo "Parametre inconnu"
   exit
fi

# Comportement par defaut : on log
echantilloner
