#--------------------------------------------------------
#   pisciweb : petite interface avec ma piscine.
#
#   A Faire
#     . option archiver pour se debarasser de templog.sh
#     . configuration du repertoire de stockage des rrd
#
#   Fait
#     . comment visualiser sur le log les actions en ligne
#     de commande ? => 1.8 on fork un tail ...
#--------------------------------------------------------
from flask import Flask, url_for, render_template, redirect, Response
import glob
import time
import datetime
import os
try:
   import RPi.GPIO as gpio
except ImportError:
   print "*** Fallback to FAKE GPIO ..."
   import FakeRPi.GPIO as gpio
import argparse
import sys
import rrdtool
import ConfigParser
import logging
import json

app = Flask(__name__)

#--------------------------------------------------------
# Generalites
#--------------------------------------------------------
pisciWebVersion  = "1.11" # ajout de pages pour acceder depuis
                          # domoweb. WARNING : unsafe !
#pisciWebVersion = "1.10" # ajout d'un /temperature
#pisciWebVersion = "1.9"
#pisciWebVersion = "1.8"  # Utilisation de FakeRPi pour tests
                          # Utilisation de ConfigParser
                          # Utilisation de logging
#pisciWebVersion = "1.7"  # Ajout de options -R -r -L -l
#pisciWebVersion = "1.6"  # Normalisation des etats marche/arret
#pisciWebVersion = "1.5"  # Ajout de 3  interfaces
#pisciWebVersion = "1.4"  # Utilisation de rrdtool pour loguer
#pisciWebVersion = "1.3"  # introduction de la gestion des arguments
#pisciWebVersion = "1.2"  # Ajout d'un mode debug
#pisciWebVersion = "1.1"  # Ajout d'une desactivation
#pisciWebVersion = "1.0"  # Premiere version operationnelle

repertoire = "/home/pi/pisciweb"

rrd_filename = "tempiscine.rrd"

rrd_file = repertoire + "/" + rrd_filename

#--------------------------------------------------------
# Pour pouvoir logguer sur une page web
# (from https://gist.github.com/jhorneman/3181165)
#--------------------------------------------------------
class WebPageHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.messages = []
 
    def emit(self, record):
        self.messages.append(self.format(record))
 
    def get_messages(self):
        return self.messages

log_handler = WebPageHandler()

#--------------------------------------------------------
# Logage d'un message
#--------------------------------------------------------
def logFONCTIONAVIRER(message):
   logFile=open(logFileName, "a");
   logFile.write("["+time.asctime( time.localtime(time.time()) ) + "] " + message + "\n");
   logFile.close()
   
#--------------------------------------------------------
# Le gpio
#--------------------------------------------------------

# Les pins utilisees
pinActive = 11
pinPompe = 12
pinControlepH = 13
pinActiveRobot = 15
pinRobot = 16
pinLumiere = 18

# Quelques "macros"
gpioMarche = gpio.LOW
gpioArret = gpio.HIGH

gpioPins = {
   pinActive : {
      'nom'  : 'Activation Pompe',
      'etat' : gpioMarche
   },   
   pinPompe : {
      'nom'  : 'Filtration',
      'etat' : gpioArret
   },   
   pinControlepH : {
      'nom' : 'Controle pH',
      'etat' : gpioArret
   },
   pinActiveRobot : {
      'nom'  : 'Activation Robot',
      'etat' : gpioMarche
   },   
   pinRobot : {
      'nom'  : 'Robot',
      'etat' : gpioArret
   },   
   pinLumiere : {
      'nom' : 'Eclairage',
      'etat' : gpioArret
   }
}

#========================================================
# Divers helper
#========================================================
def tail(f, n):
  stdin,stdout = os.popen2("tail -n " + str(n) + " "+f)
  stdin.close()
  lines = stdout.readlines(); stdout.close()
  return lines

