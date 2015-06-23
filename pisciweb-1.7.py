#--------------------------------------------------------
#   pisciweb : petite interface avec ma piscine.
#--------------------------------------------------------
from flask import Flask, url_for, render_template, redirect
import glob
import time
import datetime
import os
import RPi.GPIO as gpio
import argparse
import sys
import rrdtool

app = Flask(__name__)

#--------------------------------------------------------
# Generalites
#--------------------------------------------------------
pisciWebVersion  = "1.7"  # Ajout de options -R -r -L -l
#pisciWebVersion = "1.6"  # Normalisation des etats marche/arret
#pisciWebVersion = "1.5"  # Ajout de 3  interfaces
#pisciWebVersion = "1.4"  # Utilisation de rrdtool pour loguer
#pisciWebVersion = "1.3"  # introduction de la gestion des arguments
#pisciWebVersion = "1.2"  # Ajout d'un mode debug
#pisciWebVersion = "1.1"  # Ajout d'une desactivation
#pisciWebVersion = "1.0"  # Premiere version operationnelle

#htmlMain="version2.html"
htmlMain="main.html"

repertoire = "/home/pi/pisciweb"

logFileName = "/home/pi/pisciweb/raspiscine.log"
rrd_filename = "tempiscine.rrd"

rrd_file = repertoire + "/" + rrd_filename

sondeTemperatureEau = "28-0000037ae572"
sondeTemperatureLocal = "28-0000037b14c5"

#--------------------------------------------------------
# Logage d'un message
#--------------------------------------------------------
def log(message):
   logFile=open(logFileName, "a");
   logFile.write("["+time.asctime( time.localtime(time.time()) ) + "] " + message + "\n");
   logFile.close()
   
#--------------------------------------------------------
# Les sondes thermiques WARNING : hardcode  pas beau
#--------------------------------------------------------
base_dir = '/sys/bus/w1/devices/'
#device_folder = glob.glob(base_dir + '28*')[0]
device_folder_eau = base_dir + sondeTemperatureEau
device_file_eau = device_folder_eau + '/w1_slave'

device_folder_local = base_dir + sondeTemperatureLocal
device_file_local = device_folder_local + '/w1_slave'

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
# Gestion de rrdtool
#========================================================
def echantillonner():
   t_e = str(temperature_eau())
   t_l = str(temperature_local())
   ps = str(1-gpio.input(pinPompe)) # Le "1-" est la car actif=low
   N = str(int(time.time())) 
   #print rrd_file + " : " + N+":"+t_e+":"+t_l+":"+ps
   #log("Echantillonnage dans " +  rrd_file + " : " + N+":"+t_e+":"+t_l+":"+ps)
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
   log("Allumage de la pompe (" + via + ")")

#--------------------------------------------------------
# Extinction de la pompe
#--------------------------------------------------------
def filtration_stop(via="erreur"):
   gpio.output(pinPompe, gpioArret)
   log("Extinction de la pompe (" + via + ")")

#--------------------------------------------------------
# Mise en marche du ph
#--------------------------------------------------------
def ph_start(via="erreur"):
   gpio.output(pinControlepH, gpioMarche)
   log("Allumage du controle pH (" + via + ")")

#--------------------------------------------------------
# Extinction du controle pH
#--------------------------------------------------------
def ph_stop(via="erreur"):
   gpio.output(pinControlepH, gpioArret)
   log("Extinction du controle pH (" + via + ")")

#--------------------------------------------------------
# Mise en marche du robot
#--------------------------------------------------------
def robot_start(via="erreur"):
   gpio.output(pinRobot, gpioMarche)
   log("Allumage du robot (" + via + ")")

#--------------------------------------------------------
# Extinction du robot
#--------------------------------------------------------
def robot_stop(via="erreur"):
   gpio.output(pinRobot, gpioArret)
   log("Extinction du robot (" + via + ")")

#--------------------------------------------------------
# Mise en marche de l'eclairage
#--------------------------------------------------------
def eclairage_start(via="erreur"):
   gpio.output(pinLumiere, gpioMarche)
   log("Allumage de l'eclairage (" + via + ")")

#--------------------------------------------------------
# Extinction de l'eclairage
#--------------------------------------------------------
def eclairage_stop(via="erreur"):
   gpio.output(pinLumiere, gpioArret)
   log("Extinction de l'eclairage (" + via + ")")


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

   # Along with the pin dictionary, put the message into the template data dictionary:
   templateData = {
      'message' : message,
      'gpioPins' : gpioPins
   }

   return redirect('/debogage')

#--------------------------------------------------------
# La page principale
#--------------------------------------------------------
@app.route("/")
def hello():
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

#--------------------------------------------------------
# Le main
#--------------------------------------------------------
if __name__ == "__main__":
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

   # S'il n'y a pas d'option, le comportement par defaut
   # est d'activer le serveur web
   log("Demmarrage de pisciweb " + pisciWebVersion)

   gpioInit(True)

   #  Lorsqu'on demarre le serveur, il faut que le systeme
   # soit dans l'etat de base (attention, ca veut actif mais 
   # eteint)
   for pin in gpioPins:
      gpio.output(pin, gpioPins[pin]['etat'])

   print "Temperature eau " + str(temperature_eau()) + "\n"
   app.run(host='0.0.0.0', port=8081, debug=False)