#========================================================
# Gestion de rrdtool
#========================================================
def echantillonner():
   t_e = str(temperature_eau())
   t_l = str(temperature_local())
   ps = str(1-gpio.input(pinPompe)) # Le "1-" est la car actif=low
   N = str(int(time.time())) 
   #print rrd_file + " : " + N+":"+t_e+":"+t_l+":"+ps
   #logging.debug("Echantillonnage dans " +  rrd_file + " : " + N+":"+t_e+":"+t_l+":"+ps)
   rrdtool.update(rrd_file, N+":"+t_e+":"+t_l+":"+ps)

#========================================================
# Gestion du gpio
#========================================================
#--------------------------------------------------------
# Initialisation du systeme
#    w : Activation des warnings ?
#--------------------------------------------------------
def gpioInit(w=True):
   gpio.setwarnings(w) 
   gpio.setmode(gpio.BOARD)
   for pin in gpioPins:
      gpio.setup(pin, gpio.OUT)
   
#--------------------------------------------------------
# Lecture de l'etat des commandes
#--------------------------------------------------------
def lireEtatCommandes():
   for pin in gpioPins:
      gpioPins[pin]['etat'] = gpio.input(pin)

#--------------------------------------------------------
# Lecture de la temperature d'une sonde
#--------------------------------------------------------
def read_temp_raw(device_file):
   f = open(device_file, 'r')
   lines = f.readlines()
   f.close()
   return lines
 
def read_temp(device_file):
   lines = read_temp_raw(device_file)
   while lines[0].strip()[-3:] != 'YES':
      time.sleep(0.2)
      lines = read_temp_raw(device_file)
   equals_pos = lines[1].find('t=')
   if equals_pos != -1:
      temp_string = lines[1][equals_pos+2:]
      temp_c = float(temp_string) / 1000.0
      return temp_c

#--------------------------------------------------------
# Temperature de l'eau
#--------------------------------------------------------
def temperature_eau():
   return read_temp(device_file_eau)

#--------------------------------------------------------
# Temperature du local
#--------------------------------------------------------
def temperature_local():
   return read_temp(device_file_local)

#--------------------------------------------------------
# Mise en marche de la pompe
#--------------------------------------------------------
def filtration_start(via="erreur"):
   gpio.output(pinPompe, gpioMarche)
   logger.info("Allumage de la pompe (" + via + ")")

#--------------------------------------------------------
# Extinction de la pompe
#--------------------------------------------------------
def filtration_stop(via="erreur"):
   gpio.output(pinPompe, gpioArret)
   logger.info("Extinction de la pompe (" + via + ")")

#--------------------------------------------------------
# Mise en marche du ph
#--------------------------------------------------------
def ph_start(via="erreur"):
   gpio.output(pinControlepH, gpioMarche)
   logger.info("Allumage du controle pH (" + via + ")")

#--------------------------------------------------------
# Extinction du controle pH
#--------------------------------------------------------
def ph_stop(via="erreur"):
   gpio.output(pinControlepH, gpioArret)
   logger.info("Extinction du controle pH (" + via + ")")

#--------------------------------------------------------
# Mise en marche du robot
#--------------------------------------------------------
def robot_start(via="erreur"):
   gpio.output(pinRobot, gpioMarche)
   logger.info("Allumage du robot (" + via + ")")

#--------------------------------------------------------
# Extinction du robot
#--------------------------------------------------------
def robot_stop(via="erreur"):
   gpio.output(pinRobot, gpioArret)
   logger.info("Extinction du robot (" + via + ")")

#--------------------------------------------------------
# Mise en marche de l'eclairage
#--------------------------------------------------------
def eclairage_start(via="erreur"):
   gpio.output(pinLumiere, gpioMarche)
   logger.info("Allumage de l'eclairage (" + via + ")")

#--------------------------------------------------------
# Extinction de l'eclairage
#--------------------------------------------------------
def eclairage_stop(via="erreur"):
   gpio.output(pinLumiere, gpioArret)
   logger.info("Extinction de l'eclairage (" + via + ")")


#========================================================
# Gestion de l'interface web
#========================================================

#--------------------------------------------------------
# La page de debogage
#--------------------------------------------------------
@app.route("/debogage")
def debogage():
   message = "Etat du systeme"
   # For each pin, read the pin state and store it in the pins dictionary:
   for pin in gpioPins:
      gpioPins[pin]['state'] = gpio.input(pin)

   # Along with the pin dictionary, put the message into the template data dictionary:
   templateData = {
      'message' : message,
      'gpioPins' : gpioPins
   }

   return render_template('debogage.html', **templateData)

@app.route("/<changePin>/<action>")
def action(changePin, action):
   # Convert the pin from the URL into an integer:
   changePin = int(changePin)
   # Get the device name for the pin being changed:
   deviceName = gpioPins[changePin]['nom']
   # If the action part of the URL is "high," execute the code indented below:
   if action == "high":
      # Set the pin high:
      gpio.output(changePin, gpio.HIGH)
      # Save the status message to be passed into the template:
      message = "Turned " + deviceName + " high."
   if action == "low":
      gpio.output(changePin, gpio.LOW)
      message = "Turned " + deviceName + " low."
   if action == "toggle":
      # Read the pin and set it to whatever it isn't (that is, toggle it):
      gpio.output(changePin, not gpio.input(changePin))
      message = "Toggled " + deviceName + "."

   # For each pin, read the pin state and store it in the pins dictionary:
   for pin in gpioPins:
      gpioPins[pin]['etat'] = gpio.input(pin)

   logger.info(message)
   # Along with the pin dictionary, put the message into the template data dictionary:
   templateData = {
      'message' : message,
      'gpioPins' : gpioPins
   }

   return redirect('/debogage')

#--------------------------------------------------------
# Une page pour la temperature
#--------------------------------------------------------
@app.route("/temperature")
def getTemp():
   return Response(json.dumps(temperature_eau()),mimetype='application/json')

#--------------------------------------------------------
# Une page pour la temperature de l'air
#--------------------------------------------------------
@app.route("/temperature_air")
def getTempAir():
   return Response(json.dumps(temperature_local()),mimetype='application/json')

#--------------------------------------------------------
# Une page pour l'etat de la lumiere
#--------------------------------------------------------
@app.route("/light")
def getLightStatus():
   return Response(json.dumps(1-gpioPins[pinLumiere]['etat']),mimetype='application/json')

#--------------------------------------------------------
# Une page pour l'etat de la pompe
#--------------------------------------------------------
@app.route("/pump")
def getPumpStatus():
   return Response(json.dumps(1-gpioPins[pinPompe]['etat']),mimetype='application/json')

#--------------------------------------------------------
# Une page pour l'etat du pHmetre
#--------------------------------------------------------
@app.route("/ph")
def getPhStatus():
   return Response(json.dumps(1-gpioPins[pinControlepH]['etat']),mimetype='application/json')

#--------------------------------------------------------
# Une page pour l'etat du robot
#--------------------------------------------------------
@app.route("/robot")
def getRobotStatus():
   return Response(json.dumps(1-gpioPins[pinRobot]['etat']),mimetype='application/json')

#--------------------------------------------------------
# La page principale
#--------------------------------------------------------
@app.route("/")
def accueil():
   print("Acces a la racine\n")
   lireEtatCommandes()
   print("Commandes lues\n")
   templateData = {
      'title' : 'Bienvenue dans la piscine Chaput !',
      'date' : datetime.date.today().strftime("%a %d %b %y"),
      'activation' : gpioPins[pinActive]['etat'],
      'etatPompe' : gpioPins[pinPompe]['etat'],
      'etatEclairage' : gpioPins[pinLumiere]['etat'],
      'etatControlepH' : gpioPins[pinControlepH]['etat'],
      'gpioMarche' : gpioMarche,
      'tempEau': round(temperature_eau(), 1),
      'pisciWebVersion': pisciWebVersion
   }
   print("Rendu en cours \n")
   return render_template(htmlMain, **templateData)

#--------------------------------------------------------
# Affichage des logs 
#--------------------------------------------------------
@app.route("/historique")
def historique():
   templateData = {
      'title' : 'Bienvenue dans la piscine Chaput !',
      'date' : datetime.date.today().strftime("%a %d %b %y"),
      'activation' : gpioPins[pinActive]['etat'],
      'etatPompe' : gpioPins[pinPompe]['etat'],
      'etatEclairage' : gpioPins[pinLumiere]['etat'],
      'etatControlepH' : gpioPins[pinControlepH]['etat'],
      'gpioMarche' : gpioMarche,
      'tempEau': round(temperature_eau(), 1),
      'pisciWebVersion': pisciWebVersion
   }
   if (logUseFile) :
      templateData['messages'] = tail(logFileName, logMaxLength)
   else :
      messages = []
      for message in log_handler.get_messages()  :
         messages.append(message) 
      templateData['messages'] = messages
   return render_template('historique.html', **templateData)

#--------------------------------------------------------
#
#--------------------------------------------------------
@app.route("/configuration")
def configuration():
   return accueil()

#--------------------------------------------------------
# Les divers marche/arret
#--------------------------------------------------------
@app.route("/pompe_marche")
def pompe_marche():
   filtration_start("web")
   return redirect('/')

@app.route("/pompe_arret")
def pompe_arret():
   filtration_stop("web")
   return redirect('/')

@app.route("/controleph_marche")
def controleph_marche():
   ph_start("web")
   return redirect('/')

@app.route("/controleph_arret")
def controleph_arret():
   ph_stop("web")
   return redirect('/')

@app.route("/eclairage_arret")
def eclairage_arret():
   eclairage_stop("web")
   return redirect('/')

@app.route("/eclairage_marche")
def eclairage_marche():
   eclairage_start("web")
   return redirect('/')

@app.route("/robot_marche")
def robot_marche():
   robot_start("web")
   return redirect('/')

@app.route("/robot_arret")
def robot_arret():
   robot_stop("web")
   return redirect('/')

#=============================================================
# Le main
#=============================================================

#-------------------------------------------------------------
# On va chercher la configuration dans les fichiers suivants et dans
# cet ordre
#   /etc/pisciweb.cfg
#   ${HOME}/.pisciweb.cfg
#-------------------------------------------------------------
config = ConfigParser.ConfigParser()

config.read(['/etc/pisciweb.cfg', os.path.expanduser('~/.pisciweb.cfg')])

# Lecture des parametres de configuration
#  La configuration generale

#  Le 1wire
oneWireRootDir = config.get('1wire', 'rootDir')
sondeTemperatureEau = config.get('1wire', 'sondeTemperatureEau')
sondeTemperatureLocal = config.get('1wire', 'sondeTemperatureLocal')

#  Le debogage
logFileName = config.get('debug', 'logFile')
logConsole = False

# L'interface web
htmlMain = config.get('web', 'htmlMain')
webPort = config.getint('web', 'port')
debugFlask = config.getboolean('web', 'debugFlask')
logMaxLength  = config.getint('web', 'logMaxLength')
logUseFile = config.getboolean('web', 'logUseFile')

#--------------------------------------------------------
# Les sondes thermiques WARNING : hardcode  pas beau
#--------------------------------------------------------
device_folder_eau = oneWireRootDir  + '/' + sondeTemperatureEau
device_file_eau = device_folder_eau + '/w1_slave'

device_folder_local = oneWireRootDir + '/' + sondeTemperatureLocal
device_file_local = device_folder_local + '/w1_slave'

if __name__ == "__main__":
#--------------------------------------------------------
# Configuration du systeme de log
#--------------------------------------------------------
   logger = logging.getLogger('pisciweb')
   logger.setLevel(logging.DEBUG)
   formatter = logging.Formatter('%(asctime)s - %(levelname)s:%(message)s')
   if (logConsole) :
      # define a Handler which writes INFO messages or higher to the sys.stderr
      console = logging.StreamHandler()
      console.setLevel(logging.INFO)
      console.setFormatter(formatter)
      logging.getLogger('pisciweb').addHandler(console)
   else :
      fh = logging.FileHandler(logFileName)
      fh.setLevel(logging.DEBUG)
      fh.setFormatter(formatter)
      logging.getLogger('pisciweb').addHandler(fh)

   # Ajout d'un handler pour la page web  
   log_handler.setLevel(logging.INFO)
   log_handler.setFormatter(formatter)
   logger.addHandler(log_handler)

   # Gestion des parametres
   parser = argparse.ArgumentParser()
   parser.add_argument("-a", "--afficher", help="Afficher les temperatures",
                    action="store_true")
   parser.add_argument("-e", "--echantillonner", help="Enregistrer une mesure",
                    action="store_true")
   parser.add_argument("-F", "--filtration_start", help="Demarrage de la filtration",
                    action="store_true")
   parser.add_argument("-f", "--filtration_stop", help="Extinction de la filtration",
                    action="store_true")
   parser.add_argument("-R", "--robot_start", help="Demarrage du robot",
                    action="store_true")
   parser.add_argument("-r", "--robot_stop", help="Extinction du robot",
                    action="store_true")
   parser.add_argument("-P", "--ph_start", help="Activation du controle pH",
                    action="store_true")
   parser.add_argument("-p", "--ph_stop", help="Extinction du controle pH",
                    action="store_true")
   parser.add_argument("-L", "--eclairage_start", help="Demarrage de l'eclairage",
                    action="store_true")
   parser.add_argument("-l", "--eclairage_stop", help="Extinction de l'eclairage",
                    action="store_true")
   args = parser.parse_args()

   # On traite les options
   if (args.filtration_start) :
      gpioInit(False)
      filtration_start("cmd line")
      sys.exit()

   if (args.filtration_stop) :
      gpioInit(False)
      filtration_stop("cmd line")
      sys.exit()

   if (args.robot_start) :
      gpioInit(False)
      robot_start("cmd line")
      sys.exit()

   if (args.robot_stop) :
      gpioInit(False)
      robot_stop("cmd line")
      sys.exit()

   if (args.eclairage_start) :
      gpioInit(False)
      eclairage_start("cmd line")
      sys.exit()

   if (args.eclairage_stop) :
      gpioInit(False)
      reclairage_stop("cmd line")
      sys.exit()

   if (args.ph_stop) :
      gpioInit(False)
      ph_stop("cmd line")
      sys.exit()

   if (args.ph_start) :
      gpioInit(False)
      ph_start("cmd line")
      sys.exit()

   if (args.echantillonner) :
      gpioInit(False)  # Pour l'etat de la pompe
      echantillonner()
      sys.exit()

   if (args.afficher) :
      print "Time  : " + str(int(time.time()))
      print "Eau   : " + str(temperature_eau())
      print "Local : " + str(temperature_local())
      sys.exit()

#--------------------------------------------------------
# S'il n'y a pas d'option, le comportement par defaut
# est d'activer le serveur web
#--------------------------------------------------------
   logger.info("Demarrage de pisciweb " + pisciWebVersion)

   gpioInit(True)

   #  Lorsqu'on demarre le serveur, il faut que le systeme
   # soit dans l'etat de base (attention, ca veut dire actif
   # mais eteint)
   for pin in gpioPins:
      gpio.output(pin, gpioPins[pin]['etat'])

   print "Temperature eau " + str(temperature_eau()) + "\n"
   app.run(host='0.0.0.0', port=webPort, debug=debugFlask)

